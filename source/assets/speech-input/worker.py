"""Private Python 3.11 worker. Audio never leaves the computer."""
import argparse, json, os, sys, time, threading
from pathlib import Path

def emit(value):
 print(json.dumps(value,ensure_ascii=False),flush=True)

def record(path, seconds):
 import numpy as np
 import sounddevice as sd
 import soundfile as sf
 stop=threading.Event()
 def listen():
  if sys.stdin.readline().strip()=='stop':stop.set()
 threading.Thread(target=listen,daemon=True).start()
 chunks=[];rate=16000;started=time.monotonic()
 def callback(data,frames,timing,status):
  chunks.append(data.copy())
 with sd.InputStream(samplerate=rate,channels=1,dtype='float32',callback=callback):
  emit({'status':'recording','device':str(sd.query_devices(kind='input')['name'])})
  stop.wait(seconds)
 if not chunks:raise ValueError('No audio was captured. Check Windows microphone permissions.')
 data=np.concatenate(chunks);sf.write(path,data,rate,subtype='PCM_16')
 emit({'status':'recorded','duration':len(data)/rate,'peak':float(np.max(np.abs(data))),'seconds':time.monotonic()-started})

def serve(root):
 import importlib.util,torch,numpy as np,soundfile as sf
 if not torch.cuda.is_available():raise ValueError('CUDA is unavailable; no CPU model was substituted.')
 spec=importlib.util.spec_from_file_location('official_bark',root/'bark_loader.py')
 loader=importlib.util.module_from_spec(spec);spec.loader.exec_module(loader)
 model=None
 emit({'status':'ready','cuda':torch.version.cuda,'gpu':torch.cuda.get_device_name(0)})
 for line in sys.stdin:
  try:
   request=json.loads(line)
   if request.get('op')=='close':break
   if request.get('op')!='transcribe':raise ValueError('Unsupported speech operation.')
   path=Path(request['audio']);wave,rate=sf.read(str(path),dtype='float32',always_2d=True)
   if not 0<len(wave)<=rate*61 or not np.isfinite(wave).all():raise ValueError('Choose a finite recording of at most 60 seconds.')
   if float(np.max(np.abs(wave)))<.001:raise ValueError('The microphone recording is silent. Check the selected input device and try again.')
   began=time.monotonic();torch.cuda.reset_peak_memory_stats()
   if model is None:model=loader.load_model(str(root/'model.bark'),device='cuda',dtype=torch.float32)
   else:model=model.to('cuda')
   torch.cuda.synchronize();loaded=time.monotonic()
   text=loader.transcribe(model,wave.mean(1),rate);torch.cuda.synchronize()
   elapsed=time.monotonic()-loaded;peak=torch.cuda.max_memory_allocated()
   # Retain decoded weights in RAM, release VRAM before restoring the chat model.
   model=model.to('cpu');torch.cuda.empty_cache()
   emit({'status':'complete','message':'Transcription ready. Review or edit it before sending.','text':text,'device':'cuda','gpu':torch.cuda.get_device_name(0),'loadSeconds':loaded-began,'transcribeSeconds':elapsed,'peakAllocatedBytes':peak,'duration':len(wave)/rate,'resident':'cpu','offline':os.environ.get('HF_HUB_OFFLINE')=='1'})
  except Exception as ex:
   model=None
   import gc;gc.collect();torch.cuda.empty_cache()
   emit({'status':'error','message':str(ex)[:1000]})

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['record','serve','devices']);parser.add_argument('--model');parser.add_argument('--output');parser.add_argument('--seconds',type=float,default=60);args=parser.parse_args()
 try:
  if args.mode=='record':record(args.output,min(60,max(1,args.seconds)))
  elif args.mode=='devices':
   import sounddevice as sd
   emit({'devices':[dict(d) for d in sd.query_devices()],'default':list(sd.default.device)})
  else:serve(Path(args.model))
 except Exception as ex:emit({'status':'error','message':str(ex)[:1000]});sys.exit(1)
