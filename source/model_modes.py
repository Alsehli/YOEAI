"""One local inference process shared by chat and every Mini YOE agent.

Mode changes are user initiated and hold the existing shared inference gate.
Only this application's inherited-pipe worker owns the loaded model.
"""
import json,os,threading,time
from pathlib import Path
import runtime
from configuration import APP_DIR,HOME,CONFIG_FILE,read_config

CATALOG=HOME/'model-modes.json'
OWN=HOME/'model-mode-process.json'
LOCK=threading.RLock()
STATE={'phase':'idle','busy':False,'error':None,'detail':''}
ADVANCED=Path(os.environ.get('YOEAI_ADVANCED_MODEL',str(HOME/'Models/Qwen3.8-27B-UD-IQ3_S.gguf')))
BACKEND=APP_DIR/'NativeRuntime/b11784/llama.dll'

def atomic(path,value):
 tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2),encoding='utf8');tmp.replace(path)

def catalog():
 if CATALOG.exists():
  value=json.loads(CATALOG.read_text(encoding='utf8'));current=read_config();mode=current.get('modelMode','fast')
  # Preserve the actual legacy launch configuration on first native migration.
  if current.get('inferenceEngine')!='native' and mode in value and Path(value[mode]['model']).resolve()==Path(current['model']).resolve():
   value[mode]['context']=int(current.get('context',value[mode].get('context',8192)))
   if current.get('projector'):value[mode]['projector']=current['projector']
   atomic(CATALOG,value)
  return value
 c=read_config()
 if c.get('modelMode')=='advanced':raise ValueError('Fast Mode configuration is missing. Restore model-modes.json from your profile backup.')
 value={'selected':'fast','fast':dict(c),'advanced':{'model':str(ADVANCED),'context':8192,'gpuLayers':'all'},'fastStarter':''}
 atomic(CATALOG,value);return value

def model_path(mode,cat=None):
 return Path((cat or catalog())[mode]['model'])

def verify_advanced(path):
 # Full validity and tensor compatibility are additionally checked by llama.cpp
 # on each load. Inspect metadata rather than trusting the filename.
 from gguf_metadata import inspect_model
 info=inspect_model(path)
 meta=info['metadata']
 if meta.get('general.architecture')!='qwen35' or meta.get('qwen35.block_count')!=65 or meta.get('qwen35.embedding_length')!=5120 or meta.get('general.file_type')!=26:
  raise ValueError('Advanced Mode requires the verified Qwen3.8 27B IQ3_S architecture. This GGUF does not match.')
 return info

PROJECTOR_SHA256='cbb841a9ee0636b2ec172f5bb8df2ea8dfeb01e90fe7c6126581d662a0b4e43e'
PROJECTOR_BYTES=927607488
_PROJECTOR_CHECK=None

def advanced_projector(cat,verify=False):
 # A missing optional projector leaves text mode usable; never reuse the 9B projector.
 global _PROJECTOR_CHECK
 path=Path(cat['advanced'].get('projector') or model_path('advanced',cat).parent/'YOEAI-Vision-27B/mmproj-F16.gguf')
 if not path.is_file():return None
 if verify:
  import hashlib
  stat=path.stat();key=(str(path.resolve()),stat.st_size,stat.st_mtime_ns)
  if _PROJECTOR_CHECK!=key:
   if stat.st_size!=PROJECTOR_BYTES:raise ValueError('The 27B vision projector has an unexpected size. Text model was not changed.')
   sha=hashlib.sha256()
   with path.open('rb') as stream:
    for block in iter(lambda:stream.read(8*1024*1024),b''):sha.update(block)
   if sha.hexdigest()!=PROJECTOR_SHA256:raise ValueError('The 27B vision projector failed its publisher checksum. Nothing was loaded.')
   _PROJECTOR_CHECK=key
 return path

# Native model lifecycle. The UI HTTP transport remains unchanged.
from native_ai.manager import INSTANCE as NATIVE

def request_json(path):
 if path=='/props':return {'model_path':NATIVE.state.get('model'),'default_generation_settings':{'n_ctx':NATIVE.state.get('context')}}
 if path=='/slots':return [{'is_processing':NATIVE.state['busy']}]
 raise ValueError('Unsupported native metadata operation.')
def actual():return NATIVE.state.get('model','')if NATIVE.state['loaded']else''
def reconcile_running():
 if not NATIVE.state['loaded']:raise ValueError('The selected native model is not loaded.')
 return read_config().get('modelMode',catalog().get('selected','fast'))
def require_advanced_vision(c):
 if not NATIVE.state.get('vision'):raise ValueError('The selected native model has no loaded vision projector.')
 return Path(c.get('projector',''))
def set_state(**values):
 with LOCK:STATE.update(values)
def status():
 cat=catalog();c=read_config();native=dict(NATIVE.state)
 with LOCK:s=dict(STATE)
 s.update(selected=cat.get('selected','fast'),active=c.get('modelMode','fast')if native['loaded']else None,online=native['loaded'],context=c.get('context'),model=c['model'],name='Qwen3.8 27B · UD-IQ3_S'if c.get('modelMode')=='advanced'else'Qwen3.5 9B · Q6_K',vision=bool(native.get('vision')),advancedAvailable=model_path('advanced',cat).is_file()and BACKEND.is_file(),advancedPath=str(model_path('advanced',cat)),backend='Bundled native libllama · private IPC',shared=True,native=True,progress=native.get('progress',0),gpuLayers=native.get('gpuLayers'),log=str(getattr(NATIVE,'log_path','')))
 if native.get('phase')=='loading':s['phase']='loading';s['detail']='Loading selected native model: '+str(round(native.get('progress',0)*100))+'%'
 s['customAvailable']='custom' in cat and Path(cat['custom'].get('model','')).is_file()
 if c.get('customModel') or c.get('modelMode')=='custom':s['name']=Path(c['model']).stem
 return s
def media_busy():
 import image_generation_adapter as images,video_generation_adapter as videos
 return (images.INSTANCE is not None and images.INSTANCE.status().get('status')in('running','restoring'))or(videos.INSTANCE is not None and videos.INSTANCE.state.get('status')in('running','restoring'))
def assert_idle(allow_media=False):
 if NATIVE.state['busy']:raise ValueError('Finish or stop the active native generation first.')
 if not allow_media and media_busy():raise ValueError('Wait for image/video generation to finish.')
def stop_current():
 if NATIVE.state['busy']:raise ValueError('The native model is active; stop the current request first.')
 if NATIVE.worker:list(NATIVE.request('unload'))
def load_native(mode,cat):
 from native_ai.resources import plans
 selected=cat[mode];path=model_path(mode,cat)
 if mode=='advanced':verify_advanced(path)
 context=int(selected.get('context',8192 if mode=='advanced'else 16384));projector=advanced_projector(cat,verify=True)if mode=='advanced'else Path(selected.get('projector',''))
 if not projector or not projector.is_file():projector=None
 profile=plans(path,context,projector);errors=[]
 for layers in profile['gpuLayerAttempts']:
  set_state(phase='loading',detail='Loading the selected GGUF through bundled native libraries.',error=None)
  try:
   # The worker owns its exact bundled runtime; no model-server process is adopted.
   NATIVE.start();list(NATIVE.request('load',runtime=str(NATIVE.runtime),model=str(path),context=context,layers=layers,projector=str(projector)if projector else None));break
  except Exception as ex:
   errors.append(str(ex))
   # A faulted worker cannot retain a usable model; recreate it before retrying.
   NATIVE.close()
   if not any(x in str(ex).lower()for x in ('alloc','memory','cuda','worker closed')):raise
 else:raise ValueError('The selected model did not initialize safely. '+errors[-1])
 c=read_config();c.update(model=str(path),projector=str(projector)if projector else'',context=context,modelMode=mode,externalBackend=False,inferenceEngine='native');atomic(CONFIG_FILE,c)
 NATIVE.state['resourcePlan']=profile
 return c
def transition(mode,context=None):
 if mode not in('fast','advanced','custom'):raise ValueError('Choose Fast, Advanced or a configured local model.')
 cat=catalog();assert_idle();old=read_config().get('modelMode','fast')
 if NATIVE.state['loaded']and old==mode and context is None:return
 if context is not None:
  if type(context)is not int or context not in(4096,8192,16384):raise ValueError('Unsupported context length.')
  cat[mode]['context']=context
 set_state(phase='unloading',error=None,detail='Releasing the previous native model.')
 stop_current();load_native(mode,cat);cat['selected']=mode;atomic(CATALOG,cat);set_state(phase='ready',error=None,detail='Native model ready. All workspaces share this instance.')
def switch(mode):
 from mini_agents import GATE
 if mode not in('fast','advanced','custom'):raise ValueError('Choose Fast, Advanced or a configured local model.')
 with LOCK:
  if STATE['busy']:raise ValueError('A native model is already loading.')
  if not GATE.acquire(blocking=False):raise ValueError('Finish or stop the current task before switching models.')
  try:assert_idle()
  except Exception:GATE.release();raise
  STATE.update(busy=True,target=mode,phase='checking',error=None)
 def work():
  try:transition(mode)
  except Exception as ex:set_state(phase='error',error=str(ex),detail='Native loading failed. No different model was substituted.')
  finally:set_state(busy=False);GATE.release()
 threading.Thread(target=work,daemon=True,name='YOEAI-native-switch').start();return {'accepted':True}
def ensure_selected():
 if NATIVE.state['loaded']:return
 cat=catalog();load_native(cat.get('selected','fast'),cat);set_state(phase='ready',error=None,detail='Native model ready.')
def change_context(context,confirmed):
 if confirmed is not True:raise ValueError('Confirm reloading the shared native model.')
 from mini_agents import GATE
 if not GATE.acquire(blocking=False):raise ValueError('Finish the current task before changing context.')
 try:transition(read_config().get('modelMode','fast'),context);return {'status':'ok','context':context}
 finally:GATE.release()
def pause_for_media():
 assert_idle(allow_media=True)
 if not NATIVE.state['loaded']:return False
 stop_current();return True

def route(handler,post=False):
 if handler.path not in('/models/state','/models/switch'):return False
 if not handler.allowed()or(post and handler.headers.get('Origin')!='http://'+handler.headers.get('Host','')):handler.json(403,{'error':'Use the local YOEAI interface.'});return True
 try:
  if not post and handler.path=='/models/state':value=status()
  elif post and handler.path=='/models/switch':
   n=int(handler.headers.get('Content-Length','0'))
   if handler.headers.get('Transfer-Encoding')or not 0<n<=256:raise ValueError('Invalid model request.')
   value=switch(json.loads(handler.rfile.read(n)).get('mode'))
  else:raise ValueError('Unsupported model operation.')
  handler.json(200,value)
 except Exception as ex:handler.json(409,{'error':str(ex)})
 return True
