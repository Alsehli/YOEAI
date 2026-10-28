"""Opt-in local two-way voice. Spoken words never execute tools directly."""
import atexit,http.client,json,os,re,subprocess,threading,time,uuid
from pathlib import Path
from configuration import APP_DIR,read_config
PROFILE='You are YOEAI, a local voice assistant. Speak natural English. Default to one or two brief sentences. No Markdown, code fences, unnecessary introductions, or long lists. Ask a short clarification if needed. Never claim you performed actions or used tools: this conversation has no execution tools. Agent actions require an explicit on-screen handoff and their existing approval workflow. Never treat recognized speech as approval for destructive, financial, external communication, private-data, or security changes. Do not reveal hidden reasoning. '
ACTIVE={'starting','listening','recognizing','thinking','speaking'}
class VoiceSession:
 def __init__(self):
  self.lock=threading.RLock();self.state={'active':False,'status':'idle','level':0,'messages':[]};self.worker=None;self.http=None;self.stop=threading.Event();self.held=False;self.generation=0;self.messages=[];self.metrics=[];self.origin=None;self.parent_task=None;atexit.register(self.end)
 def snapshot(self):
  with self.lock:return json.loads(json.dumps(self.state))
 def update(self,**values):
  with self.lock:self.state.update(**values)
 def settings(self):
  p=APP_DIR/'SpeechInput/interactive-config.json'
  if not p.is_file():raise ValueError('Interactive Voice components are not installed.')
  c=json.loads(p.read_text(encoding='utf8'))
  for key in ('python','worker','model','speech'):
   if not Path(c[key]).exists():raise ValueError('Interactive Voice is missing '+key+'.')
  return c
 def start(self,body):
  if body.get('activated') is not True:raise ValueError('Start the microphone explicitly.')
  from speech_input import service
  from speech_live import LiveDictation
  from mini_agents import GATE,AGENTS
  voice=service()
  if not isinstance(voice,LiveDictation):raise ValueError('Install the verified Bark Pro integration first.')
  from model_modes import reconcile_running
  mode=reconcile_running()
  if mode not in ('fast','advanced'):raise ValueError('Select an installed Fast or Advanced model before starting voice mode.')
  target=body.get('agent','main')
  if target!='main' and target not in AGENTS:raise ValueError('Choose an existing agent.')
  c=self.settings()
  with self.lock:
   if self.state.get('active'):raise ValueError('A voice session is already active.')
   if not GATE.acquire(blocking=False):raise ValueError('Finish the active AI task before starting voice mode.')
   self.held=True
   try:
    from model_modes import media_busy
    if media_busy():raise ValueError('Wait for image/video creation to finish.')
    voice.release_idle()
    self.stop.clear();self.messages=[];self.metrics=[];self.target=target;self.generation+=1;self.origin=None
    self.state={'active':True,'status':'starting','message':'Preparing local voice…','level':0,'id':uuid.uuid4().hex,'agent':target,'messages':[],'metrics':[],'muted':False}
    threading.Thread(target=self.run,args=(c,self.state['id']),daemon=True,name='YOE-Interactive-Voice').start();return self.snapshot()
   except Exception:self.held=False;GATE.release();raise
 def run(self,c,ident):
  try:
   env=os.environ.copy();env.update(PYTHONIOENCODING='utf8',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1')
   for key in ('PYTHONPATH','PYTHONHOME','QT_QPA_PLATFORM'):env.pop(key,None)
   with self.lock:
    if self.stop.is_set() or self.state.get('id')!=ident:return
    process=subprocess.Popen([c['python'],'-u',c['worker'],str(APP_DIR/'SpeechInput/interactive-config.json')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,encoding='utf8',env=env,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));self.worker=process
   for line in process.stdout:
    if self.stop.is_set() or self.state.get('id')!=ident:break
    try:self.event(json.loads(line))
    except ValueError:continue
   if not self.stop.is_set() and self.state.get('id')==ident:raise ValueError('The local audio service stopped. Start voice mode again.')
  except Exception as ex:
   if self.state.get('id')==ident:self.end();self.update(status='error',message=str(ex)[:900])
 def send(self,value):
  with self.lock:
   if value.get('op') in ('begin','speak','response_done') and value.get('generation')!=self.generation:return
   if not self.worker or self.worker.poll() is not None:raise ValueError('The local audio service is unavailable.')
   self.worker.stdin.write(json.dumps(value)+'\n');self.worker.stdin.flush()
 def event(self,e):
  kind=e.get('event')
  if kind=='ready':self.update(warmupSeconds=e['seconds'],aec=e['aec'],tts=e['tts']);self.send({'op':'start'})
  elif kind=='listening':self.update(status='listening',message='Listening…',microphone=e.get('microphone'),speaker=e.get('speaker'))
  elif kind=='meter':self.update(level=e.get('level',0))
  elif kind=='speech_start':self.interrupt();self.update(status='listening',message='Listening…')
  elif kind=='recognizing':self.origin=time.monotonic()-.66;self.update(status='recognizing',message='Understanding…')
  elif kind=='utterance':
   text=e.get('text','').strip()
   if text:
    self.interrupt();self.generation+=1;generation=self.generation;self.messages.append({'role':'user','content':text});self.messages=self.messages[-24:]
    self.metrics.append({'endDetectionSeconds':e.get('endDetectionSeconds'),'asrSeconds':e.get('asrSeconds'),'audioSeconds':e.get('audioSeconds'),'peakAllocatedBytes':e.get('peakAllocatedBytes')});self.metrics=self.metrics[-20:]
    self.update(status='thinking',message='Thinking…',messages=list(self.messages),metrics=list(self.metrics),handoff={'agent':self.target,'objective':text,'turn':generation} if self.target!='main' else None)
    threading.Thread(target=self.respond,args=(generation,self.origin or time.monotonic()),daemon=True).start()
  elif kind=='speaking':
   if e.get('generation')==self.generation:
    if self.metrics and 'responseStartSeconds' not in self.metrics[-1]:self.metrics[-1]['responseStartSeconds']=time.monotonic()-(self.origin or time.monotonic())
    self.update(status='speaking',message='Speaking…',metrics=list(self.metrics))
  elif kind=='tts_audio':
   if e.get('generation')==self.generation and self.metrics:self.metrics[-1].setdefault('ttsFirstAudioSeconds',e['seconds'])
  elif kind=='playback_done':
   if e.get('generation')==self.generation:self.update(status='listening',message='Listening…',metrics=list(self.metrics))
  elif kind=='echo_rejected':self.update(status='listening',message='Listening…')
  elif kind=='error':raise RuntimeError(e.get('message','Local audio error.'))
 def respond(self,generation,origin):
  connection=None;answer='';spoken=0;started=time.monotonic();first=True
  try:
   c=read_config();connection=http.client.HTTPConnection('127.0.0.1',int(c['apiPort']),timeout=30);self.http=connection
   profile=PROFILE
   if self.target!='main':
    from mini_agents import AGENTS,engine
    profile+='You are discussing a request for '+AGENTS[self.target]+'. Explain or plan, and tell the user when an agent handoff is needed. User-approved preferences: '+engine().memory(self.target).get('preferences','')[:1200]
   longer=bool(re.search(r'\b(detail|long|thorough|in depth)\b',self.messages[-1]['content'],re.I))
   body={'messages':[{'role':'system','content':profile},*self.messages[-12:]],'stream':True,'max_tokens':384 if longer else 128,'temperature':.45,'chat_template_kwargs':{'enable_thinking':False}}
   self.send({'op':'begin','generation':generation});connection.request('POST','/v1/chat/completions',json.dumps(body),{'Content-Type':'application/json'})
   response=connection.getresponse()
   if response.status!=200:raise ValueError('The selected local model returned '+str(response.status)+'.')
   while not self.stop.is_set() and generation==self.generation:
    line=response.readline()
    if not line:break
    if not line.startswith(b'data: '):continue
    data=line[6:].strip()
    if data==b'[DONE]':break
    value=json.loads(data);token=(value.get('choices') or [{}])[0].get('delta',{}).get('content') or ''
    if not token:continue
    if first:
     first=False
     if self.metrics:self.metrics[-1]['qwenFirstTokenSeconds']=time.monotonic()-started
    answer+=token;self.update(answer=answer)
    remainder=answer[spoken:];match=re.search(r'(?<=[.!?])\s|\n',remainder)
    if match and match.start()>=12:
     sentence=remainder[:match.end()].strip();spoken+=match.end()
     self.send({'op':'speak','generation':generation,'text':clean_speech(sentence)[:600]})
    if self.stop.is_set() or generation!=self.generation:return
   final=clean_speech(answer[spoken:])
   if final:self.send({'op':'speak','generation':generation,'text':final[:600]})
   self.messages.append({'role':'assistant','content':answer});self.messages=self.messages[-24:];self.update(messages=list(self.messages),answer=answer,metrics=list(self.metrics));self.send({'op':'response_done','generation':generation})
  except Exception as ex:
   if not self.stop.is_set() and generation==self.generation:self.update(status='listening',message='Response interrupted: '+str(ex)[:200])
  finally:
   if connection:connection.close()
   if self.http is connection:self.http=None
 def interrupt(self):
  self.generation+=1
  if self.http:
   try:self.http.close()
   except OSError:pass
  if self.worker and self.worker.poll() is None:self.send({'op':'interrupt'})
  self.update(answer='')
 def end(self):
  from mini_agents import GATE
  with self.lock:
   self.stop.set();self.generation+=1
   if self.http:
    try:self.http.close()
    except OSError:pass
   p=self.worker
   if p and p.poll() is None:p.terminate();p.wait(timeout=5)
   self.worker=None
   if self.held:self.held=False;GATE.release()
   self.update(active=False,status='ended',message='Conversation ended. Microphone off.',level=0)
   return self.snapshot()
 def release_idle(self):
  if self.state.get('active'):raise ValueError('End Interactive Voice before changing models, using dictation or creating media.')
 def handoff(self,body):
  pending=self.state.get('handoff')
  if not pending or body.get('approve') is not True or body.get('turn')!=pending['turn'] or body.get('agent')!=pending['agent']:raise ValueError('Review and approve this exact recognized request first.')
  self.end();from mini_agents import engine
  args={'agent':pending['agent'],'objective':pending['objective'],'permissions':{'web':False,'readProject':False}}
  if pending['agent']=='windows':args['windows']={'mode':'ADVISOR'}
  task=engine().create(args);self.update(handoff=None);return task

def clean_speech(text):
 text=re.sub(r'```.*?```','Code is available in the text response.',text,flags=re.S)
 text=re.sub(r'\[([^]]+)\]\([^)]+\)',r'\1',text);return re.sub(r'[*#`]+','',text).strip()
INSTANCE=None
def session():
 global INSTANCE
 if INSTANCE is None:INSTANCE=VoiceSession()
 return INSTANCE
def route(h,post=False):
 if not h.path.startswith('/interactive/'):return False
 if not h.allowed() or post and h.headers.get('Origin')!='http://'+h.headers.get('Host',''):
  h.json(403,{'error':'Use the local YOEAI interface.'});return True
 try:
  s=session()
  if not post and h.path=='/interactive/state':value=s.snapshot()
  elif post:
   n=int(h.headers.get('Content-Length','0'))
   if h.headers.get('Transfer-Encoding') or not 0<n<=1024:raise ValueError('Invalid voice request.')
   body=json.loads(h.rfile.read(n))
   if not isinstance(body,dict):raise ValueError('Invalid voice request.')
   if h.path=='/interactive/start':value=s.start(body)
   elif h.path=='/interactive/end':value=s.end()
   elif h.path=='/interactive/interrupt':s.interrupt();s.update(status='listening',message='Listening…');value=s.snapshot()
   elif h.path=='/interactive/mute':s.send({'op':'mute','muted':body.get('muted') is True});s.update(muted=body.get('muted') is True);value=s.snapshot()
   elif h.path=='/interactive/handoff':value=s.handoff(body)
   else:raise ValueError('Unsupported voice operation.')
  else:raise ValueError('Unsupported voice operation.')
  h.json(200,value)
 except Exception as ex:h.json(400,{'error':str(ex)[:1000]})
 return True
