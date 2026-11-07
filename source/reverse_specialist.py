"""Pinned local specialist. No binary execution or network inference."""
import json,os,time,hashlib,threading,subprocess,queue,urllib.request,shutil
from pathlib import Path
from configuration import APP_DIR,HOME
MANIFEST=Path(APP_DIR)/'reverse-specialist-model.json'
MODEL=Path('C:/AI/Models/LLM4Decompile-1.3B-v2')
PYTHON=Path('E:/YOEAI-Runtimes/Bark/venv/Scripts/python.exe')
LOCK=threading.Lock(); CANCEL=threading.Event(); STATE={'state':'idle','bytes':0,'total':2694355079}; VERIFIED=False
SETTINGS=Path(HOME)/'reverse-specialist.json'

def metadata():return json.loads(MANIFEST.read_text(encoding='utf-8'))
def settings():
 try:v=json.loads(SETTINGS.read_text(encoding='utf-8'))
 except (OSError,ValueError):v={}
 return {'mode':v.get('mode','Automatic')}
def configure(mode):
 if mode not in ['Automatic','Enabled','Disabled']:raise ValueError('Choose Automatic, Enabled or Disabled.')
 SETTINGS.write_text(json.dumps({'mode':mode}),encoding='utf-8');return status()
def digest(p,meta):
 if not p.is_file() or p.is_symlink() or p.stat().st_size!=meta['size']:return False
 with p.open('rb') as f:
  if meta.get('sha256'):return hashlib.file_digest(f,'sha256').hexdigest()==meta['sha256']
  h=hashlib.sha1(('blob '+str(meta['size'])+'\0').encode())
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
  return h.hexdigest()==meta['gitBlob']
def verify():
 global VERIFIED
 VERIFIED=all(digest(MODEL/name,m) for name,m in metadata()['files'].items());return VERIFIED
def status():
 m=metadata();return {**STATE,**settings(),'installed':(VERIFIED or (MODEL/'verified.json').is_file()) and all((MODEL/n).is_file() and (MODEL/n).stat().st_size==v['size'] for n,v in m['files'].items()),'runtimeAvailable':PYTHON.is_file(),'path':str(MODEL),'repository':m['repository'],'revision':m['revision'],'licenseNotice':m['licenseNotice']}
def install():
 if not LOCK.acquire(False):raise ValueError('Specialist is busy.')
 CANCEL.clear();threading.Thread(target=_install,daemon=True).start();return status()
def _install():
 global VERIFIED
 try:
  m=metadata();MODEL.mkdir(parents=True,exist_ok=True);STATE.update(state='downloading',error=None,bytes=0,total=sum(x['size'] for x in m['files'].values()))
  for name,info in m['files'].items():
   p=MODEL/name
   if digest(p,info):STATE['bytes']+=info['size'];continue
   if p.exists():raise ValueError('Existing '+name+' failed verification. It was preserved; repair it explicitly before retrying.')
   part=p.with_name(p.name+'.partial');offset=part.stat().st_size if part.exists() else 0
   req=urllib.request.Request('https://huggingface.co/'+m['repository']+'/resolve/'+m['revision']+'/'+name,headers={'Range':f'bytes={offset}-'} if offset else {})
   if shutil.disk_usage(MODEL).free<info['size']-offset+100_000_000:raise ValueError('Not enough free space for the model.')
   with urllib.request.urlopen(req,timeout=45) as response:
    if offset and response.status!=206:offset=0
    STATE['bytes']+=offset
    with part.open('ab' if offset else 'wb') as out:
     while True:
      if CANCEL.is_set():raise InterruptedError('Download cancelled; partial files retained for resume.')
      chunk=response.read(1024*1024)
      if not chunk:break
      if out.tell()+len(chunk)>info['size']:raise ValueError('Download exceeds expected file size.')
      out.write(chunk);STATE['bytes']+=len(chunk)
   if not digest(part,info):raise ValueError('Integrity check failed for '+name+'. Partial file retained.')
   os.replace(part,p)
  VERIFIED=True;(MODEL/'verified.json').write_text(json.dumps({'revision':m['revision'],'verifiedAt':time.time()}));STATE.update(state='ready')
 except Exception as ex:STATE.update(state='cancelled' if CANCEL.is_set() else 'error',error=str(ex)[:600])
 finally:LOCK.release()
def cancel_install():CANCEL.set();return status()
def scheduling():
 # Conservative reservation: fp16 weights + bounded KV + CUDA overhead + safety reserve.
 try:
  from runtime import gpu_status
  g=gpu_status();free=g['total']-g['used'];return {'device':'cuda' if free>=4800 else 'cpu','freeMiB':free,'requiredMiB':4800,'gpu':g}
 except Exception:return {'device':'cpu','reason':'GPU telemetry unavailable; no GPU allocation attempted.'}
def extract(result):
 try:body=result.get('structuredContent') or json.loads(next(v['text'] for v in result.get('content',[]) if v.get('type')=='text'))
 except (ValueError,StopIteration):return None
 value=body.get('normalized_result',body.get('result'))
 return value if isinstance(value,str) and 10<len(value)<=40000 else None

def refine(e,t,item,procedure,result,headers):
 mode=settings()['mode']
 if mode=='Disabled':return None
 original=extract(result)
 if not original or headers.get('machine') not in ['0x8664','0x14c']:return {'specialist':'skipped','reason':'Supported x86/x64 Ghidra function text is required.'}
 try:
  if not LOCK.acquire(False):raise ValueError('The specialist installer or another function is busy.')
  try:
   if not VERIFIED and not verify():raise ValueError('Specialist model is not installed or its integrity check failed. Use Install specialist in Reverse YOE settings.')
   if not PYTHON.is_file():raise ValueError('The optional local Transformers runtime is unavailable.')
   m=metadata();key=hashlib.sha256(json.dumps([item['sha256'],procedure,original,m['revision'],4096,384],sort_keys=True).encode()).hexdigest()
   cache=Path(e.home)/'ReverseSpecialistCache';cache.mkdir(exist_ok=True);cached=cache/(key+'.json')
   if cached.is_file():
    v=json.loads(cached.read_text(encoding='utf-8'));v['cached']=True;return v
   execution=scheduling();e.check(t);e.event(t,'Refining one observed Ghidra function locally on '+execution['device'].upper()+'.')
   worker=Path(APP_DIR)/'reverse_specialist_worker.py'
   env=os.environ.copy();env.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1')
   flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
   p=subprocess.Popen([str(PYTHON),str(worker),str(MODEL),execution['device']],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',env=env,creationflags=flags)
   results=queue.Queue()
   def communicate():
    try:results.put(p.communicate(json.dumps({'code':original,'maxTokens':384})))
    except Exception as ex:results.put(ex)
   threading.Thread(target=communicate,daemon=True).start();start=time.monotonic();STATE.update(state='refining',device=execution['device'])
   try:
    while p.poll() is None:
     e.check(t)
     if time.monotonic()-start>240:raise TimeoutError('Specialist function inference exceeded four minutes; original analysis is preserved.')
     time.sleep(.1)
    output=results.get(timeout=5)
    if isinstance(output,Exception):raise output
    stdout,stderr=output
    if p.returncode:
     if execution['device']=='cuda' and any(x in stderr.lower() for x in ['out of memory','available vram changed','cuda error']):
      e.check(t);e.event(t,'GPU memory became insufficient; retrying this function locally on CPU.')
      execution={'device':'cpu','reason':'CUDA allocation failed; no Qwen model was unloaded.'}
      # Retry through a fresh process after the GPU process has exited.
      cpu=subprocess.Popen([str(PYTHON),str(worker),str(MODEL),'cpu'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',env=env,creationflags=flags)
      p=cpu;results=queue.Queue();threading.Thread(target=communicate,daemon=True).start();start=time.monotonic()
      while p.poll() is None:
       e.check(t)
       if time.monotonic()-start>240:raise TimeoutError('CPU fallback timed out; original analysis is preserved.')
       time.sleep(.1)
      output=results.get(timeout=5)
      if isinstance(output,Exception):raise output
      stdout,stderr=output
     if p.returncode:raise ValueError('Specialist runtime failed: '+stderr[-700:])
    v=json.loads(stdout.strip().splitlines()[-1]);v.update(original=original,procedure=procedure,file=item['name'],model=m['repository'],revision=m['revision'],execution=execution,cached=False,notice='Unverified generated C candidate; not original source and not behaviorally verified.')
    if not v.get('refined') or len(v['refined'])>30000:raise ValueError('Specialist returned empty or invalid output.')
    cached.write_text(json.dumps(v,ensure_ascii=False),encoding='utf-8');e.check(t);return v
   finally:
    if p.poll() is None:p.terminate()
    try:p.wait(timeout=5)
    except subprocess.TimeoutExpired:p.kill();p.wait()
    STATE.update(state='ready')
  finally:LOCK.release()
 except Exception as ex:
  e.check(t);e.event(t,'Specialist unavailable; continuing with original Ghidra evidence: '+str(ex)[:250]);return {'specialist':'unavailable','reason':str(ex)[:700],'original':original,'procedure':procedure,'file':item['name']}
