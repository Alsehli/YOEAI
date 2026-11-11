from candidate_environment import initialize as initialize_candidate
initialize_candidate()
from native_ai.client import Connection as NativeConnection
"""YOEAI Lite: local text/image edition using system Microsoft Edge."""
import mimetypes
from urllib.parse import unquote,urlsplit
import argparse,ctypes,hashlib,http.client,json,os,shutil,socket,subprocess,sys,threading,time,urllib.request,uuid,zipfile
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
if '--assistant-tool-worker' in sys.argv:
 from intelligence.worker import main as assistant_worker
 assistant_worker(sys.argv[-1]);raise SystemExit(0)
if '--windows-tool-worker' in sys.argv:
 from windows_tools import worker_main
 worker_main();raise SystemExit(0)
APP=Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(__file__).parent
from native_update import data_home
DATA=data_home()
DATA.mkdir(parents=True,exist_ok=True)
BUNDLE=Path(getattr(sys,'_MEIPASS',APP))
import lite_read_aloud
lite_read_aloud.configure(APP,DATA)
CONFIG=DATA/'profile.json';STATE=DATA/'engine-state.json'
UI_STATE=DATA/'ui-state.json'
HTTP=urllib.request.build_opener(urllib.request.ProxyHandler({}))
LOCK=threading.RLock()
def sha(path):
 with open(path,'rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def config():
 return json.loads(CONFIG.read_text(encoding="utf-8-sig")) if CONFIG.exists() else dict(model=str(APP/'Models/DeepSeek-V4-Pro-Qwen3.5-9B-MTP-Q4_K_M.gguf'),projector=str(APP/'Models/mmproj-F32.gguf'),inferenceEngine='native',apiPort=8086,uiPort=8087,context=16384,gpuLayers=99)
def identity(pid):
 from ctypes import wintypes
 k=ctypes.WinDLL('kernel32');k.OpenProcess.restype=wintypes.HANDLE;k.QueryFullProcessImageNameW.argtypes=[wintypes.HANDLE,wintypes.DWORD,wintypes.LPWSTR,ctypes.POINTER(wintypes.DWORD)];k.GetProcessTimes.argtypes=[wintypes.HANDLE,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p];k.CloseHandle.argtypes=[wintypes.HANDLE]
 h=k.OpenProcess(0x1000,False,pid)
 if not h:return None
 try:
  name=ctypes.create_unicode_buffer(32768);length=wintypes.DWORD(32768);times=[ctypes.c_ulonglong() for _ in range(4)]
  if not k.QueryFullProcessImageNameW(h,0,name,ctypes.byref(length)) or not k.GetProcessTimes(h,*[ctypes.byref(t) for t in times]):return None
  return dict(exe=str(Path(name.value).resolve()),created=times[0].value)
 finally:k.CloseHandle(h)
def healthy():
 import lite_native
 return lite_native.healthy()
def stop_engine():
 import lite_native
 return lite_native.stop()

def stop():
 stop_engine()
 if UI_STATE.exists():
  ui=json.loads(UI_STATE.read_text())
  if identity(ui['pid'])!=ui['identity']:return
  payload=json.dumps({'token':ui['token']}).encode()
  try:HTTP.open(urllib.request.Request(f"http://127.0.0.1:{config()['uiPort']}/shutdown",payload,{'Content-Type':'application/json'}),timeout=5).close()
  except urllib.error.URLError:pass
def start():
 import lite_native
 from builtin_vision import activate
 return activate(APP,DATA,config,explicit=True)
def native_status():
 from native_ai.manager import INSTANCE
 state=INSTANCE.state
 return {'status':'ok'if healthy()else'offline','changing':state.get('phase')=='loading','progress':state.get('progress',0),'error':state.get('error'),'native':True,'activeModel':state.get('model'),'vision':bool(state.get('vision')),'builtinVision':bool(state.get('builtinVisionActive'))}

class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def reply(self,code,value):
  b=json.dumps(value).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def allowed(self):
  port=config()['uiPort'];return self.headers.get('Host') in [f'127.0.0.1:{port}',f'localhost:{port}'] and (not self.headers.get('Origin') or self.headers['Origin']==f'http://127.0.0.1:{port}')
 def json(self,code,value):return self.reply(code,value)
 def do_GET(self):
  from speech_input import route as speech_input_route
  if speech_input_route(self,False,Path(os.environ.get('YOEAI_ASSISTANT_RUNTIME',str(APP))),DATA):return
  from object_generation import route as object_route
  if object_route(self,False,APP,DATA,BUNDLE,config):return
  from lite_video_generation import route as video_route
  if video_route(self,False,APP,DATA,BUNDLE,config):return
  if self.path.startswith('/assistant/'):
   from intelligence.routes import route as assistant_route
   if assistant_route(self,False,DATA,Path(os.environ.get('YOEAI_ASSISTANT_RUNTIME',str(APP))),'Lite'):return
  from lite_image_generation import route as image_route
  if image_route(self,False,APP,DATA,BUNDLE,config):return
  if self.path.startswith('/local-models/'):
   from model_settings import route as local_models_route,configure_lite
   if local_models_route(self,False,configure_lite(APP,DATA,config)):return
  from lite_agents_bridge import route_agents
  if route_agents(self,False,DATA,BUNDLE,config):return
  from web_search import route as search_route
  if search_route(self,False,DATA):return
  if lite_read_aloud.route(self):return
  if not self.allowed():return self.reply(403,{'error':'Only the local Lite interface is allowed.'})
  path=unquote(urlsplit(self.path).path)
  if path.startswith('/assets/'):
   from request_policy import packaged_assets
   item=packaged_assets(BUNDLE/'assets').get(path[len('/assets/'):])
   if item is None:return self.reply(404,{'error':'Asset not found'})
   file,content_type=item
   b=file.read_bytes();self.send_response(200);self.send_header('Content-Type',content_type);self.send_header('Content-Length',str(len(b)));self.send_header('X-Content-Type-Options','nosniff');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(b);return
  if self.path=='/':
   from request_policy import page_headers
   source=BUNDLE/'ui.html';b=source.read_bytes();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(b)))
   for key,value in page_headers().items():self.send_header(key,value)
   self.end_headers();self.wfile.write(b)
  elif self.path=='/status':
   try:
    raw=subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,memory.total,utilization.gpu,temperature.gpu','--format=csv,noheader,nounits'],text=True,stdin=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW,timeout=10);v=[float(x) for x in raw.splitlines()[0].split(',')];self.reply(200,dict(zip(['used','total','util','temp'],v))|dict(context=config()['context'],model=config()['model'],**native_status()))
   except Exception as e:self.reply(200,dict(context=config()['context'],model=config()['model'],used=None,total=None,util=None,temp=None,warning='GPU monitoring unavailable: '+str(e),**native_status()))
  else:self.reply(404,{'error':'Not found'})
 def do_POST(self):
  from speech_input import route as speech_input_route
  if speech_input_route(self,True,Path(os.environ.get('YOEAI_ASSISTANT_RUNTIME',str(APP))),DATA):return
  from object_generation import route as object_route
  if object_route(self,True,APP,DATA,BUNDLE,config):return
  from lite_video_generation import route as video_route
  if video_route(self,True,APP,DATA,BUNDLE,config):return
  if self.path.startswith('/assistant/'):
   from intelligence.routes import route as assistant_route
   if assistant_route(self,True,DATA,Path(os.environ.get('YOEAI_ASSISTANT_RUNTIME',str(APP))),'Lite'):return
  from lite_image_generation import route as image_route
  if image_route(self,True,APP,DATA,BUNDLE,config):return
  if self.path.startswith('/local-models/'):
   from model_settings import route as local_models_route,configure_lite
   if local_models_route(self,True,configure_lite(APP,DATA,config)):return
  if self.path in ['/writing/check','/writing/cancel']:
   from lite_agents_bridge import initialize
   initialize(DATA,BUNDLE,config)
   from writing_check import route as writing_route
   if writing_route(self,True):return
  from windows_spelling import route as spell_route
  if spell_route(self,True):return
  from lite_agents_bridge import route_agents,shared_request
  if route_agents(self,True,DATA,BUNDLE,config):return
  with shared_request(self,DATA,BUNDLE,config) as ready:
   if ready:return self.existing_POST()
 def existing_POST(self):
  from web_search import route as search_route
  if search_route(self,True,DATA):return
  if lite_read_aloud.route(self,True):return
  if not self.allowed():return self.reply(403,{'error':'Only the local Lite interface is allowed.'})
  if self.headers.get('Transfer-Encoding'):return self.reply(400,{'error':'Unsupported transfer encoding.'})
  try:length=int(self.headers.get('Content-Length','-1'))
  except ValueError:return self.reply(400,{'error':'Invalid length.'})
  if not 0<=length<=25000000:return self.reply(400,{'error':'Invalid or oversized request.'})
  self.connection.settimeout(30)
  try:
   body=self.rfile.read(length)
   if len(body)!=length:return self.reply(400,{'error':'Incomplete request body.'})
   if self.path=='/developer-mode':
    if self.headers.get('Origin')!=f"http://127.0.0.1:{config()['uiPort']}":return self.reply(403,{'error':'Local desktop action only.'})
    from developer_mode import launch
    launch(Path(__file__));return self.reply(200,{'status':'opened','note':'Developer settings opened on this PC.'})
   if self.path=='/shutdown':
    try:token=json.loads(body).get('token')
    except ValueError:return self.reply(400,{'error':'Invalid shutdown request.'})
    if not UI_STATE.exists() or token!=json.loads(UI_STATE.read_text())['token']:return self.reply(403,{'error':'Unauthorized shutdown.'})
    if lite_read_aloud.INSTANCE:lite_read_aloud.INSTANCE.stop()
    self.reply(200,{'status':'closing'});threading.Thread(target=self.server.shutdown,daemon=True).start();return
   if self.path=='/context':
    try:n=json.loads(body)['context']
    except (ValueError,KeyError,TypeError):return self.reply(400,{'error':'Invalid context request.'})
    from context_limits import validate_context
    try:
     model=config().get('model')
     if not model:raise ValueError('Choose a local model before changing its context.')
     validate_context(model,n)
    except (ValueError,OSError,AssertionError) as ex:return self.reply(400,{'error':str(ex)})
    with LOCK:
     previous=config();stop_engine();c=dict(previous);c['context']=n
     from model_settings import atomic
     atomic(CONFIG,c)
     try:start()
     except Exception as failure:
      try:
       stop_engine();atomic(CONFIG,previous);start()
      except Exception as recovery:
       raise RuntimeError(f'Context change failed: {failure}. Recovery also failed: {recovery}. Restart Lite with your previous context.') from failure
      raise RuntimeError(f'Context {n} could not start: {failure}. Previous context restored.') from failure
    return self.reply(200,{'status':'ok','context':n})
   if self.path!='/v1/chat/completions':return self.reply(404,{'error':'Not found'})
   from builtin_vision import activate,has_current_image
   from request_policy import chat_payload
   try:payload=chat_payload(body)
   except ValueError as error:return self.reply(400,{'error':str(error)})
   body=json.dumps(payload,ensure_ascii=False).encode('utf8')
   activate(APP,DATA,config,vision=has_current_image(payload['messages']))
   if not healthy():
    import lite_native
    if lite_native.INSTANCE.state.get('manualUnloaded'):raise ValueError('The model is unloaded. Open Settings and select Load to chat again.')
    start()
   upstream=NativeConnection(timeout=180);upstream.request('POST',self.path,body,{'Content-Type':'application/json'});response=upstream.getresponse();self.send_response(response.status);self.send_header('Content-Type',response.getheader('Content-Type','application/json'));self.end_headers()
   try:
    while True:
     chunk=response.read1(8192)
     if not chunk:break
     self.wfile.write(chunk);self.wfile.flush()
   finally:upstream.close()
  except (BrokenPipeError,ConnectionResetError):pass
  except Exception as e:
   try:self.reply(500,{'error':str(e)})
   except Exception:pass
def serve(browser=True):
 def open_browser():
  exe=Path(os.environ.get('PROGRAMFILES(X86)','C:/Program Files (x86)'))/'Microsoft/Edge/Application/msedge.exe'
  if not exe.exists():raise RuntimeError('Microsoft Edge is required. No browser runtime is redistributed.')
  subprocess.Popen([str(exe),'--app=http://127.0.0.1:'+str(config()['uiPort'])+'/', '--user-data-dir='+str(DATA/'BrowserProfile')],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 import lite_native
 if not lite_native.acquire_profile(DATA):
  if browser:open_browser()
  return
 try:server=ThreadingHTTPServer(('127.0.0.1',config()['uiPort']),Handler);server.daemon_threads=True
 except OSError:
  with HTTP.open(f"http://127.0.0.1:{config()['uiPort']}/status",timeout=3) as response:existing=json.load(response)
  if existing.get('model')!=config()['model']:raise RuntimeError('Lite interface port belongs to another service.')
  if browser:open_browser()
  return
 UI_STATE.write_text(json.dumps(dict(pid=os.getpid(),identity=identity(os.getpid()),token=uuid.uuid4().hex)))
 # File discovery is lightweight and never loads or switches the selected model.
 from model_settings import configure_lite
 configure_lite(APP,DATA,config)
 # Registration is local and lightweight; search/reader workers stay lazy.
 try:
  from intelligence.routes import initialize as initialize_assistant
  initialize_assistant(DATA,Path(os.environ.get('YOEAI_ASSISTANT_RUNTIME',str(APP))),'Lite')
 except Exception as error:
  (DATA/'research-startup-notice.txt').write_text('Research preparation unavailable: '+str(error),encoding='utf8')
 def load():
  try:
   from lite_refresh import start_with_context_upgrade
   start_with_context_upgrade(CONFIG,DATA,start,stop_engine)
  except Exception as error:
   lite_native.INSTANCE.state.update(phase='error',error=str(error))
   (DATA/'last-error.txt').write_text(str(error),encoding='utf8')
 lite_native.INSTANCE.state.update(phase='idle',progress=0,error=None)
 if not config().get('loadOnDemand',True):
  lite_native.INSTANCE.state.update(phase='loading')
  threading.Thread(target=load,daemon=True,name='Lite-native-loader').start()
 try:
  if browser:open_browser()
  server.serve_forever()
 finally:
  from intelligence.routes import shutdown as shutdown_assistant
  shutdown_assistant()
  import model_settings
  if model_settings.INSTANCE and hasattr(model_settings.INSTANCE,'linked_library'):model_settings.INSTANCE.linked_library.close()
  server.server_close()
  import speech_input
  if speech_input.INSTANCE:speech_input.INSTANCE.close()
  import lite_video_generation
  if lite_video_generation.INSTANCE:lite_video_generation.INSTANCE.shutdown()
  import object_generation
  if object_generation.INSTANCE:object_generation.INSTANCE.shutdown()
  from lite_agents_bridge import shutdown
  shutdown()
  if lite_read_aloud.INSTANCE:lite_read_aloud.INSTANCE.stop()
  from lite_image_generation import shutdown as image_shutdown
  image_shutdown()
  lite_native.shutdown()
def install():
 from online_setup import run_setup
 run_setup(payload=APP,offline=APP)

def needs_setup():
 # A packaged download has archives, not an extracted Backend yet.
 # Never replace an existing user's configuration automatically.
 return not CONFIG.exists() and (APP/'package-manifest.json').is_file() and (APP/'Runtime').is_dir()

def diagnose_windows_handles():
 result=subprocess.run([str(APP/'NativeEngine/YOEAI-Inference.exe'),'--probe',str(APP/'NativeRuntime/b11784')],capture_output=True,text=True,encoding='utf8',timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
 if result.returncode:raise RuntimeError('The bundled native runtime could not initialize: '+result.stderr[-500:])
 (DATA/'windows-handle-diagnostic.json').write_text(result.stdout,encoding='utf8')

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--developer-mode',action='store_true');parser.add_argument('--setup',action='store_true');parser.add_argument('--stop',action='store_true');parser.add_argument('--headless',action='store_true');parser.add_argument('--web-search-check',action='store_true');parser.add_argument('--diagnose-windows-handles',action='store_true');args=parser.parse_args()
 try:
  if args.web_search_check:
   from web_search import diagnostic
   diagnostic(DATA/'web-search-native-check.json')
  elif args.developer_mode:
   from developer_mode import main
   main(APP,config(),DATA,lite=True,ui_dir=Path(getattr(sys,'_MEIPASS',APP)))
  elif args.diagnose_windows_handles:diagnose_windows_handles()
  elif args.setup:install()
  elif args.stop:stop()
  elif needs_setup():
   if args.headless:raise RuntimeError('Lite is not installed. Run Install-Lite.bat and complete setup first.')
   install()
  else:serve(not args.headless)
 except Exception as e:
  (DATA/'last-error.txt').write_text(str(e))
  if not args.headless:ctypes.windll.user32.MessageBoxW(None,str(e),'YOEAI Lite',0x10)
  sys.exit(1)
