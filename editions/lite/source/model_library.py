"""Persistent, bounded background discovery of user-owned local GGUF files.
Discovery never loads models, copies weights, downloads files or follows nested junctions.
"""
import json,os,re,struct,threading,time
from pathlib import Path

def local_folder(value):
 if not isinstance(value,str) or not value.strip() or len(value)>2000:raise ValueError('Choose a local model folder.')
 value=value.strip()
 if value.startswith(('\\\\','//')):raise ValueError('Choose a folder on a local drive.')
 from security_paths import user_local_path
 path=user_local_path(value)
 if not path.is_absolute():raise ValueError('Use the full local folder path.')
 path=path.resolve()
 if str(path).startswith(('\\\\','//')):raise ValueError('Network model folders are not supported.')
 if os.name=='nt':
  import ctypes
  if ctypes.windll.kernel32.GetDriveTypeW(str(path.anchor))==4:raise ValueError('Choose a local drive, not a mapped network drive.')
 return path

def default_folder(app,home):
 app=Path(app)
 return Path(app.anchor)/'YOEAI-Models' if app.drive and app.drive.upper()!='C:' else Path(home)/'Models'

def linked(path):
 try:return path.is_symlink() or bool(getattr(path.stat(follow_symlinks=False),'st_file_attributes',0)&0x400)
 except OSError:return True

class Library:
 def __init__(self,home,default,interval=5,start=True):
  self.config=Path(home)/'model-folder.json';self.lock=threading.RLock();self.stop_event=threading.Event();self.wake=threading.Event();self.interval=max(1,interval);self.generation=0;self.observed={};self.thread=None
  folder=str(default);error=None
  try:
   if self.config.is_file():folder=json.loads(self.config.read_text(encoding='utf-8-sig'))['folder']
   else:
    local_folder(folder).mkdir(parents=True,exist_ok=True)
    tmp=self.config.with_name(self.config.name+'.tmp');tmp.write_text(json.dumps({'folder':folder},indent=2),encoding='utf8');tmp.replace(self.config)
   self.folder=local_folder(folder)
  except (OSError,ValueError,KeyError,TypeError) as ex:self.folder=Path(default);error=str(ex)
  self.config_error=error
  self.state={'folder':str(self.folder),'models':[],'count':0,'scanning':False,'error':error,'available':False,'pendingFiles':0,'automatic':True,'intervalSeconds':self.interval,'lastScan':None}
  if start:
   self.thread=threading.Thread(target=self._watch,daemon=True,name='YOEAI-model-folder');self.thread.start()
 def snapshot(self):
  with self.lock:return dict(self.state,models=[dict(m) for m in self.state['models']])
 def set_folder(self,value):
  folder=local_folder(value)
  if not folder.is_dir():raise ValueError('Choose an existing folder, or create it in File Explorer first.')
  with self.lock:
   tmp=self.config.with_name(self.config.name+'.tmp');tmp.write_text(json.dumps({'folder':str(folder)},indent=2),encoding='utf8');tmp.replace(self.config)
   self.config_error=None;self.folder=folder;self.generation+=1;self.observed={};self.state.update(folder=str(folder),models=[],count=0,error=None,pendingFiles=0,lastScan=None,available=True)
  self.request_scan();return self.snapshot()
 def request_scan(self):self.wake.set()
 def _watch(self):
  while not self.stop_event.is_set():
   self.wake.clear();self.scan_once();self.wake.wait(self.interval)
 def scan_once(self,now=None):
  now=time.monotonic() if now is None else now
  with self.lock:
   if self.config_error:return
   folder=self.folder;generation=self.generation;old=dict(self.observed);self.state['scanning']=True
  models=[];seen={};pending=0;visited=0;examined=0;error=None;available=False;started=time.monotonic();limited=False
  try:
   folder=local_folder(str(folder))
   if not folder.is_dir():raise ValueError('Model folder is unavailable. Reconnect its drive or choose another folder.')
   available=True
   for parent,dirs,files in os.walk(folder,followlinks=False):
    visited+=1;parent=Path(parent)
    dirs[:]=[d for d in dirs if not d.startswith('.') and not linked(parent/d)]
    if len(parent.relative_to(folder).parts)>=4:dirs[:]=[]
    for name in files:
     if self.stop_event.is_set():break
     examined+=1
     if examined>10000 or time.monotonic()-started>3:limited=True;break
     lower=name.lower()
     if not lower.endswith('.gguf') or lower.startswith(('mmproj','projector')) or re.search(r'-\d{5}-of-\d{5}\.gguf$',lower):continue
     path=parent/name
     if linked(path):continue
     try:
      stat=path.stat();stamp=(stat.st_size,stat.st_mtime_ns)
      if stat.st_size<24:continue
      with path.open('rb') as stream:header=stream.read(8)
      if header[:4]!=b'GGUF' or len(header)!=8 or struct.unpack('<I',header[4:])[0] not in (2,3):continue
      identity=str(path);previous=old.get(identity);stable_since=previous[1] if previous and previous[0]==stamp else now;seen[identity]=(stamp,stable_since)
      if now-stable_since<1:pending+=1;continue
      models.append({'model':identity,'name':name,'projector':'','bytes':stat.st_size,'validation':'Detected GGUF; full compatibility is checked when loading.'})
     except OSError:continue
     if len(models)>=200:limited=True;break
    if limited or visited>=1000 or self.stop_event.is_set():limited=limited or visited>=1000;break
   if limited:error='Large folder: showing up to 200 models within a bounded scan. Choose a dedicated models folder for complete discovery.'
  except (OSError,ValueError) as ex:error=str(ex)
  with self.lock:
   if generation!=self.generation:return
   self.observed=seen;self.state.update(models=sorted(models,key=lambda m:m['name'].casefold()),count=len(models),pendingFiles=pending,scanning=False,error=error,available=available,lastScan=time.time())
 def close(self):
  self.stop_event.set();self.wake.set()
  if self.thread and self.thread is not threading.current_thread():self.thread.join(timeout=4)
