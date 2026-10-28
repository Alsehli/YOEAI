"""Fast read-only Windows Spell Checking API. No inference, uploads or dictionary writes."""
import ctypes as c,uuid,re,json,os,threading,queue,atexit
from contextlib import contextmanager
from language_understanding import LITERAL
P=c.c_void_p;U=c.c_ulong;HRESULT=c.c_long
WORD=re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)?|[\u0621-\u064a\u066e-\u06d3\u06fa-\u06ff]+(?:[\u064b-\u065f\u0670]*[\u0621-\u064a\u066e-\u06d3\u06fa-\u06ff]+)*")
EMAIL=re.compile(r'\b[^\s@]+@[^\s@]+\.[^\s@]+')
BRAND={'yoeai','yoe','qwen','gguf','cuda','searxng'}
_gate=threading.Lock()

def guid(value):return (c.c_ubyte*16).from_buffer_copy(uuid.UUID(value).bytes_le)
class Obj:
 def __init__(self,value):self.p=value if isinstance(value,P) else P(value)
 def call(self,index,types,*args):
  table=c.cast(self.p,c.POINTER(c.POINTER(P))).contents
  hr=c.WINFUNCTYPE(HRESULT,P,*types)(table[index])(self.p,*args)
  if hr<0:raise OSError('Windows spelling API failed: '+hex(hr&0xffffffff))
  return hr
 def close(self):
  if self.p and self.p.value:self.call(2,[]);self.p=P()
 def pointer(self,index,types=(),args=()):
  value=P();self.call(index,[*types,c.POINTER(P)],*args,c.byref(value));return Obj(value) if value.value else None
 def strings(self,limit=8):
  values=[]
  for _ in range(limit):
   value=P();fetched=U();hr=self.call(3,[U,c.POINTER(P),c.POINTER(U)],1,c.byref(value),c.byref(fetched))
   if not fetched.value:break
   try:values.append(c.wstring_at(value))
   finally:c.windll.ole32.CoTaskMemFree(value)
   if hr==1:break
  return values
@contextmanager
def factory():
 if os.name!='nt':raise OSError('Windows spelling is unavailable on this platform.')
 ole=c.windll.ole32;ole.CoTaskMemFree.argtypes=[P];ole.CoTaskMemFree.restype=None
 hr=ole.CoInitializeEx(None,2);initialized=hr>=0
 if hr<0 and (hr&0xffffffff)!=0x80010106:raise OSError('Windows spelling could not initialize.')
 value=P();clsid=guid('7AB36653-1796-484B-BDFA-E74F1DB7C1DC');iid=guid('8E018A9D-2415-4677-BF08-794EA61F94BB');obj=None
 try:
  hr=ole.CoCreateInstance(c.byref(clsid),None,1,c.byref(iid),c.byref(value))
  if hr<0:raise OSError('Windows spelling provider is unavailable.')
  obj=Obj(value);yield obj
 finally:
  if obj:obj.close()
  if initialized:ole.CoUninitialize()
def languages():
 with factory() as f:
  items=f.pointer(3)
  try:return items.strings(100)
  finally:items.close()
def available(f,tag):
 supported=c.c_int();f.call(4,[c.c_wchar_p,c.POINTER(c.c_int)],tag,c.byref(supported));return bool(supported.value)
def prop(obj,index):
 value=U();obj.call(index,[c.POINTER(U)],c.byref(value));return value.value
def replacement(obj):
 value=P();obj.call(6,[c.POINTER(P)],c.byref(value))
 if not value.value:return ''
 try:return c.wstring_at(value)
 finally:c.windll.ole32.CoTaskMemFree(value)
def inspect_word(speller,word):
 errors=speller.pointer(4,[c.c_wchar_p],[word]);result=[]
 if errors is None:return result
 try:
  for _ in range(4):
   error=errors.pointer(3)
   if error is None:break
   try:
    start,length,action=prop(error,3),prop(error,4),prop(error,5)
    if not action:continue
    suggestions=[]
    if action==2:suggestions=[replacement(error)]
    elif action==3:suggestions=['']
    elif action==1:
     words=speller.pointer(5,[c.c_wchar_p],[word])
     if words:
      try:suggestions=words.strings(5)
      finally:words.close()
    result.append({'offset':start,'length':length,'suggestions':suggestions})
   finally:error.close()
 finally:errors.close()
 return result
# Process-only bounded word cache; never persisted and never modifies Windows dictionaries.
_cache={}
def _check(text,f,spellers):
 blocked=[(m.start(),m.end()) for regex in [LITERAL,EMAIL] for m in regex.finditer(text)]
 matches=[m for m in WORD.finditer(text) if len(m.group())>=2 and m.group().lower() not in BRAND and not any(m.start()<b and m.end()>a for a,b in blocked) and not (m.start()>0 and text[m.start()-1]=='_') and not (m.end()<len(text) and text[m.end()]=='_')][:250]
 rows=[];used=[]
 for script,tags in [('en',['en-US','en-GB']),('ar',['ar-SA','ar-BH','ar-EG','ar-AE'])]:
  if not any(('ar' if '\u0600'<=m.group()[0]<='\u06ff' else 'en')==script for m in matches):continue
  if script not in spellers:
   tag=next((tag for tag in tags if available(f,tag)),None);spellers[script]=(tag,f.pointer(5,[c.c_wchar_p],[tag])) if tag else None
  if spellers[script]:used.append(spellers[script][0])
 for m in matches:
  pair=spellers.get('ar' if '\u0600'<=m.group()[0]<='\u06ff' else 'en')
  if not pair:continue
  tag,speller=pair;word=m.group();key=(tag,word)
  if key not in _cache:
   if len(_cache)>4096:_cache.clear()
   _cache[key]=inspect_word(speller,word)
  for error in _cache[key]:
   raw=word.encode('utf-16-le');offset=error['offset'];length=error['length'];original=raw[offset*2:(offset+length)*2].decode('utf-16-le');start=len(text[:m.start()].encode('utf-16-le'))//2+offset
   if original:rows.append({'start':start,'end':start+length,'original':original,'suggestions':error['suggestions']})
 return {'edits':rows,'languages':used}
_requests=queue.Queue(4)
_worker=None
_worker_lock=threading.Lock()
def _run():
 try:
  with factory() as f:
   spellers={}
   try:
    while True:
     request=_requests.get()
     if request is None:return
     text,done,result=request
     try:result['value']=_check(text,f,spellers)
     except Exception as ex:result['error']=str(ex)
     finally:done.set()
   finally:
    for pair in spellers.values():
     if pair:pair[1].close()
 except Exception as ex:
  while True:
   try:request=_requests.get_nowait()
   except queue.Empty:break
   if request:request[2]['error']=str(ex);request[1].set()
def check(text):
 global _worker
 if not isinstance(text,str) or len(text)>8000:raise ValueError('Use up to 8,000 characters.')
 if '```' in text:return {'edits':[],'languages':[]}
 done=threading.Event();result={}
 with _worker_lock:
  _requests.put_nowait((text,done,result))
  if _worker is None or not _worker.is_alive():_worker=threading.Thread(target=_run,name='YOEAI-Windows-Spelling',daemon=True);_worker.start()
 if not done.wait(1.5):raise OSError('Windows spelling did not respond.')
 if 'error' in result:raise OSError(result['error'])
 return result['value']
def _stop():
 if _worker and _worker.is_alive():
  try:_requests.put_nowait(None)
  except queue.Full:return
  _worker.join(1)
atexit.register(_stop)

def route(h,post=False):
 from urllib.parse import urlsplit
 if urlsplit(h.path).path!='/writing/spell':return False
 if not post or not h.allowed() or h.headers.get('Origin')!='http://'+h.headers.get('Host',''):h.json(403,{'error':'Use the local input.'});return True
 try:
  if h.headers.get('Transfer-Encoding'):raise ValueError('Unsupported request.')
  n=int(h.headers.get('Content-Length','0'))
  if not 0<n<=40000:raise ValueError('Input too large.')
  body=json.loads(h.rfile.read(n));result=check(body.get('text'));h.json(200,{'status':'checked',**result})
 except (ValueError,OSError,TypeError,AttributeError,queue.Full):h.json(200,{'status':'unavailable','edits':[]})
 return True
