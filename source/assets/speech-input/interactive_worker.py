"""Local full-duplex audio, WebRTC AEC3/VAD, Bark Pro CUDA, Kokoro CPU."""
import sys,json,time,threading,queue,collections
from pathlib import Path
PRINT=threading.Lock()
def emit(value):
 with PRINT:print(json.dumps(value,ensure_ascii=False),flush=True)

class VoiceAudio:
 def __init__(self,c):
  import numpy as np,torch,sounddevice as sd,soxr,webrtcvad,onnxruntime as ort
  from pywebrtc_audio import AudioProcessor
  from transformers import AutoProcessor,ParakeetForTDT
  from phonemizer.backend.espeak.wrapper import EspeakWrapper
  from kokoro_onnx import Kokoro
  from kokoro_onnx.config import EspeakConfig
  self.np=np;self.torch=torch;self.sd=sd;self.soxr=soxr;self.stream=None;self.stop=threading.Event();self.closed=threading.Event();self.audioq=queue.Queue(200);self.asrq=queue.Queue(2);self.ttsq=queue.Queue(8);self.output=collections.deque();self.outpos=0;self.lock=threading.RLock();self.gen=0;self.latest=0;self.ttsbusy=False;self.response_done=False;self.playing=False;self.last_done=-1;self.muted=False;self.spoken='';self.state='idle';self.vad=webrtcvad.Vad(2)
  self.output_level=0.0
  if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():raise ValueError('CUDA BF16 is required for Interactive Voice.')
  torch.set_num_threads(4);torch.cuda.reset_peak_memory_stats();stamp=time.monotonic()
  self.processor=AutoProcessor.from_pretrained(c['model'],local_files_only=True)
  self.model=ParakeetForTDT.from_pretrained(c['model'],dtype=torch.bfloat16,local_files_only=True).to('cuda').eval()
  speech=Path(c['speech']);lib=str(speech/'eSpeak/libespeak-ng.dll');data=str(speech/'eSpeak/espeak-ng-data');EspeakWrapper.set_library(lib);EspeakWrapper.set_data_path(data)
  options=ort.SessionOptions();options.intra_op_num_threads=3;options.inter_op_num_threads=1
  session=ort.InferenceSession(str(speech/'Models/kokoro-v1.0.onnx'),sess_options=options,providers=['CPUExecutionProvider'])
  self.tts=Kokoro.from_session(session,str(speech/'Models/voices-v1.0.bin'),espeak_config=EspeakConfig(lib_path=lib,data_path=data))
  self.ap=AudioProcessor(sample_rate=16000,echo_cancellation=True,noise_suppression=True,high_pass_filter=True,auto_gain_control=False,stream_delay_ms=180)
  self.tts.create('Ready.',voice='af_heart',speed=1.0,lang='en-us')
  emit({'event':'ready','seconds':time.monotonic()-stamp,'gpu':torch.cuda.get_device_name(0),'tts':'Kokoro af_heart CPU','aec':'WebRTC AEC3','peakAllocatedBytes':torch.cuda.max_memory_allocated()})
  for fn in (self.recognize,self.synthesize):threading.Thread(target=fn,daemon=True).start()
 def decode(self,wave):
  np=self.np;torch=self.torch;wave=np.concatenate([np.zeros(4000,np.float32),wave.astype(np.float32)])
  inputs=self.processor(wave,sampling_rate=16000,return_tensors='pt').to('cuda',torch.bfloat16)
  with torch.inference_mode():out=self.model.generate(**inputs)
  torch.cuda.synchronize();return self.processor.batch_decode(out.sequences if hasattr(out,'sequences') else out,skip_special_tokens=True)[0].strip()
 def clear_audio(self,gen=None):
  with self.lock:
   self.gen=self.gen+1 if gen is None else gen;self.output.clear();self.outpos=0;self.response_done=False;self.playing=False
   while True:
    try:self.ttsq.get_nowait()
    except queue.Empty:break
 def callback(self,indata,outdata,frames,timing,status):
  np=self.np;out=np.zeros(frames,np.float32)
  with self.lock:
   position=0
   while self.output and position<frames:
    audio=self.output[0];count=min(frames-position,len(audio)-self.outpos);out[position:position+count]=audio[self.outpos:self.outpos+count];position+=count;self.outpos+=count
    if self.outpos==len(audio):self.output.popleft();self.outpos=0
   now_playing=bool(position)
   if now_playing and not self.playing:emit({'event':'speaking','generation':self.gen})
   self.playing=now_playing
   if self.muted:out.fill(0)
   self.output_level=float(np.sqrt(np.mean(out**2)))
   outdata[:,0]=out
   done=self.response_done and not self.output and not self.ttsbusy and self.ttsq.empty() and self.last_done!=self.gen
   if done:self.last_done=self.gen;emit({'event':'playback_done','generation':self.gen})
  clean=self.ap.process(indata[:,0].copy(),out)
  try:self.audioq.put_nowait((clean,float(self.ap.speech_probability),now_playing))
  except queue.Full:
   try:self.audioq.get_nowait();self.audioq.put_nowait((clean,float(self.ap.speech_probability),now_playing))
   except queue.Empty:pass
 def start(self):
  if self.stream:return
  self.stop.clear();self.ap.reset();self.stream=self.sd.Stream(samplerate=16000,blocksize=160,channels=(1,1),dtype='float32',latency='low',callback=self.callback)
  self.stream.start();emit({'event':'listening','microphone':self.sd.query_devices(kind='input')['name'],'speaker':self.sd.query_devices(kind='output')['name'],'inputLatency':self.stream.latency[0],'outputLatency':self.stream.latency[1]})
  threading.Thread(target=self.detect,daemon=True).start()
 def detect(self):
  np=self.np;pending=[];preroll=collections.deque(maxlen=10);captured=[];active=False;run=0;silence=0;voiced=0;started=0;last_meter=0;was_playing=False
  while not self.stop.is_set():
   try:frame,prob,playing=self.audioq.get(timeout=.2)
   except queue.Empty:continue
   pending.append(frame)
   if len(pending)<2:continue
   frame=np.concatenate(pending);pending=[];rms=float(np.sqrt(np.mean(frame**2)));speech=self.vad.is_speech((np.clip(frame,-1,1)*32767).astype('<i2').tobytes(),16000) and rms>.004
   if playing:speech=speech and prob>.65 and rms>.007
   now=time.monotonic()
   if now-last_meter>.1:emit({'event':'meter','level':min(1,self.output_level*12 if self.playing and not self.muted else rms*12)});last_meter=now
   preroll.append(frame)
   if not active:
    run=run+1 if speech else 0
    if run>=(12 if playing else 5):
     active=True;captured=list(preroll);voiced=run;silence=0;started=now;was_playing=playing;self.latest+=1
     if playing:self.clear_audio()
     emit({'event':'speech_start','utterance':self.latest,'interruption':playing})
   else:
    captured.append(frame);voiced+=int(speech);silence=0 if speech else silence+1
    if silence>=33 or len(captured)>=1500:
     uid=self.latest;wave=np.concatenate(captured[:-max(0,silence-6)] if silence>6 else captured);active=False;run=0;captured=[]
     if voiced>=8:
      emit({'event':'recognizing','utterance':uid,'endDetectionSeconds':.66})
      try:self.asrq.put_nowait((uid,wave,was_playing,now))
      except queue.Full:emit({'event':'notice','message':'Please finish one request at a time.'})
     voiced=0;silence=0
 def recognize(self):
  while not self.closed.is_set():
   try:uid,wave,was_playing,ended=self.asrq.get(timeout=.2)
   except queue.Empty:continue
   try:
    stamp=time.monotonic();text=self.decode(wave)
    if uid!=self.latest or self.stop.is_set():continue
    # Additional playback-aware backstop; not a guarantee for every room.
    import re
    words=set(re.findall(r'\w+',text.lower()));reference=set(re.findall(r'\w+',self.spoken.lower()))
    if was_playing and len(words)>=3 and len(words&reference)/len(words)>.75:emit({'event':'echo_rejected'});continue
    if text:emit({'event':'utterance','text':text,'asrSeconds':time.monotonic()-stamp,'audioSeconds':len(wave)/16000,'endDetectionSeconds':.66,'peakAllocatedBytes':self.torch.cuda.max_memory_allocated()})
   except Exception as ex:emit({'event':'error','message':str(ex)[:700]})
 def synthesize(self):
  while not self.closed.is_set():
   try:gen,text=self.ttsq.get(timeout=.2)
   except queue.Empty:continue
   try:
    if gen!=self.gen:continue
    self.ttsbusy=True;stamp=time.monotonic();samples,rate=self.tts.create(text,voice='af_heart',speed=1.0,lang='en-us');audio=self.soxr.resample(samples,rate,16000).astype(self.np.float32)
    with self.lock:
     if gen==self.gen:self.output.append(audio);self.spoken=(self.spoken+' '+text)[-2000:]
    emit({'event':'tts_audio','generation':gen,'seconds':time.monotonic()-stamp,'duration':len(audio)/16000})
   except Exception as ex:emit({'event':'error','message':str(ex)[:700]})
   finally:self.ttsbusy=False
 def close(self):
  self.stop.set();self.closed.set();self.clear_audio()
  if self.stream:self.stream.abort();self.stream.close();self.stream=None
 def command(self,r):
  op=r.get('op')
  if op=='start':self.start()
  elif op=='begin':self.clear_audio(int(r['generation']))
  elif op=='speak':
   text=r.get('text','')
   if not isinstance(text,str) or not 0<len(text)<=600:raise ValueError('Choose a short spoken sentence.')
   self.ttsq.put_nowait((int(r['generation']),text))
  elif op=='response_done':
   if int(r['generation'])==self.gen:self.response_done=True
  elif op=='interrupt':self.clear_audio()
  elif op=='mute':self.muted=r.get('muted') is True
  elif op=='test_asr':
   import soundfile as sf
   wave,rate=sf.read(r['path'],dtype='float32',always_2d=True);wave=wave.mean(1)
   if rate!=16000:wave=self.soxr.resample(wave,rate,16000)
   stamp=time.monotonic();text=self.decode(wave);emit({'event':'test_asr','text':text,'seconds':time.monotonic()-stamp,'peakAllocatedBytes':self.torch.cuda.max_memory_allocated()})
  elif op=='test_tts':
   import soundfile as sf
   stamp=time.monotonic();audio,rate=self.tts.create(r['text'],voice='af_heart',speed=1.0,lang='en-us');sf.write(r['path'],audio,rate);emit({'event':'test_tts','seconds':time.monotonic()-stamp,'duration':len(audio)/rate})
  else:raise ValueError('Unsupported local audio operation.')

if __name__=='__main__':
 worker=None
 try:
  c=json.loads(Path(sys.argv[1]).read_text(encoding='utf8'));worker=VoiceAudio(c)
  for line in sys.stdin:
   try:
    r=json.loads(line)
    if r.get('op')=='close':break
    worker.command(r)
   except Exception as ex:emit({'event':'error','message':str(ex)[:700]})
 except Exception as ex:emit({'event':'error','message':str(ex)[:1000]})
 finally:
  if worker:worker.close()
