"""Lite Image Turbo: one existing local model set, exclusive GPU execution."""
import json,os,threading,subprocess
from pathlib import Path
from image_generation import ImageGenerator,handle_request
INSTANCE=None;INIT=threading.Lock()
ROUTER=None

class ImageRouter:
 def __init__(self,turbo,runtime):
  from ph3_image import PH3Generator
  self.turbo=turbo;self.ph3=PH3Generator(runtime/"ImageGeneration/ph3-config.json",turbo.home,turbo.pause,turbo.resume);self.ph3.gpu_lock=turbo.config_path.parent/'generation.lock';self.active=turbo;self.lock=threading.RLock()
 def start(self,body):
  if not isinstance(body,dict):raise ValueError('Image request must be an object.')
  with self.lock:
   if self.active.status()["status"] in ("running","restoring"):raise ValueError("An image is already being created.")
   engine=body.get("engine","turbo")
   if engine not in ("turbo","ph3"):raise ValueError("Unknown image model; no alternate model was used.")
   selected=self.ph3 if engine=="ph3" else self.turbo
   result=selected.start(body);self.active=selected;return result
 def status(self):return self.active.status()
 def cancel(self):return self.active.cancel()
 def output(self,name):return self.turbo.output(name)

def router(app,home,bundle,config):
 global ROUTER
 if ROUTER is None:
  runtime=Path(os.environ.get("YOEAI_ASSISTANT_RUNTIME",str(app)))
  if not getattr(__import__("sys"),"frozen",False) and not (runtime/"ImageGeneration").is_dir():runtime=Path(__file__).resolve().parents[2]
  ROUTER=ImageRouter(instance(app,home,bundle,config),runtime)
 return ROUTER

class LiteGenerator(ImageGenerator):
 def config(self):
  c=super().config();c=dict(c);args=list(c.get('arguments',[]))
  # The Normal add-on may request 12 GiB; never inherit that budget on Lite.
  try:
   raw=subprocess.check_output(['nvidia-smi','--query-gpu=memory.total','--format=csv,noheader,nounits'],text=True,timeout=5,creationflags=subprocess.CREATE_NO_WINDOW)
   total=float(raw.splitlines()[0]);budget=max(1,min(6,(total/1024)-1.5))
  except Exception:budget=5
  if '--max-vram' in args:
   at=args.index('--max-vram');args[at+1]='cuda0='+str(round(budget,1))
  else:args+=['--max-vram','cuda0='+str(round(budget,1))]
  c['arguments']=args;return c

def instance(app,home,bundle,config):
 global INSTANCE
 with INIT:
  if INSTANCE is not None:return INSTANCE
  import lite_native
  from lite_agents_bridge import initialize
  initialize(home,bundle,config)
  from mini_agents import GATE
  state={'restore':False,'held':False}
  def pause():
   if not GATE.acquire(blocking=False):raise ValueError('Finish the active chat or agent task before creating an image.')
   state['held']=True
   try:
    if lite_native.INSTANCE.state.get('busy'):raise ValueError('Stop the active AI reply first.')
    state['restore']=lite_native.healthy()
    if state['restore']:lite_native.stop()
    # Always call resume, including when chat was initially unloaded, to release the gate.
    return True
   except Exception:
    GATE.release();state['held']=False;raise
  def resume(restore=True):
   try:
    if restore and state['restore']:lite_native.start(app,home,config)
   finally:
    state['restore']=False
    if state['held']:GATE.release();state['held']=False
  candidates=[Path(home)/'ImageGeneration/config.json',Path(app)/'ImageGeneration/config.json']
  if os.environ.get('YOEAI_IMAGE_CONFIG'):candidates.insert(0,Path(os.environ['YOEAI_IMAGE_CONFIG']))
  candidates.append(Path('F:/YOEAI-Image-Generation/config.json'))
  chosen=next((p for p in candidates if p.is_file()),candidates[0])
  INSTANCE=LiteGenerator(chosen,Path(home)/'GeneratedImages',pause,resume,max_size=768)
  return INSTANCE

def route(handler,post,app,home,bundle,config):
 if handler.path.startswith('/imagegen/'):
  global INSTANCE,ROUTER
  if handler.path=='/imagegen/configure' and post:
   if not handler.allowed() or handler.headers.get('Origin')!='http://'+handler.headers.get('Host',''):
    handler.reply(403,{'error':'Use the local YOEAI settings'});return True
   try:
    n=int(handler.headers.get('Content-Length','0'))
    if handler.headers.get('Transfer-Encoding') or not 0<n<=4096:raise ValueError('Invalid configuration request')
    body=json.loads(handler.rfile.read(n))
    if not isinstance(body,dict):raise ValueError('Invalid image model folder request')
    from security_paths import user_local_path
    folder=user_local_path(body.get('folder','')).resolve()
    if not folder.is_dir():raise ValueError('Choose the folder containing the image models')
    if INSTANCE and (ROUTER.status() if ROUTER else INSTANCE.status()).get('status') in ('running','restoring'):raise ValueError('Stop image generation before changing its model folder')
    files={k:folder/name for k,name in {'diffusion':'z_image_turbo-Q4_K.gguf','encoder':'Qwen3-4B-Instruct-2507-Q4_K_M.gguf','vae':'ae.safetensors'}.items()}
    for key,file in files.items():
     if not file.is_file():raise ValueError('Missing image component: '+file.name)
     if key!='vae':
      with file.open('rb') as stream:
       if stream.read(4)!=b'GGUF':raise ValueError('Invalid GGUF component: '+file.name)
    runtimes=[Path(app)/'ImageGeneration/Runtime/CUDA/sd-cli.exe',Path('F:/YOEAI-Image-Generation/Runtime/CUDA/sd-cli.exe')]
    exe=next((x for x in runtimes if x.is_file()),None)
    if exe is None:raise ValueError('Image runtime missing; install the YOEAI image tools')
    target=Path(home)/'ImageGeneration/config.json';target.parent.mkdir(parents=True,exist_ok=True)
    value={k:str(file) for k,file in files.items()};value.update(executable=str(exe),arguments=['--backend','cuda0','--max-vram','cuda0=5','--flash-attn','off,diffusion=on','-t','6'])
    temp=target.with_suffix('.tmp');temp.write_text(json.dumps(value,indent=2),encoding='utf8');temp.replace(target)
    if ROUTER:ROUTER.ph3.shutdown()
    if INSTANCE:INSTANCE.shutdown()
    INSTANCE=None;ROUTER=None;handler.reply(200,{'saved':True});return True
   except (ValueError,TypeError,AttributeError,OSError) as e:handler.reply(400,{'error':str(e)});return True
  gen=instance(app,home,bundle,config)
  if handler.path=='/imagegen/models' and not post:
   if not handler.allowed():handler.reply(403,{'error':'Use the local YOEAI interface'});return True
   try:gen.config();status={'state':'Ready','canGenerate':True}
   except (ValueError,OSError) as e:status={'state':'Setup needed','canGenerate':False,'error':str(e)}
   ph3={'state':'Setup needed','canGenerate':False}
   try:router(app,home,bundle,config).ph3.config();ph3={'state':'Ready','canGenerate':True}
   except (ValueError,OSError,KeyError) as e:ph3['error']=str(e)
   ph3.update(model='P-H3-Image',sizes=[2048,2912],attribution='Powered by MiniMax H3',licenseUrl='https://huggingface.co/PrunaAI/P-H3-Image-Comfy/blob/main/LICENSE')
   handler.reply(200,{'turbo':status,'ph3':ph3});return True
  return handle_request(handler,router(app,home,bundle,config),post)
 if post and INSTANCE and handler.path in ('/context','/v1/chat/completions','/local-models/apply') and (ROUTER.status() if ROUTER else INSTANCE.status()).get('status') in ('running','restoring'):
  handler.reply(409,{'error':'Image Turbo is using the GPU. Wait or press Stop.'});return True
 return False

def shutdown():
 if ROUTER:ROUTER.ph3.shutdown()
 if INSTANCE:INSTANCE.shutdown()
