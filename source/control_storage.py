"""Cancelable, read-only drive metadata scans. No file contents or write tools."""
import os,re,time,uuid,heapq,threading,copy
from pathlib import Path
from windows_policy import PROTECTED,PRIVATE_NAME,redact
from control_router import storage_request

class Storage:
 def __init__(self,e):self.e=e;self.jobs={};self.lock=threading.RLock()
 def snapshot(self,jid):
  with self.lock:
   if jid not in self.jobs:raise ValueError('Storage scan is unavailable; start a new scan.')
   return copy.deepcopy({k:v for k,v in self.jobs[jid].items() if k not in ['cancel','pause']})
 def start(self,text):
  request=storage_request(text)
  if not request or request.get('question'):raise ValueError((request or {}).get('question','Name the drive and the number of largest files to show.'))
  root=Path(request['drive'])
  if os.name!='nt':raise ValueError('Drive scanning requires Windows.')
  import ctypes
  if ctypes.windll.kernel32.GetDriveTypeW(str(root)) not in [2,3]:raise ValueError('Choose a connected local or removable drive; network/device paths are not scanned.')
  if not root.is_dir():raise ValueError('The requested drive is not connected.')
  with self.lock:
   if any(j['status'] in ['RUNNING','PAUSED'] for j in self.jobs.values()):raise ValueError('Stop or finish the current storage scan first.')
   for jid in list(self.jobs)[:-8]:self.jobs.pop(jid,None)
   jid=uuid.uuid4().hex;j={'id':jid,'drive':str(root),'limit':request['limit'],'status':'RUNNING','count':0,'skipped':0,'partial':False,'files':[],'error':None,'started':time.time(),'cancel':threading.Event(),'pause':threading.Event()};self.jobs[jid]=j
  threading.Thread(target=self.scan,args=(j,root),daemon=True,name='YOE-Control-storage').start();return self.snapshot(jid)
 def action(self,jid,op):
  with self.lock:
   if jid not in self.jobs:raise ValueError('Storage scan not found.')
   j=self.jobs[jid]
   if j['status'] not in ['RUNNING','PAUSED']:return self.snapshot(jid)
   if op=='cancel':j['cancel'].set()
   elif op=='pause':j['pause'].set();j['status']='PAUSED'
   elif op=='resume':j['pause'].clear();j['status']='RUNNING'
   else:raise ValueError('Unsupported storage control.')
  return self.snapshot(jid)
 def scan(self,j,root):
  stack=[root];heap=[];deadline=time.monotonic()+120
  try:
   while stack:
    if j['cancel'].is_set() or self.e.closed:raise InterruptedError('Scan stopped; files were not changed.')
    if j['pause'].is_set():time.sleep(.05);deadline+=.05;continue
    if j['count']>=500000 or time.monotonic()>deadline:j['partial']=True;break
    folder=stack.pop()
    try:
     if folder.is_symlink() or folder!=root and getattr(folder.lstat(),'st_file_attributes',0)&0x400 or not folder.resolve().is_relative_to(root.resolve()):j['skipped']+=1;continue
     with os.scandir(folder) as entries:
      for ent in entries:
       if j['cancel'].is_set() or self.e.closed:raise InterruptedError('Scan stopped; files were not changed.')
       if j['pause'].is_set():
        while j['pause'].is_set() and not j['cancel'].is_set() and not self.e.closed:time.sleep(.05);deadline+=.05
       if j['count']>=500000 or time.monotonic()>deadline:j['partial']=True;break
       try:
        st=ent.stat(follow_symlinks=False);j['count']+=1
        if ent.is_symlink() or getattr(st,'st_file_attributes',0)&(0x400|2|4) or ent.name.startswith('.') or ent.name.lower() in PROTECTED or PRIVATE_NAME.search(ent.name):j['skipped']+=1;continue
        if ent.is_dir(follow_symlinks=False):
         if len(stack)<10000 and len(Path(ent.path).parts)<48:stack.append(Path(ent.path))
         else:j['partial']=True
        elif ent.is_file(follow_symlinks=False):
         item=(st.st_size,ent.path)
         if len(heap)<j['limit']:heapq.heappush(heap,item)
         elif item>heap[0]:heapq.heapreplace(heap,item)
       except OSError:j['skipped']+=1
    except OSError:j['skipped']+=1
   if j['cancel'].is_set():raise InterruptedError('Scan stopped; files were not changed.')
   j['status']='COMPLETED'
  except InterruptedError:j['status']='CANCELLED'
  except Exception as ex:j.update(status='FAILED',error=redact(str(ex))[:500])
  finally:
   with self.lock:j['files']=[{'path':p,'bytes':size} for size,p in sorted(heap,reverse=True)];j['finished']=time.time()

def service(e):
 if not hasattr(e,'control_storage'):e.control_storage=Storage(e)
 return e.control_storage
