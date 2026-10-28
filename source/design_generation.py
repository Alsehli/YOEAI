"""Isolated MOSS image subprocess and the existing Turbo image-engine selector."""
import json,os,threading,time,uuid,subprocess,hashlib
from pathlib import Path
from image_generation import ImageGenerator,has_visual_content,handle_request
from configuration import APP_DIR

ACTIVE={'running','restoring','installing'}

def load_json(path,default=None):
 try:return json.loads(Path(path).read_text(encoding='utf-8-sig'))
 except (OSError,ValueError):return {} if default is None else default

class DesignGenerator(ImageGenerator):
 def __init__(self,config_path,pause,resume,gpu_lock):
  self.base=Path(config_path).parent;self.gpu_lock=Path(gpu_lock)
  super().__init__(config_path,self.base/'Outputs',pause,resume,max_size=1536)
 def config(self):
  c=load_json(self.config_path)
  install=load_json(self.base/'installation.json')
  if install.get('status') in ['Downloading','Installing'] and time.time()-install.get('updated',0)<120:raise ValueError('Design installation is still active. Wait for file and backend verification.')
  for key in ['python','modelDirectory']:
   if not Path(c.get(key,'__missing__')).exists():raise ValueError('Design needs setup. Generate will prepare it automatically.')
  verified=load_json(self.base/'files-verified.json');backend=load_json(self.base/'backend.json')
  if verified.get('revision')!=c.get('revision') or not backend.get('cudaAvailable'):raise ValueError('Design setup verification is incomplete. Generate will check it automatically.')
  manifest=load_json(self.base/'model-manifest.json');model=Path(c['modelDirectory'])
  for f in manifest.get('siblings',[]):
   p=model/f['rfilename']
   if not p.is_file() or p.stat().st_size!=f['size']:raise ValueError('Design model file missing or incomplete: '+f['rfilename'])
  if not manifest.get('siblings'):raise ValueError('Design model manifest is missing.')
  return c
 def start(self,body):
  prompt=body.get('prompt');width=body.get('width',body.get('size',768));height=body.get('height',body.get('size',768));steps=body.get('steps',50);guidance=body.get('guidance',3.0);negative=body.get('negativePrompt','')
  if not isinstance(prompt,str) or not 1<=len(prompt.strip())<=16000:raise ValueError('Describe your design in 1–16,000 characters, including supported JSON layout prompts.')
  if prompt.lstrip().startswith('{'):
   try:json.loads(prompt)
   except ValueError:raise ValueError('The structured layout prompt must be valid JSON.')
  if any(type(n) is not int or n<256 or n>1536 or n%16 for n in [width,height]) or width*height>1536**2:raise ValueError('Design dimensions must be multiples of 16 from 256 to 1536.')
  if type(steps) is not int or not 10<=steps<=100:raise ValueError('Choose 10–100 Design steps. The official default is 50.')
  if type(guidance) not in [int,float] or not 0<=guidance<=10:raise ValueError('Choose a finite guidance value from 0 to 10.')
  if not isinstance(negative,str) or len(negative)>4000:raise ValueError('Negative prompt is limited to 4,000 characters.')
  with self.lock:
   if self.state['status'] in ACTIVE:raise ValueError('An image job is already active.')
   self.cancelled.clear();job=uuid.uuid4().hex;self.state={'status':'installing','engine':'design','message':'Checking Design automatically…','id':job,'started':time.time()}
   self.worker=threading.Thread(target=self.prepare_and_run,args=({'prompt':prompt.strip(),'width':width,'height':height,'steps':steps,'guidance':guidance,'negativePrompt':negative},job),daemon=True);self.worker.start()
  return self.status()
 def runtime_ready(self):
  c=self.config();key=(c['python'],Path(c['python']).stat().st_mtime_ns,load_json(self.base/'backend.json'))
  if getattr(self,'runtime_checked',None)==key:return c
  env=os.environ.copy();env.update(PYTHONNOUSERSITE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
  try:
   result=subprocess.run([c['python'],'-I','-c','import torch,diffusers,transformers,accelerate,safetensors; assert torch.cuda.is_available(), "CUDA unavailable"'],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,timeout=60,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
  except (OSError,subprocess.TimeoutExpired) as ex:raise ValueError('Design runtime check failed: '+str(ex))
  if result.returncode:raise ValueError('Design runtime needs repair: '+result.stderr.decode(errors='replace')[-800:])
  self.runtime_checked=key;return c
 def prepare_and_run(self,request,job):
  try:
   try:c=self.runtime_ready()
   except ValueError:
    if not getattr(self,'ensure_ready',None):raise
    self.ensure_ready(self.cancelled,self.setup_progress)
    c=self.runtime_ready()
   if self.cancelled.is_set():raise InterruptedError('Design generation stopped before loading the model.')
   with self.lock:self.state.update(status='running',message='Preparing Design locally…')
   self.run_design(c,request,job)
  except InterruptedError as ex:
   with self.lock:self.state={'status':'cancelled','engine':'design','message':str(ex),'id':job}
  except Exception as ex:
   with self.lock:self.state={'status':'error','engine':'design','message':'Design could not finish automatic setup: '+str(ex),'id':job}
 def setup_progress(self,info):
  with self.lock:
   self.state.update(status='installing',message=info.get('message') or 'Preparing Design automatically…',downloadedBytes=info.get('downloadedBytes',0),totalBytes=info.get('totalBytes',0))
 def status(self):
  state=super().status()
  if state.get('status')=='running' and state.get('id'):
   progress=load_json(self.home/(state['id']+'.progress.json'))
   if progress:state.update({k:v for k,v in progress.items() if k in ['message','step','steps','phase','metrics']})
  state['engine']='design';return state
 def run_design(self,c,request,job):
  paused=False;handle=None;result={};self.home.mkdir(parents=True,exist_ok=True);started=time.time();output=self.home/(job+'.png');log=self.home/(job+'.log')
  try:
   try:handle=os.open(self.gpu_lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
   except FileExistsError:raise ValueError('Another image or video job is using the GPU. Wait for it to finish.')
   os.write(handle,str(os.getpid()).encode())
   self.state['message']='Pausing chat and unloading inactive models…'
   if self.pause:paused=bool(self.pause())
   if self.cancelled.is_set():raise InterruptedError('Design generation stopped.')
   request.update(output=str(output),modelDirectory=c['modelDirectory'],approval=str(self.base/'code-approval.json'),seed=int.from_bytes(os.urandom(4),'little'),revision=c['revision'])
   jobfile=self.home/(job+'.request.json');jobfile.write_text(json.dumps(request,ensure_ascii=False),encoding='utf8')
   worker=APP_DIR/'assets/design-engine/worker.py'
   env=os.environ.copy();env.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_DATASETS_OFFLINE='1',HF_HOME=str(self.base/'Cache'),PYTHONUTF8='1',PYTHONNOUSERSITE='1')
   with log.open('w',encoding='utf8') as trace:
    with self.lock:
     if self.cancelled.is_set():raise InterruptedError('Design generation stopped.')
     self.process=subprocess.Popen([c['python'],'-I',str(worker),str(jobfile)],cwd=self.base,env=env,stdin=subprocess.DEVNULL,stdout=trace,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    try:code=self.process.wait(timeout=3600)
    except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=20);raise ValueError('Design exceeded one hour. Try a smaller image or fewer steps.')
   if self.cancelled.is_set():raise InterruptedError('Design generation stopped.')
   metrics=load_json(output.with_suffix('.json'))
   if code or not output.is_file() or not has_visual_content(output):
    error=load_json(output.with_suffix('.progress.json')).get('error')
    raise ValueError(error or 'Design produced no usable image. See its local generation log.')
   result={'status':'complete','engine':'design','message':'Design image ready.','id':job,'url':'/imagegen/output/'+job,'seconds':round(time.time()-started,1),'seed':request['seed'],'width':request['width'],'height':request['height'],'metrics':metrics}
   (self.base/'ready.json').write_text(json.dumps({'revision':c['revision'],'verifiedByActualGeneration':True,'output':str(output),'time':time.time()}),encoding='utf8')
  except InterruptedError as e:result={'status':'cancelled','engine':'design','message':str(e),'id':job}
  except Exception as e:result={'status':'error','engine':'design','message':str(e),'id':job}
  finally:
   with self.lock:self.process=None
   if paused and self.resume:
    self.state.update(status='restoring',message='Design model unloaded. Restoring local chat…')
    try:self.resume()
    except Exception:result['message']=result.get('message','')+' Chat restart failed; reopen YOEAI.';result['chatRestartFailed']=True
   if handle is not None:
    os.close(handle)
    try:self.gpu_lock.unlink()
    except OSError:pass
   with self.lock:self.state=result

class ImageEngines:
 def __init__(self,turbo,design):self.turbo=turbo;self.design=design;self.current=turbo;self.lock=threading.RLock();self.installer=None;design.ensure_ready=self.prepare_design
 @property
 def state(self):return self.current.state
 def start(self,body):
  if not isinstance(body,dict):raise ValueError('Image request must be an object.')
  name=body.get('engine','turbo')
  if name not in ['turbo','design']:raise ValueError('Choose Image Turbo or Design.')
  with self.lock:
   if any(g.status().get('status') in ACTIVE for g in [self.turbo,self.design]):raise ValueError('Finish or stop the current image before switching engines.')
   self.current=self.design if name=='design' else self.turbo
   result=self.current.start(body);result['engine']=name;return result
 def status(self):
  result=self.current.status();result['engine']='design' if self.current is self.design else 'turbo';return result
 def cancel(self):return self.current.cancel()
 def output(self,name):
  for generator in [self.turbo,self.design]:
   try:return generator.output(name)
   except ValueError:pass
  raise ValueError('Image not found. Reconnect its original image drive.')
 def models(self):
  installation=load_json(self.design.base/'installation.json');ready=load_json(self.design.base/'ready.json');backend=load_json(self.design.base/'backend.json');available=False;error=None
  try:self.design.config();available=True
  except ValueError as e:error=str(e)
  state=installation.get('status','Not installed')
  if available:state='Ready' if ready.get('verifiedByActualGeneration') else 'Installed — awaiting first image verification'
  if self.design.status().get('status') in ACTIVE:state={'running':'Generating','installing':'Preparing automatically','restoring':'Restoring chat'}[self.design.state['status']]
  if self.design.state.get('status')=='error':state='Error';error=self.design.state['message']
  turbo_ready=False;turbo_error=None
  try:self.turbo.config();turbo_ready=True
  except (ValueError,OSError,KeyError) as e:turbo_error=str(e)
  return {'turbo':{'name':'Image Turbo','model':'Z-Image-Turbo','state':'Generating' if self.turbo.state['status']=='running' else 'Ready' if turbo_ready else 'Not installed','canGenerate':turbo_ready,'error':turbo_error},'design':{'name':'Design','model':'MOSS-Image-SFT','state':state,'canGenerate':available,'error':error,'downloadedBytes':installation.get('downloadedBytes',0),'totalBytes':installation.get('totalBytes',0),'verifiedFiles':installation.get('verifiedFiles',0),'requiredFiles':installation.get('requiredFiles',0),'directory':str(self.design.base),'backend':backend}}
 def prepare_design(self,cancelled,progress):
  status=load_json(self.design.base/'installation.json')
  external=status.get('status') in ['Downloading','Installing'] and time.time()-status.get('updated',0)<120
  if not external:self.retry({'approve':True},_automatic=True)
  process=None if external else self.installer
  deadline=time.monotonic()+7200
  while time.monotonic()<deadline:
   if cancelled.is_set():raise InterruptedError('Image cancelled. Setup continues in the background; no image will be generated.')
   info=load_json(self.design.base/'installation.json');progress(info)
   if process is not None:
    code=process.poll()
    if code is not None:
     if code:raise ValueError(info.get('error') or 'The isolated installer failed. Check the local install log.')
     self.design.config();return
   elif info.get('status') not in ['Downloading','Installing']:
    if info.get('status')=='Error':raise ValueError(info.get('error') or 'Setup failed.')
    self.design.config();return
   elif time.time()-info.get('updated',0)>180:raise ValueError('Setup stopped responding. Generate again after checking the model drive and connection.')
   cancelled.wait(.5)
  raise ValueError('Automatic setup exceeded two hours; existing downloads are preserved.')
 def retry(self,body,_automatic=False):
  if body.get('approve') is not True:raise ValueError('Approve resuming the official model download and isolated backend installation first.')
  with self.lock:
   status=load_json(self.design.base/'installation.json')
   if status.get('status') in ['Downloading','Installing'] and time.time()-status.get('updated',0)<120:raise ValueError('Design installation is already active. Its existing progress is preserved.')
   if self.installer and self.installer.poll() is None:raise ValueError('Design installation is already running.')
   if self.current.status().get('status') in ACTIVE and not (_automatic and self.current is self.design and self.design.state['status']=='installing'):raise ValueError('Wait for image generation to finish before repairing Design.')
   configured=load_json(self.design.config_path).get('python','')
   bootstrap=next((p for p in [Path(configured),Path('C:/Python313/python.exe')] if p.is_file()),None)
   if bootstrap is None:raise ValueError('A compatible Python 3.13 runtime is missing. Automatic setup cannot continue on this PC; no interpreter was installed silently.')
   logs=self.design.base/'install.log';logs.parent.mkdir(parents=True,exist_ok=True)
   with logs.open('a',encoding='utf8') as trace:self.installer=subprocess.Popen([str(bootstrap),str(APP_DIR/'assets/design-engine/install.py'),str(self.design.base)],stdin=subprocess.DEVNULL,stdout=trace,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
  return self.models()

def model_route(handler,engines,post=False):
 path=handler.path.split('?',1)[0]
 if path not in ['/imagegen/models','/imagegen/install']:return False
 if not handler.allowed() or post and handler.headers.get('Origin')!='http://'+handler.headers.get('Host',''):handler.json(403,{'error':'Use the local YOEAI image screen.'});return True
 try:
  if post and path=='/imagegen/install':
   n=int(handler.headers.get('Content-Length','-1'))
   if handler.headers.get('Transfer-Encoding') or not 0<n<=1000:raise ValueError('Invalid installation request.')
   body=json.loads(handler.rfile.read(n))
   if not isinstance(body,dict):raise ValueError('Installation request must be an object.')
   handler.json(202,engines.retry(body))
  elif not post and path=='/imagegen/models':handler.json(200,engines.models())
  else:handler.json(405,{'error':'Unsupported image management method.'})
 except (ValueError,TypeError,OSError) as e:handler.json(400,{'error':str(e)})
 return True
