"""Model context declarations and conservative memory estimates, not fit guarantees."""
import functools,math
from pathlib import Path
MAX_CONTEXT=1048576
STEPS=(2048,4096,8192,16384,32768,49152,65536,98304,102400,131072,196608,262144,524288,1048576)
@functools.lru_cache(maxsize=16)
def _read(path,stamp,size):
 from gguf_metadata import inspect_model
 return inspect_model(path)
def model_info(path):
 p=Path(path);s=p.stat();return _read(str(p.resolve()),s.st_mtime_ns,s.st_size)
def dimensions(info):
 m=info['metadata'];a=str(m.get('general.architecture',''));get=lambda k,d=None:m.get(a+'.'+k,d)
 maximum=get('context_length');maximum=maximum if type(maximum)is int and maximum>=256 else None
 layers=int(get('block_count',0));mtp=int(get('nextn_predict_layers',0));layers=max(0,layers-mtp)
 return m,a,get,maximum,layers
def validate_context(path,value,info=None):
 if type(value)is not int or not 256<=value<=MAX_CONTEXT:raise ValueError('Choose a context between 256 and 1,048,576 tokens.')
 _,_,_,maximum,_=dimensions(info or model_info(path))
 if maximum is None:
  if value>16384:raise ValueError('This GGUF does not declare its context limit; extended context cannot be verified.')
 elif value>maximum:raise ValueError(f'This GGUF declares a {maximum:,}-token context limit. No automatic RoPE extension is applied.')
 return value
def cache_estimate(info,context):
 m,a,get,maximum,layers=dimensions(info)
 try:
  heads=get('attention.head_count');kv=get('attention.head_count_kv');embedding=int(get('embedding_length'))
  key=int(get('attention.key_length',embedding//heads if isinstance(heads,int) and heads else 0));value=int(get('attention.value_length',key))
  interval=get('full_attention_interval');recurrent=get('attention.recurrent_layers');hybrid=get('ssm.state_size') is not None
  if hybrid and not (isinstance(recurrent,list) or type(interval)is int and interval>0):return {'bytes':None,'reason':'Hybrid attention layout is not declared.'}
  full=[]
  for i in range(layers):
   if isinstance(recurrent,list):
    if len(recurrent)<layers:return {'bytes':None,'reason':'Incomplete recurrent layer metadata.'}
    if recurrent[i]:continue
   elif hybrid and (i+1)%interval:continue
   h=int(kv[i] if isinstance(kv,list) else kv)
   if h<1 or key<1 or value<1:raise ValueError()
   full.append((math.ceil(h*key/32)*34,math.ceil(h*value/32)*34))
  padded=math.ceil(context/256)*256
  return {'bytes':sum(k+v for k,v in full)*padded,'attentionLayers':len(full),'recurrentLayers':layers-len(full),'cacheType':'Q8_0','paddedTokens':padded,'kind':'estimate','note':'KV cache only; recurrent state, compute buffers, vision and runtime overhead need additional memory.'}
 except (ValueError,TypeError,ZeroDivisionError):return {'bytes':None,'reason':'Insufficient attention metadata for a safe cache estimate.'}
def capacity(info,requested,active=None,hardware=None,projector_bytes=0):
 _,_,_,maximum,layers=dimensions(info);limit=min(maximum or 16384,MAX_CONTEXT);options=sorted(set([x for x in STEPS if x<=limit]+[limit]+([requested] if type(requested)is int and 256<=requested<=limit else [])))
 result={'modelLimit':maximum,'runtimeSafetyLimit':MAX_CONTEXT,'requested':requested,'active':active,'options':options,'kv':cache_estimate(info,requested if type(requested)is int else 16384),'recommended':None,'estimateOnly':True}
 if hardware:
  gpu=hardware.get('gpu') or {};available=gpu.get('freeBytes',0);reserve=1536*1048576+projector_bytes
  # Prefer full-weight GPU residency. A loaded model's free VRAM cannot be used
  # to infer a fresh-load recommendation, so the caller labels that case.
  for n in options:
   estimate=cache_estimate(info,n)['bytes']
   if estimate is not None and info['sizeBytes']*1.12+reserve+estimate<=available:result['recommended']=n
 result['note']='Model limit is metadata, allocation is measured after loading; neither guarantees useful recall at the full length. Input + output share this context. GPU size alone does not determine capacity.'
 return result
