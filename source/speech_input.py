"""Explicit local microphone capture; dictation results are never submitted."""
import atexit,json,os,subprocess,threading,time,uuid,queue
from pathlib import Path
from configuration import APP_DIR,HOME
ACTIVE={'starting','recording','transcribing','restoring'}

class Dictation:
 def __init__(self,config=None):
  self.config=Path(config) if config else APP_DIR/'SpeechInput/config.json'
  self.lock=threading.RLock();self.state={'status':'idle'};self.capture=None;self.worker=None;self.messages=queue.Queue();self.cancelled=threading.Event();self.finished=threading.Event();self.finished.set()
  self.audio=HOME/'Dictation';self.audio.mkdir(parents=True,exist_ok=True);atexit.register(self.cancel)
 def status(self):
  with self.lock:return dict(self.state)
 def update(self,**values):
  with self.lock:self.state.update(**values)
 def settings(self):
  if not self.config.is_file():raise ValueError('Local English dictation is not installed on this PC.')
  c=json.loads(self.config.read_text(encoding='utf8'))
  for key in ('python','worker','model'):
   if not Path(c[key]).exists():raise ValueError('Local dictation files are missing: '+key)
  return c
 def launch(self,args,c):
  env=os.environ.copy();env.update(PYTHONIOENCODING='utf-8',HF_HOME=c['cache'],HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1')
  for key in ('PYTHONPATH','PYTHONHOME','QT_QPA_PLATFORM'):env.pop(key,None)
  return subprocess.Popen([c['python'],'-u',c['worker'],*args],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,encoding='utf8',env=env,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
 def start(self,approved=False):
  if approved is not True:raise ValueError('Activate the microphone explicitly before recording.')
  c=self.settings()
  with self.lock:
   if self.state['status'] in ACTIVE:raise ValueError('Stop or cancel the current recording first.')
   self.cancelled.clear();self.finished.clear();ident=uuid.uuid4().hex;path=self.audio/(ident+'.wav')
   self.state={'status':'starting','id':ident,'message':'Opening microphone…'}
   try:self.capture=self.launch(['record','--output',str(path)],c)
   except Exception:self.finished.set();self.state={'status':'error','message':'Could not open the microphone service.'};raise
   threading.Thread(target=self.run,args=(path,c),daemon=True,name='YOE-Dictation').start()
   return self.status()
 def stop(self):
  with self.lock:
   if self.state['status'] not in ('starting','recording'):raise ValueError('No active recording.')
   if self.capture and self.capture.poll() is None:
    self.capture.stdin.write('stop\n');self.capture.stdin.flush()
   return self.status()
 def cancel(self):
  with self.lock:
   self.cancelled.set()
   for p in (self.capture,self.worker):
    if p and p.poll() is None:p.terminate()
   self.worker=None
   if self.state['status'] not in ACTIVE:self.state={'status':'cancelled','message':'Dictation cancelled.'}
   return {'cancelling':True}
 def check(self):
  if self.cancelled.is_set():raise InterruptedError('Dictation cancelled.')
 def reply(self,timeout):
  deadline=time.monotonic()+timeout
  while time.monotonic()<deadline:
   self.check()
   try:return self.messages.get(timeout=.2)
   except queue.Empty:pass
  raise ValueError('Local transcription timed out. Try a shorter recording.')
 def reader(self,p,q):
  try:
   for line in p.stdout:
    try:q.put(json.loads(line))
    except ValueError:continue
  finally:q.put({'status':'error','message':'The speech worker exited. Try again.'})
 def run(self,path,c):
  held=False;paused=False;result=None
  try:
   for line in self.capture.stdout:
    self.check();value=json.loads(line)
    if value['status']=='error':raise ValueError(value['message'])
    if value['status']=='recording':self.update(status='recording',message='Listening locally · click Stop to transcribe',device=value.get('device'))
   self.capture.wait(timeout=5);self.check()
   if not path.is_file():raise ValueError('Microphone capture failed. Check Windows Settings → Privacy → Microphone and your input device.')
   from mini_agents import GATE
   held=GATE.acquire(blocking=False)
   if not held:raise ValueError('The AI is busy. Finish its current task, then record again.')
   from model_modes import media_busy,pause_for_media,ensure_selected
   if media_busy():raise ValueError('Wait for image or video generation to finish first.')
   self.update(status='transcribing',message='Preparing local English transcription…')
   paused=pause_for_media();self.check()
   if self.worker is None or self.worker.poll() is not None:
    self.messages=queue.Queue();self.worker=self.launch(['serve','--model',c['model']],c)
    threading.Thread(target=self.reader,args=(self.worker,self.messages),daemon=True).start()
    ready=self.reply(60)
    if ready.get('status')!='ready':raise ValueError(ready.get('message','Speech worker unavailable.'))
   self.worker.stdin.write(json.dumps({'op':'transcribe','audio':str(path)})+'\n');self.worker.stdin.flush()
   result=self.reply(240)
   if result.get('status')!='complete':raise ValueError(result.get('message','Transcription failed.'))
   self.check()
  except InterruptedError:result={'status':'cancelled','message':'Dictation cancelled.'}
  except Exception as ex:result={'status':'error','message':str(ex)[:1000]}
  finally:
   try:
    if result and result.get('status')!='complete' and self.worker:
     if self.worker.poll() is None:
      self.worker.terminate();self.worker.wait(timeout=10)
     self.worker=None
    if paused:
     self.update(status='restoring',message='Restoring your chat model…')
     ensure_selected()
   except Exception as ex:
    result={'status':'error','message':'Dictation ended, but the chat model could not be restored: '+str(ex)[:700]}
   finally:
    if held:GATE.release()
    path.unlink(missing_ok=True)
    if self.cancelled.is_set() and result and result.get('status')=='complete':result={'status':'cancelled','message':'Dictation cancelled.'}
    self.update(**(result or {'status':'error','message':'Dictation did not finish.'}));self.capture=None;self.finished.set()

INSTANCE=None
def service():
 global INSTANCE
 if INSTANCE is None:
  config=APP_DIR/'SpeechInput/config.json'
  if config.is_file() and json.loads(config.read_text(encoding='utf8')).get('engine')=='bark-pro':
   from speech_live import LiveDictation
   INSTANCE=LiveDictation()
  else:INSTANCE=Dictation()
 return INSTANCE
def route(h,post=False):
 if not h.path.startswith('/dictation/'):return False
 if not h.allowed() or post and h.headers.get('Origin')!='http://'+h.headers.get('Host',''):
  h.json(403,{'error':'Use the local YOEAI interface.'});return True
 try:
  s=service()
  if not post and h.path=='/dictation/state':value=s.status()
  elif post:
   size=int(h.headers.get('Content-Length','0'))
   if h.headers.get('Transfer-Encoding') or not 0<size<=256:raise ValueError('Invalid dictation request.')
   body=json.loads(h.rfile.read(size))
   if not isinstance(body,dict):raise ValueError('Invalid dictation request.')
   if h.path=='/dictation/start':value=s.start(body.get('activated'))
   elif h.path=='/dictation/stop':value=s.stop()
   elif h.path=='/dictation/cancel':value=s.cancel()
   else:raise ValueError('Unsupported dictation operation.')
  else:raise ValueError('Unsupported dictation operation.')
  h.json(200,value)
 except Exception as ex:h.json(400,{'error':str(ex)[:1000]})
 return True
