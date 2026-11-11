"""Additional P-H3 engine; shares the existing GPU lock, chat gate and outputs."""
import json,os,re,subprocess,threading,time,uuid
from pathlib import Path
from image_generation import ImageGenerator

class PH3Generator(ImageGenerator):
 def config(self):
  c=json.loads(self.config_path.read_text(encoding='utf-8-sig'))
  for key in ('python','worker','backendRoot'):
   c[key]=str((self.config_path.parent/c[key]).resolve())
  if c.get('enabled') is not True:raise ValueError('P-H3-Image is being installed and tested. Image Turbo is available.')
  for key in ('python','worker'):
   if not Path(c[key]).is_file():raise ValueError('P-H3 component missing: '+key)
  root=Path(c['backendRoot']);assets=json.loads((root/'model-assets.json').read_text())
  for asset in assets['files']:
   path=root/'Models'/asset['path']
   if not path.is_file() or path.stat().st_size!=asset['bytes']:raise ValueError('P-H3 models need repair; no alternate model was used.')
  return c
 def start(self,body):
  if not isinstance(body,dict):raise ValueError('Invalid image request')
  prompt=body.get('prompt');size=body.get('size',2912)
  if not isinstance(prompt,str) or not 1<=len(prompt.strip())<=2000:raise ValueError('Describe the image in 1 to 2,000 characters.')
  if type(size) is not int or size not in (2048,2912):raise ValueError('Choose 2048 or 2912 pixels for P-H3-Image.')
  c=self.config()
  with self.lock:
   if self.state['status'] in ('running','restoring'):raise ValueError('An image is already being created.')
   self.cancelled.clear();job=uuid.uuid4().hex;self.state={'status':'running','message':'Preparing P-H3-Image...','id':job,'engine':'ph3','started':time.time()}
   self.worker=threading.Thread(target=self.run,args=(c,prompt.strip(),size,job),daemon=True);self.worker.start()
  return self.status()
 def cancel(self):
  self.cancelled.set()
  with self.lock:process=self.process
  if process is not None and process.poll() is None:
   import psutil
   try:
    children=psutil.Process(process.pid).children(recursive=True)
    for child in reversed(children):
     try:child.terminate()
     except psutil.NoSuchProcess:pass
    process.terminate();psutil.wait_procs(children,timeout=10)
    for child in children:
     try:
      if child.is_running():child.kill()
     except psutil.NoSuchProcess:pass
   except psutil.NoSuchProcess:pass
  return self.status()
 def status(self):
  value=super().status()
  if value.get('id') and value['status']=='running':
   log=self.home/(value['id']+'.log')
   if log.exists():
    with log.open('rb') as f:f.seek(max(0,log.stat().st_size-8000));tail=f.read().decode('utf8','replace')
    stages=[line[10:] for line in tail.splitlines() if line.startswith('PH3_STAGE ')]
    if stages:value['message']=stages[-1]
    steps=re.findall(r'(\d+)/8\s*\[',tail)
    if steps:value['message']='P-H3-Image rendering step '+steps[-1]+' of 8'
    elif 'Generating tokens:' in tail:value['message']='Refining your prompt locally...'
    with self.lock:self.state['message']=value['message']
  return value
 def run(self,c,prompt,size,job):
  paused=False;handle=None;started=time.monotonic();result={'id':job,'engine':'ph3','model':'P-H3-Image'};self.home.mkdir(parents=True,exist_ok=True)
  folder=self.home/(job+'.ph3');folder.mkdir();request=folder/'request.json';output=self.home/(job+'.png');partial=folder/'result.png';lock=getattr(self,'gpu_lock',self.config_path.parent/'generation.lock')
  try:
   try:handle=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
   except FileExistsError:raise ValueError('Another image or video job owns the GPU.')
   os.write(handle,str(os.getpid()).encode())
   if self.pause:paused=bool(self.pause())
   if self.cancelled.is_set():raise InterruptedError('Image creation stopped.')
   seed=int.from_bytes(os.urandom(4),'little');request.write_text(json.dumps({'executionAuthorized':True,'backendRoot':c['backendRoot'],'prompt':prompt,'size':size,'seed':seed,'output':str(partial)}))
   env=dict(os.environ,PYTHONNOUSERSITE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
   with (self.home/(job+'.log')).open('w',encoding='utf8') as log:
    with self.lock:
     if self.cancelled.is_set():raise InterruptedError('Image creation stopped.')
     self.process=subprocess.Popen([c['python'],'-u',c['worker'],'--request',str(request)],env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    try:code=self.process.wait(timeout=2700)
    except subprocess.TimeoutExpired:self.cancel();raise ValueError('P-H3 timed out; no substitute image was generated.')
   if self.cancelled.is_set():raise InterruptedError('Image creation stopped.')
   if code or not partial.exists():raise ValueError('P-H3-Image failed. See the image job log; no alternate model was used.')
   from PIL import Image,ImageStat
   with Image.open(partial) as image:
    image.verify()
   with Image.open(partial) as image:
    width,height=image.size
    if max(ImageStat.Stat(image.convert('RGB')).stddev)<1:raise ValueError('P-H3 produced an empty image.')
   partial.replace(output);result.update(status='complete',message='Image ready.',url='/imagegen/output/'+job,width=width,height=height,seed=seed,seconds=round(time.monotonic()-started,1))
  except InterruptedError as error:result.update(status='cancelled',message=str(error))
  except Exception as error:result.update(status='error',message=str(error))
  finally:
   with self.lock:self.process=None
   if paused and self.resume:
    self.state.update(status='restoring',message='Restoring your chat model...')
    try:self.resume()
    except Exception as error:result.update(chatRestartFailed=True,message=result.get('message','')+' Chat restore failed: '+str(error))
   if handle is not None:os.close(handle);lock.unlink(missing_ok=True)
   self.state=result
