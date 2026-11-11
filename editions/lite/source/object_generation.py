"""Local image-to-3D jobs using the existing chat pause and GPU lock."""
import base64,json,os,re,struct,subprocess,threading,time,uuid
from pathlib import Path
from ph3_image import PH3Generator
from video_inputs import normalise_image
INSTANCE=None;INIT=threading.Lock();ACTIVE=('running','restoring')
class ObjectGenerator(PH3Generator):
 def config(self):
  cfg=json.loads(self.config_path.read_text(encoding='utf-8-sig'))
  if cfg.get('engine')!='triposr' or cfg.get('enabled') is not True:raise ValueError('TripoSR is being prepared; 3D generation is not enabled yet.')
  for key in ('python','worker','backendRoot'):
   cfg[key]=str((self.config_path.parent/cfg[key]).resolve())
  for key in ('python','worker'):
   if not Path(cfg[key]).is_file():raise ValueError('Missing 3D component: '+key)
  root=Path(cfg['backendRoot']);assets=json.loads((root/'model-assets.json').read_text())
  for item in assets['files']:
   file=root/'Models'/item['path']
   if not file.is_file() or file.stat().st_size!=item['bytes']:raise ValueError('TripoSR models need repair; no alternate model was used.')
  if not (root/'Models/Background/models/u2netp/u2netp.onnx').is_file():raise ValueError('The 3D background-removal model is missing.')
  return cfg
 def start(self,body):
  if not isinstance(body,dict):raise ValueError('3D request must be an object.')
  cfg=self.config();source=body.get('sourceJob')
  if source:
   if not isinstance(source,str) or not re.fullmatch('[0-9a-f]{32}',source) or body.get('image'):raise ValueError('Invalid source image reference.')
   source=bytes.fromhex(source).hex()  # Canonical hex IDs cannot introduce path separators.
   file=self.home.parent/'GeneratedImages'/(source+'.png')
   if not file.is_file():raise ValueError('The source image is unavailable. Attach it again.')
   image=normalise_image('data:image/png;base64,'+base64.b64encode(file.read_bytes()).decode())
  else:image=normalise_image(body.get('image'))
  with self.lock:
   if self.state['status'] in ACTIVE:raise ValueError('A 3D object is already being created.')
   self.cancelled.clear();job=uuid.uuid4().hex;self.state={'id':job,'status':'running','message':'Preparing your 3D object...','kind':'object3d','model':'TripoSR'}
   self.worker=threading.Thread(target=self.run,args=(cfg,image,job),daemon=True);self.worker.start()
  return self.status()
 def status(self):
  with self.lock:value=dict(self.state)
  if value.get('id') and value['status']=='running':
   file=self.home/(value['id']+'.log')
   if file.is_file():
    with file.open('rb') as f:f.seek(max(0,file.stat().st_size-8000));lines=f.read().decode('utf8','replace').splitlines()
    stages=[line[len('OBJECT_STAGE '):] for line in lines if line.startswith('OBJECT_STAGE ')]
    if stages:value['message']=stages[-1]
  return value
 def run(self,cfg,image,job):
  self.home.mkdir(parents=True,exist_ok=True);folder=self.home/(job+'.work');folder.mkdir();source=folder/'input.png';source.write_bytes(image);output=folder/'object.glb';request=folder/'request.json';lock=self.gpu_lock;handle=None;paused=False;started=time.monotonic();result={'id':job,'kind':'object3d','model':'TripoSR'}
  try:
   try:handle=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
   except FileExistsError:raise ValueError('An image, video or 3D job already owns the GPU.')
   os.write(handle,str(os.getpid()).encode())
   if self.pause:paused=bool(self.pause())
   request.write_text(json.dumps({'executionAuthorized':True,'backendRoot':cfg['backendRoot'],'image':str(source),'output':str(output)}))
   with (self.home/(job+'.log')).open('w',encoding='utf8') as trace:
    with self.lock:
     if self.cancelled.is_set():raise InterruptedError('3D creation stopped.')
     self.process=subprocess.Popen([cfg['python'],'-u',cfg['worker'],'--request',str(request)],env=dict(os.environ,PYTHONNOUSERSITE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1'),stdin=subprocess.DEVNULL,stdout=trace,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    try:code=self.process.wait(timeout=600)
    except subprocess.TimeoutExpired:self.cancel();raise ValueError('TripoSR timed out; no substitute object was created.')
   if self.cancelled.is_set():raise InterruptedError('3D creation stopped.')
   if code or not output.exists():raise ValueError('TripoSR could not create this object. See its job log; no substitute model was used.')
   with output.open('rb') as f:magic,version,length=struct.unpack('<4sII',f.read(12))
   if magic!=b'glTF' or version!=2 or length!=output.stat().st_size:raise ValueError('The 3D engine produced an invalid GLB.')
   details=json.loads(output.with_suffix('.json').read_text());output.replace(self.home/(job+'.glb'));output.with_suffix('.poster.png').replace(self.home/(job+'.png'))
   result.update(details,status='complete',message='3D object ready.',url='/objectgen/output/'+job,poster='/objectgen/poster/'+job,seconds=round(time.monotonic()-started,1))
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

def instance(app,home,bundle,config):
 global INSTANCE
 with INIT:
  if INSTANCE is None:
   from lite_image_generation import instance as images
   parent=images(app,home,bundle,config);runtime=Path(os.environ.get('YOEAI_ASSISTANT_RUNTIME',str(app)))
   if not getattr(__import__('sys'),'frozen',False) and not (runtime/'ObjectGeneration').is_dir():runtime=Path(__file__).resolve().parents[2]
   INSTANCE=ObjectGenerator(runtime/'ObjectGeneration/config.json',Path(home)/'GeneratedObjects',parent.pause,parent.resume);INSTANCE.gpu_lock=parent.config_path.parent/'generation.lock'
  return INSTANCE

def route(handler,post,app,home,bundle,config):
 path=handler.path.split('?',1)[0]
 if not path.startswith('/objectgen/'):
  if post and INSTANCE and INSTANCE.status()['status'] in ACTIVE and path in ('/context','/v1/chat/completions','/local-models/apply','/imagegen/create','/videogen/create'):
   handler.reply(409,{'error':'3D generation is using the GPU. Wait or press Stop.'});return True
  return False
 if not handler.allowed() or (post and handler.headers.get('Origin')!='http://'+handler.headers.get('Host','')):handler.reply(403,{'error':'Use the local YOEAI interface.'});return True
 try:
  gen=instance(app,home,bundle,config)
  if post:
   n=int(handler.headers.get('Content-Length','0'))
   if handler.headers.get('Transfer-Encoding') or not 0<n<=22*1024**2:raise ValueError('Invalid 3D request size.')
   body=json.loads(handler.rfile.read(n))
   if path=='/objectgen/create':value=gen.start(body)
   elif path=='/objectgen/stop':value=gen.cancel()
   else:raise ValueError('Unknown 3D operation.')
  elif path=='/objectgen/models':
   try:gen.config();value={'ready':True,'model':'TripoSR','format':'glb','vertexColors':True}
   except (ValueError,OSError,KeyError) as error:value={'ready':False,'model':'TripoSR','error':str(error)}
  elif path=='/objectgen/status':value=gen.status()
  elif re.fullmatch('/objectgen/(output|poster)/[0-9a-f]{32}',path):
   poster='/poster/' in path;file=gen.home/(path.rsplit('/',1)[-1]+('.png' if poster else '.glb'))
   if not file.is_file():raise ValueError('Object is unavailable.')
   handler.send_response(200);handler.send_header('Content-Type','image/png' if poster else 'model/gltf-binary');handler.send_header('X-Content-Type-Options','nosniff');handler.send_header('Content-Length',str(file.stat().st_size));handler.send_header('Content-Disposition','inline' if poster else 'attachment; filename="YOEAI-object.glb"');handler.end_headers()
   with file.open('rb') as f:
    while chunk:=f.read(1024**2):handler.wfile.write(chunk)
   return True
  else:raise ValueError('Unknown 3D endpoint.')
  handler.reply(200,value)
 except (ValueError,OSError,TypeError,KeyError) as error:handler.reply(400,{'error':str(error)})
 return True
