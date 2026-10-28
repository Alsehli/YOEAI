# SPDX-License-Identifier: GPL-3.0-only
"""Same-origin, CPU-only Read aloud jobs for Normal YOEAI."""
import atexit,json,re,subprocess,threading,time,uuid,wave
from pathlib import Path
from configuration import APP_DIR,HOME
class SpeechJobs:
 def __init__(self):
  self.root=APP_DIR/'Speech';self.output=HOME/'Speech-Audio';self.output.mkdir(parents=True,exist_ok=True)
  self.lock=threading.Lock();self.process=None;self.cancelled=threading.Event();self.state={'status':'idle'};atexit.register(self.stop)
 def status(self):
  with self.lock:return dict(self.state)
 def start(self,text,speed):
  if not isinstance(text,str) or not text.strip() or len(text)>6000:raise ValueError('Choose a reply between 1 and 6,000 characters.')
  if isinstance(speed,bool) or speed not in (0.85,1.0,1.15):raise ValueError('Unsupported speech speed.')
  for rel in ['Runtime/YOEAI-Speech.exe','Models/kokoro-v1.0.onnx','Models/voices-v1.0.bin','eSpeak/libespeak-ng.dll','eSpeak/espeak-ng-data/phontab']:
   if not (self.root/rel).is_file():raise ValueError('The local Read aloud files are missing. Use the updated Normal package.')
  with self.lock:
   if self.state['status']=='running':raise ValueError('Stop the current voice before reading another reply.')
   job=uuid.uuid4().hex;self.cancelled.clear();self.state={'status':'running','id':job,'message':'Preparing voice…'}
   threading.Thread(target=self.run,args=(job,text.strip(),float(speed)),daemon=True).start()
   return dict(self.state)
 def stop(self):
  with self.lock:
   if self.state['status']=='running':
    self.cancelled.set()
    if self.process and self.process.poll() is None:self.process.terminate()
   return dict(self.state)
 def run(self,job,text,speed):
  output=self.output/(job+'.wav');started=time.monotonic()
  try:
   with self.lock:
    if self.cancelled.is_set():raise InterruptedError()
    self.process=subprocess.Popen([str(self.root/'Runtime/YOEAI-Speech.exe')],cwd=str(self.root),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    process=self.process
   try:stdout,stderr=process.communicate(json.dumps({'text':text,'speed':speed,'output':str(output)}).encode('utf-8'),timeout=300)
   except subprocess.TimeoutExpired:process.kill();process.communicate();raise ValueError('Voice preparation timed out. Try a shorter reply.')
   if self.cancelled.is_set():raise InterruptedError()
   if process.returncode or not output.is_file():raise ValueError('Voice preparation failed. Check the local speech files.')
   with wave.open(str(output),'rb') as audio:
    frames=audio.getnframes();rate=audio.getframerate()
    if not frames or rate!=24000 or audio.getnchannels()!=1 or audio.getsampwidth()!=2:raise ValueError('The voice engine produced invalid audio.')
   result={'status':'complete','id':job,'url':'/speech/audio/'+job,'message':'Voice ready.','seconds':round(time.monotonic()-started,2),'duration':round(frames/rate,2)}
  except InterruptedError:result={'status':'cancelled','id':job,'message':'Voice stopped.'}
  except Exception as error:result={'status':'error','id':job,'message':str(error)}
  finally:
   with self.lock:self.process=None;self.state=result
 def audio(self,name):
  if not re.fullmatch('[0-9a-f]{32}',name):raise ValueError('Invalid audio reference.')
  p=self.output/(name+'.wav')
  if not p.is_file() or p.stat().st_size>100_000_000:raise ValueError('Audio is unavailable.')
  return p.read_bytes()
INSTANCE=None
def jobs():
 global INSTANCE
 if INSTANCE is None:INSTANCE=SpeechJobs()
 return INSTANCE

def route(handler,post=False):
 path=handler.path.split('?',1)[0]
 if not path.startswith('/speech/'):return False
 if not handler.allowed():handler.json(403,{'error':'Read aloud is available only in the local YOEAI app.'});return True
 try:
  if post:
   if handler.headers.get('Origin')!='http://'+handler.headers.get('Host',''):raise ValueError('Use the local YOEAI app to read replies.')
   if handler.headers.get('Transfer-Encoding'):raise ValueError('Unsupported transfer encoding.')
   length=int(handler.headers.get('Content-Length','0'))
   if not 0<length<=40000:raise ValueError('Invalid speech request size.')
   body=json.loads(handler.rfile.read(length))
   if not isinstance(body,dict):raise ValueError('Invalid speech request.')
   if path=='/speech/create':data=jobs().start(body.get('text'),body.get('speed',1.0))
   elif path=='/speech/stop':data=jobs().stop()
   else:handler.json(404,{'error':'Unknown speech request.'});return True
   handler.json(200,data)
  elif path=='/speech/status':handler.json(200,jobs().status())
  elif path.startswith('/speech/audio/'):
   data=jobs().audio(path[len('/speech/audio/'):]);handler.send_response(200);handler.send_header('Content-Type','audio/wav');handler.send_header('Content-Length',str(len(data)));handler.send_header('X-Content-Type-Options','nosniff');handler.send_header('Cache-Control','no-store');handler.end_headers();handler.wfile.write(data)
  else:handler.json(404,{'error':'Unknown speech request.'})
 except (ValueError,TypeError,KeyError) as error:handler.json(400,{'error':str(error)})
 return True
