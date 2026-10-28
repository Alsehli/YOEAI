"""Bark Pro BF16 local incremental dictation. Short windows, not native streaming."""
import json,sys,time,threading,re
from pathlib import Path
def emit(value):print(json.dumps(value,ensure_ascii=False),flush=True)
def join_text(left,right):
 a=left.split();b=right.split();norm=lambda s:re.sub(r'[^\w]','',s).casefold()
 for k in range(min(8,len(a),len(b)),0,-1):
  if [norm(x) for x in a[-k:]]==[norm(x) for x in b[:k]]:return ' '.join(a+b[k:])
 return ' '.join(a+b)
def main(root):
 import numpy as np,torch,sounddevice as sd,soundfile as sf,soxr
 from transformers import AutoProcessor,ParakeetForTDT
 if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():raise ValueError('Bark Pro requires CUDA and BF16 support; no alternative model was selected.')
 torch.set_num_threads(4);start=time.monotonic();torch.cuda.reset_peak_memory_stats()
 proc=AutoProcessor.from_pretrained(str(root),local_files_only=True)
 model=ParakeetForTDT.from_pretrained(str(root),dtype=torch.bfloat16,local_files_only=True).to('cuda').eval()
 torch.cuda.synchronize();emit({'status':'ready','loadSeconds':time.monotonic()-start,'gpu':torch.cuda.get_device_name(0),'resident':'cuda','peakAllocatedBytes':torch.cuda.max_memory_allocated()})
 def decode(wave):
  wave=np.concatenate([np.zeros(4000,np.float32),wave.astype(np.float32)])
  inputs=proc(wave,sampling_rate=16000,return_tensors='pt').to('cuda',torch.bfloat16)
  with torch.inference_mode():out=model.generate(**inputs)
  torch.cuda.synchronize();ids=out.sequences if hasattr(out,'sequences') else out
  return proc.batch_decode(ids,skip_special_tokens=True)[0].strip()
 stop=threading.Event();thread=None
 def live():
  began=time.monotonic();chunks=[];rate=16000;offset=0;committed='';latest='';last=0;partials=0;latencies=[];first=None
  def callback(data,frames,timing,status):chunks.append(data[:,0].copy())
  try:
   with sd.InputStream(samplerate=rate,channels=1,dtype='float32',callback=callback):
    emit({'status':'recording','message':'Listening · text appears as you speak','device':sd.query_devices(kind='input')['name']})
    while not stop.wait(.1) and time.monotonic()-began<60:
     count=sum(len(x) for x in chunks)
     if count-last<rate*1.2:continue
     wave=np.concatenate(chunks);segment=wave[offset:];last=count
     if len(segment)<rate*.4 or float(np.max(np.abs(segment)))<.003:continue
     stamp=time.monotonic();latest=decode(segment);latencies.append(time.monotonic()-stamp)
     if latest:
      partials+=1;first=first or time.monotonic()-began
      emit({'status':'recording','text':join_text(committed,latest),'partial':True,'revision':partials,'message':'Listening · review text before sending','partialSeconds':latencies[-1]})
     quiet=len(segment)>rate and float(np.sqrt(np.mean(segment[-8000:]**2)))<.004
     if quiet or len(segment)>=rate*10:
      committed=join_text(committed,latest);offset=max(offset,count-4000);latest=''
   wave=np.concatenate(chunks) if chunks else np.array([],np.float32);segment=wave[offset:]
   if len(segment)>rate*.35 and float(np.max(np.abs(segment)))>=.003:latest=decode(segment)
   text=join_text(committed,latest)
   if not text:raise ValueError('No speech detected. Check the microphone and try again.')
   emit({'status':'complete','text':text,'message':'Review or edit your text, then press Send.','device':'cuda','engine':'bark-pro','dtype':'bfloat16','duration':len(wave)/rate,'firstPartialSeconds':first,'partials':partials,'partialInferenceSeconds':latencies,'seconds':time.monotonic()-began,'peakAllocatedBytes':torch.cuda.max_memory_allocated(),'resident':'cuda','offline':True})
  except Exception as ex:emit({'status':'error','message':str(ex)[:1000]})
 for line in sys.stdin:
  try:
   r=json.loads(line);op=r.get('op')
   if op=='close':stop.set();break
   if op=='stop':stop.set();continue
   if thread and thread.is_alive():raise ValueError('Finish the current recording first.')
   if op=='live':stop.clear();thread=threading.Thread(target=live,daemon=True);thread.start()
   elif op=='transcribe':
    wave,rate=sf.read(r['audio'],dtype='float32',always_2d=True);wave=wave.mean(1)
    if rate!=16000:wave=soxr.resample(wave,rate,16000)
    if not 0<len(wave)<=16000*60 or not np.isfinite(wave).all():raise ValueError('Audio must be finite and at most 60 seconds.')
    stamp=time.monotonic();text=decode(wave)
    emit({'status':'complete','text':text,'transcribeSeconds':time.monotonic()-stamp,'peakAllocatedBytes':torch.cuda.max_memory_allocated(),'resident':'cuda','dtype':'bfloat16','offline':True})
   else:raise ValueError('Unsupported operation.')
  except Exception as ex:emit({'status':'error','message':str(ex)[:1000]})
if __name__=='__main__':
 try:main(Path(sys.argv[1]))
 except Exception as ex:emit({'status':'error','message':str(ex)[:1000]});sys.exit(1)
