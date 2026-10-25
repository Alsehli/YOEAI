"""One local inference process shared by chat and every Mini YOE agent.

Mode changes are user initiated, hold the existing shared inference gate, and
never stop an engine without a matching executable, creation time and model.
"""
import json,os,socket,subprocess,threading,time,urllib.request
from pathlib import Path
import runtime
from configuration import APP_DIR,HOME,CONFIG_FILE,read_config

CATALOG=HOME/'model-modes.json'
OWN=HOME/'model-mode-process.json'
LOCK=threading.RLock()
STATE={'phase':'idle','busy':False,'error':None,'detail':''}
ADVANCED=Path('E:/Qwen3.8-27B-UD-IQ3_S.gguf')
BACKEND=APP_DIR/'ModelBackends/b11784/llama-server.exe'

def atomic(path,value):
 tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2),encoding='utf8');tmp.replace(path)

def catalog():
 if CATALOG.exists():return json.loads(CATALOG.read_text(encoding='utf8'))
 c=read_config()
 if c.get('modelMode')=='advanced':raise ValueError('Fast Mode configuration is missing. Restore model-modes.json from your profile backup.')
 value={'selected':'fast','fast':dict(c),'advanced':{'model':str(ADVANCED),'context':8192,'gpuLayers':'all'},'fastStarter':os.environ.get('YOEAI_ENGINE_STARTER','')}
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

def require_advanced_vision(c):
 projector=advanced_projector(catalog(),verify=True)
 if not projector or Path(c.get('projector') or '').resolve()!=projector.resolve():raise ValueError('The matching 27B vision projector is not loaded. Select Advanced again to load it.')
 owned=running_owned()
 if owned['mode']!='advanced' or Path(projector_argument(owned['args']) or '').resolve()!=projector.resolve():raise ValueError('The active backend has no verified 27B vision projector. Reload Advanced Mode.')
 return projector

def projector_argument(args):
 return next((args[i+1] for i,a in enumerate(args[:-1]) if a in ('--mmproj','-mm')),'')

def request_json(path):
 with runtime.HTTP.open('http://127.0.0.1:'+str(read_config()['apiPort'])+path,timeout=3) as r:return json.load(r)

def actual():
 try:
  data=request_json('/props');return data.get('model_path') or data.get('model') or ''
 except Exception:return ''

def running_owned(cat=None):
 """Identify the listener independently of AppData (MSIX may virtualise it).

 A matching HTTP model name alone never grants ownership: require the listening
 PID, exact approved executable and its actual model/port command arguments.
 """
 import psutil
 cat=cat or catalog();c=read_config();props=request_json('/props')
 path=Path(props.get('model_path') or '')
 mode=next((x for x in ('fast','advanced') if path.resolve()==model_path(x,cat).resolve()),None)
 if mode is None:raise ValueError('The running model is not one of this app’s configured models. No process was adopted or stopped.')
 permitted={BACKEND.resolve()} if mode=='advanced' else {(APP_DIR/'backend/llama-server.exe').resolve()}
 if mode=='fast' and Path(cat.get('fastStarter','')).resolve()==Path('C:/AI/llama.cpp/start-deepseek.ps1').resolve():permitted.add(Path('C:/AI/llama.cpp/llama-server.exe').resolve())
 listeners={x.pid for x in psutil.net_connections(kind='tcp4') if x.status==psutil.CONN_LISTEN and x.laddr.port==int(c['apiPort']) and x.laddr.ip=='127.0.0.1'}
 if len(listeners)!=1:raise ValueError('Cannot uniquely verify the local model listener. Nothing was stopped.')
 pid=listeners.pop();process=psutil.Process(pid);identity=runtime.identity(pid)
 if not identity or Path(identity['exe']).resolve() not in permitted:raise ValueError('This model listener belongs to another installation. Nothing was stopped.')
 args=process.cmdline()
 def arg(names):
  return next((args[i+1] for i,x in enumerate(args[:-1]) if x in names),None)
 if Path(arg(('-m','--model')) or '').resolve()!=path.resolve() or arg(('--port',))!=str(c['apiPort']) or arg(('--host',))!='127.0.0.1':raise ValueError('Model process arguments did not match the local service. Nothing was stopped.')
 context=int(props.get('default_generation_settings',{}).get('n_ctx') or arg(('-c','--ctx-size')) or c['context'])
 return {'pid':pid,'identity':identity,'model':str(path),'port':int(c['apiPort']),'context':context,'gpuLayers':arg(('-ngl','--gpu-layers')) or 'all','args':args,'mode':mode}

def reconcile_running():
 """Reconnect to a verified already-running model; never load another copy."""
 cat=catalog();found=running_owned(cat);mode=found.pop('mode');c=read_config()
 # Keep this profile's ports/history and its original Fast configuration.
 if mode=='advanced':
  c.update(model=found['model'],projector=projector_argument(found['args']),context=found['context'],modelMode=mode,externalBackend=True)
 else:
  c.update(model=found['model'],projector=cat['fast']['projector'],context=found['context'],modelMode=mode,externalBackend=cat['fast'].get('externalBackend',False))
 previous=json.loads(OWN.read_text(encoding='utf8')) if OWN.exists() else {}
 if previous.get('identity')==found['identity'] and previous.get('log'):found['log']=previous['log']
 atomic(OWN,found);atomic(CONFIG_FILE,c);cat['selected']=mode;atomic(CATALOG,cat)
 set_state(phase='ready',error=None,detail='Connected to the verified running model. No second model was loaded.')
 return mode

def set_state(**values):
 with LOCK:STATE.update(values)

def status():
 cat=catalog();c=read_config();online=runtime.healthy(c['apiPort']);mode=c.get('modelMode','fast')
 live=actual() if online and not STATE['busy'] else ''
 with LOCK:
  if online and not STATE['busy'] and (STATE.get('error') and STATE.get('target') in (None,mode) or live and Path(live).resolve()!=Path(c['model']).resolve()):
   try:reconcile_running();cat=catalog();c=read_config();mode=c.get('modelMode','fast')
   except Exception as ex:set_state(error=str(ex),phase='error')
 with LOCK:s=dict(STATE)
 s.update(selected=cat['selected'],active=mode if online else None,online=online,context=c.get('context'),model=c['model'],name='Qwen3.8 27B · UD-IQ3_S' if mode=='advanced' else 'Qwen3.5 9B · Q6_K',vision=online and bool(c.get('projector')),advancedAvailable=model_path('advanced',cat).is_file() and BACKEND.is_file(),advancedPath=str(model_path('advanced',cat)),backend=str(BACKEND) if mode=='advanced' else 'Existing Fast backend',shared=True)
 if OWN.exists() and (mode=='advanced' or s['busy'] and s['phase']=='loading'):
  owned=json.loads(OWN.read_text(encoding='utf8'))
  s['gpuLayers']=owned.get('gpuLayers');s['log']=owned.get('log')
  if s['busy'] and owned.get('log'):
   try:s['detail']=Path(owned['log']).read_text(encoding='utf8',errors='replace')[-2500:]
   except OSError:pass
 return s

def media_busy():
 import image_generation_adapter as images,video_generation_adapter as videos
 return (images.INSTANCE is not None and images.INSTANCE.status().get('status') in ('running','restoring')) or (videos.INSTANCE is not None and videos.INSTANCE.state.get('status') in ('running','restoring'))

def assert_idle(allow_media=False):
 import interactive_voice
 if interactive_voice.INSTANCE is not None:interactive_voice.INSTANCE.release_idle()
 import speech_input
 voice=speech_input.INSTANCE
 if voice is not None and hasattr(voice,'release_idle'):voice.release_idle()
 if not allow_media and media_busy():raise ValueError('Wait for image/video creation and model restoration to finish.')
 try:
  for slot in request_json('/slots'):
   if slot.get('is_processing'):raise ValueError('The shared model is generating. Stop or finish the current task first.')
 except urllib.error.HTTPError as ex:
  if ex.code!=503:raise
 except urllib.error.URLError:pass

def stop_current():
 c=read_config()
 saved=json.loads(OWN.read_text(encoding='utf8')) if OWN.exists() else None
 if not saved or runtime.identity(saved['pid']) is None:
  with socket.socket() as probe:
   if probe.connect_ex(('127.0.0.1',c['apiPort']))!=0:return
 if OWN.exists():
  s=json.loads(OWN.read_text(encoding='utf8'));current=runtime.identity(s['pid'])
  if current and current==s['identity'] and Path(s['model']).resolve()==Path(c['model']).resolve() and int(s['port'])==int(c['apiPort']):
   exe=Path(s['identity']['exe'])
   permitted={BACKEND.resolve(),(APP_DIR/'backend/llama-server.exe').resolve()}
   if Path(catalog().get('fastStarter','')).resolve()==Path('C:/AI/llama.cpp/start-deepseek.ps1').resolve():permitted.add(Path('C:/AI/llama.cpp/llama-server.exe').resolve())
   if exe.resolve() not in permitted:raise ValueError('The saved engine belongs to another installation.')
   result=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(APP_DIR/'stop_model.ps1'),'-PidToStop',str(s['pid']),'-ExpectedExe',str(exe),'-Created',str(current['created'])],capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=35)
   if result.returncode:raise ValueError('The model could not close safely: '+result.stdout[-600:]+result.stderr[-600:])
   return
 if c.get('externalBackend'):
  approved=Path('C:/AI/llama.cpp/start-deepseek.ps1')
  cat=catalog()
  if Path(cat.get('fastStarter','')).resolve()!=approved.resolve():raise ValueError('This external engine has no approved ownership controller.')
  state=json.loads((approved.parent/'server-state.json').read_text(encoding='utf-8-sig'))
  if Path(state['model']).resolve()!=Path(c['model']).resolve() or int(state['port'])!=int(c['apiPort']):raise ValueError('The active external engine differs from this application. Nothing was stopped.')
  result=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(approved.parent/'stop-deepseek.ps1')],capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=40)
  if result.returncode:raise ValueError(result.stdout[-500:]+result.stderr[-500:])
 else:runtime.stop_engine()
 if runtime.healthy(c['apiPort']):raise ValueError('The previous engine is still running. No second model was loaded.')

def launch_fast(cat):
 c={**read_config(),**cat['fast'],'modelMode':'fast'};atomic(CONFIG_FILE,c)
 starter=Path(cat.get('fastStarter',''))
 if c.get('externalBackend'):
  if starter.resolve()!=Path('C:/AI/llama.cpp/start-deepseek.ps1').resolve() or not starter.is_file():raise ValueError('The saved Fast Mode launcher is unavailable.')
  log=HOME/'Logs/fast-mode-start.log';log.parent.mkdir(exist_ok=True)
  with log.open('w',encoding='utf8') as out:
   p=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(starter),'-Context',str(c['context']),'-Port',str(c['apiPort'])],stdout=out,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW,timeout=240)
  if p.returncode:raise ValueError('Fast Mode failed to load: '+log.read_text(encoding='utf8',errors='replace')[-1200:])
 else:runtime.ensure_engine()

def launch_advanced(cat):
 path=model_path('advanced',cat);verify_advanced(path)
 if not BACKEND.is_file():raise ValueError('The Advanced CUDA backend is missing. No model was downloaded.')
 projector=advanced_projector(cat,verify=True)
 base=read_config();context=int(cat['advanced'].get('context',8192))
 if context not in (4096,8192):raise ValueError('Advanced Mode supports 4K or 8K context in this 16GB profile.')
 # Retry the SAME file only, with fewer GPU layers; never silently change model.
 for layers in (cat['advanced'].get('gpuLayers','all'),'56','48'):
  if runtime.healthy(base['apiPort']):raise ValueError('The previous model is still running.')
  with socket.socket() as probe:
   if probe.connect_ex(('127.0.0.1',base['apiPort']))==0:raise ValueError('The inference port is occupied. No additional model was loaded.')
  set_state(phase='loading',detail=f'Loading the 27B model: {context:,} context, {layers} GPU layers. Waiting for llama.cpp readiness.')
  logs=HOME/'Logs';logs.mkdir(exist_ok=True);log=logs/f'advanced-{time.time_ns()}.log'
  args=[str(BACKEND),'-m',str(path),'--host','127.0.0.1','--port',str(base['apiPort']),'--alias','deepseek-local','-ngl',str(layers),'-c',str(context),'-np','1','-t','6','-tb','6','-b','256','-ub','128','-fa','on','-ctk','q8_0','-ctv','q8_0','--fit','on','--fit-target','1024','--jinja','--reasoning','off','--metrics','--slots','-lv','4']
  if projector:args.extend(['--mmproj',str(projector),'--image-max-tokens','1024'])
  startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
  with log.open('w',encoding='utf8') as out:
   process=subprocess.Popen(args,cwd=str(BACKEND.parent),stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,startupinfo=startup,creationflags=subprocess.CREATE_NEW_CONSOLE|subprocess.CREATE_NEW_PROCESS_GROUP)
  owned={'pid':process.pid,'identity':runtime.identity(process.pid),'model':str(path),'port':base['apiPort'],'context':context,'gpuLayers':str(layers),'log':str(log),'args':args};atomic(OWN,owned)
  deadline=time.monotonic()+240
  while time.monotonic()<deadline:
   if process.poll() is not None:break
   if runtime.healthy(base['apiPort']):
    c={**base,'model':str(path),'projector':str(projector) if projector else '','context':context,'externalBackend':True,'modelMode':'advanced'};atomic(CONFIG_FILE,c)
    cat['advanced'].update(context=context,gpuLayers=str(layers));return
   time.sleep(.35)
  if process.poll() is None:
   # Set the provisional identity so stop_current can verify and close this
   # exact process after a timeout; restore config on failure in transition.
   atomic(CONFIG_FILE,{**base,'model':str(path),'modelMode':'advanced','externalBackend':True});stop_current();atomic(CONFIG_FILE,base)
   raise ValueError('Advanced loading timed out; the owned process was closed safely. '+str(log))
  message=log.read_text(encoding='utf8',errors='replace')[-5000:]
  if not any(word in message.lower() for word in ('out of memory','cuda error','failed to allocate','insufficient memory')):raise ValueError('Advanced model loading failed. '+message[-1800:])
  set_state(detail='Insufficient GPU memory; retrying the same 27B file with fewer GPU layers.')
 raise ValueError('The 27B model did not fit the tested GPU profiles. Close other GPU applications and retry. No other model was substituted.')

def transition(mode,context=None):
 cat=catalog()
 if mode not in ('fast','advanced'):raise ValueError('Choose Fast or Advanced Mode.')
 if mode=='advanced':verify_advanced(model_path(mode,cat))
 if runtime.healthy(read_config()['apiPort']):
  running=reconcile_running();cat=catalog()
  if running==mode and context is None and (mode!='advanced' or Path(advanced_projector(cat) or '').resolve()==Path(read_config().get('projector') or '').resolve()):return
 original=read_config();old=original.get('modelMode','fast')
 assert_idle()
 if old=='fast':cat['fast']=dict(original)
 if context is not None:
  if context not in ((4096,8192) if mode=='advanced' else (4096,8192,16384)):raise ValueError('Unsupported context for this model mode.')
  cat[mode]['context']=context
 set_state(phase='unloading',detail='Closing the previous model before loading the selected model.',error=None)
 stop_current()
 try:
  if mode=='advanced':launch_advanced(cat)
  else:launch_fast(cat)
  if not runtime.healthy(read_config()['apiPort']):raise ValueError('The selected engine did not become ready.')
  cat['selected']=mode;atomic(CATALOG,cat);set_state(phase='ready',error=None,detail='Model ready. All conversations and agents share this instance.')
 except Exception:
  # Keep selection/config truthful. Do not launch another model automatically.
  atomic(CONFIG_FILE,original);raise

def switch(mode):
 from mini_agents import GATE
 if mode not in ('fast','advanced'):raise ValueError('Choose Fast or Advanced Mode.')
 with LOCK:
  if STATE['busy']:raise ValueError('A model is already loading.')
  if not GATE.acquire(blocking=False):raise ValueError('Finish or stop the active chat/agent task before switching models.')
  try:assert_idle()
  except Exception:GATE.release();raise
  STATE.update(busy=True,target=mode,phase='checking',error=None,detail='Checking the selected local model.')
 def work():
  try:transition(mode)
  except Exception as ex:set_state(phase='error',error=str(ex),detail='Loading failed. No different model was substituted; choose a mode to retry.')
  finally:set_state(busy=False);GATE.release()
 threading.Thread(target=work,daemon=True,name='YOEAI-model-switch').start()
 return {'accepted':True}

def ensure_selected():
 cat=catalog();mode=cat.get('selected','fast');c=read_config()
 if runtime.healthy(c['apiPort']):
  reconcile_running();return
 if mode=='advanced':launch_advanced(cat)
 else:launch_fast(cat)
 set_state(phase='ready',error=None,detail='Selected model restored.')

def change_context(context,confirmed):
 if confirmed is not True:raise ValueError('Confirm the shared engine restart.')
 with LOCK:
  if STATE['busy']:raise ValueError('Wait for model loading to finish.')
  STATE['busy']=True
 try:transition(read_config().get('modelMode','fast'),context);return {'status':'ok','context':read_config()['context']}
 finally:set_state(busy=False)

def pause_for_media():
 with LOCK:
  if not runtime.healthy(read_config()['apiPort']):return False
  assert_idle(allow_media=True)
  # Verify the real listener/executable/model before pausing a stale saved mode.
  # Reconciliation preserves the actual context so media restores the same engine.
  reconcile_running();stop_current();return True

def route(handler,post=False):
 if handler.path not in ('/models/state','/models/switch'):return False
 if not handler.allowed() or (post and handler.headers.get('Origin')!='http://'+handler.headers.get('Host','')):handler.json(403,{'error':'Use the local YOEAI interface.'});return True
 try:
  if not post and handler.path=='/models/state':value=status()
  elif post and handler.path=='/models/switch':
   n=int(handler.headers.get('Content-Length','0'))
   if handler.headers.get('Transfer-Encoding') or not 0<n<=256:raise ValueError('Invalid model request.')
   body=json.loads(handler.rfile.read(n));value=switch(body.get('mode'))
  else:raise ValueError('Unsupported model operation.')
  handler.json(200,value)
 except Exception as ex:handler.json(409,{'error':str(ex)})
 return True
