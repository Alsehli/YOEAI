"""Disposable local-only inference subprocess; never executes generated C."""
import os,sys,json,time
sys.stdout.reconfigure(encoding='utf-8');sys.stdin.reconfigure(encoding='utf-8')
os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
import torch,psutil
from transformers import PreTrainedTokenizerFast,AutoModelForCausalLM
class FirstToken:
 def __init__(self):self.first=None;self.prompt=True
 def put(self,value):
  if self.prompt:self.prompt=False
  elif self.first is None:self.first=time.monotonic()
 def end(self):pass
start=time.monotonic();path,device=sys.argv[1:3];request=json.load(sys.stdin)
torch.set_num_threads(min(8,os.cpu_count() or 4))
tokenizer=PreTrainedTokenizerFast(tokenizer_file=os.path.join(path,'tokenizer.json'),bos_token='<｜begin▁of▁sentence｜>',eos_token='<｜end▁of▁sentence｜>')
assert tokenizer.eos_token_id==32014, 'Unexpected tokenizer identity'
code=request['code'];prompt='# This is the assembly code:\n'+code+'\n# What is the source code?\n'
inputs=tokenizer(prompt,return_tensors='pt');count=inputs.input_ids.shape[1];limit=min(int(request.get('maxTokens',384)),768)
if count+limit>4096:raise ValueError('Function exceeds the conservative 4096-token training window; choose a smaller function.')
if device=='cuda':
 free,total=torch.cuda.mem_get_info()
 if free<4800*1024**2:raise RuntimeError('Available VRAM changed; allocation stopped before loading. Retry to use CPU fallback.')
 torch.cuda.reset_peak_memory_stats()
else:
 if psutil.virtual_memory().available<7*1024**3:raise RuntimeError('CPU fallback needs at least 7 GiB available RAM.')
model=AutoModelForCausalLM.from_pretrained(path,local_files_only=True,trust_remote_code=False,use_safetensors=True,dtype=torch.float16 if device=='cuda' else torch.float32,attn_implementation='sdpa').to(device).eval()
loaded=time.monotonic();inputs={k:v.to(device) for k,v in inputs.items()}
streamer=FirstToken()
with torch.inference_mode():out=model.generate(**inputs,max_new_tokens=limit,do_sample=False,use_cache=True,streamer=streamer,pad_token_id=tokenizer.eos_token_id)
end=time.monotonic();generated=out[0,count:];text=tokenizer.decode(generated,skip_special_tokens=True)
print(json.dumps({'refined':text,'inputTokens':count,'outputTokens':len(generated),'loadSeconds':loaded-start,'generationSeconds':end-loaded,'timeToFirstTokenSeconds':streamer.first-loaded if streamer.first else None,'tokensPerSecond':len(generated)/max(.001,end-loaded),'peakCudaMiB':torch.cuda.max_memory_allocated()/1024**2 if device=='cuda' else 0,'peakRSSMiB':psutil.Process().memory_info().peak_wset/1024**2 if os.name=='nt' else psutil.Process().memory_info().rss/1024**2,'device':device,'truncated':len(generated)>=limit},ensure_ascii=False))
