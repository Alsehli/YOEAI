"""Single-model libllama engine, used only inside YOEAI's private worker."""
import codecs,ctypes as C,json,os,threading,time,uuid
from pathlib import Path
from .libllama import Library,Message,I
class Engine:
 def __init__(self,runtime):
  self.lib=Library(runtime);self.model=None;self.ctx=None;self.vocab=None;self.path=None;self.context=0;self.layers=0;self.vision=None;self.lock=threading.Lock()
 def close(self):
  if self.vision:self.vision.close();self.vision=None
  if self.ctx:self.lib.free(self.ctx);self.ctx=None
  if self.model:self.lib.model_free(self.model);self.model=None
  self.vocab=None;self.path=None
 def load(self,path,context=8192,layers=0,progress=None,cancel=None,projector=None):
  path=Path(path).resolve()
  if not path.is_file():raise ValueError('Selected GGUF file is missing: '+path.name)
  if not 256<=int(context)<=32768:raise ValueError('Native context must be between 256 and 32768 tokens.')
  if int(layers)>0 and self.lib.cuda_error:raise RuntimeError('CUDA initialization is unavailable: '+self.lib.cuda_error)
  self.close();started=time.monotonic();self.path=str(path)
  from .libllama import Progress
  def report(value,unused):
   if progress:progress(float(value))
   return not(cancel and cancel.is_set())
  self.callback=Progress(report);p=self.lib.model_default_params();p.n_gpu_layers=int(layers);p.progress_callback=self.callback;p.load_mtp=False
  self.model=self.lib.model_load_from_file(os.fsencode(path),p)
  if not self.model:self.close();raise RuntimeError('Native GGUF loading failed. See the worker log; no different model was substituted.')
  params=self.lib.context_default_params();params.n_ctx=int(context);params.n_batch=256;params.n_ubatch=128;params.n_seq_max=1;params.n_threads=params.n_threads_batch=min(8,os.cpu_count()or 4);params.flash_attn_type=1;params.type_k=params.type_v=8;params.no_perf=False
  self.ctx=self.lib.init_from_model(self.model,params)
  if not self.ctx:self.close();raise RuntimeError('Native context allocation failed. Retry the same file with less GPU offload or a smaller context.')
  self.vocab=self.lib.model_get_vocab(self.model);self.context=int(context);self.layers=int(layers)
  if projector:
   from .vision import Vision
   self.vision=Vision(self,projector)
  return {'vision':bool(self.vision),'model':str(path),'context':self.context,'gpuLayers':self.layers,'loadSeconds':time.monotonic()-started,'gpuSupported':bool(self.lib.supports_gpu_offload()),'transport':'private-stdio','runtime':'libllama b11784'}
 def tokenize(self,text):
  if not self.vocab:raise ValueError('Load a model before tokenizing.')
  return self.lib.tokenize_text(self.vocab,text)
 def prompt(self,messages):
  data=[]
  for m in messages:
   if m.get('role')not in ('system','user','assistant','tool'):raise ValueError('Unsupported chat role.')
   if not isinstance(m.get('content'),str):raise ValueError('Native image input is not enabled in this runtime build yet. No image was silently ignored.')
   data.append((m['role'].encode(),m['content'].encode('utf8')))
  if not data:raise ValueError('Chat messages are missing.')
  array=(Message*len(data))(*(Message(r,c)for r,c in data));template=self.lib.model_chat_template(self.model,None)
  out=C.create_string_buffer(65536);n=self.lib.chat_apply_template(template,array,len(array),True,out,len(out))
  if n<0:raise ValueError('Native chat template is unsupported; refusing to silently use another format.')
  if n>=len(out):out=C.create_string_buffer(n+1);n=self.lib.chat_apply_template(template,array,len(array),True,out,len(out))
  text=out.raw[:n].decode('utf8')
  # Qwen3.5 non-thinking assistant prefix, matching existing reasoning-off behavior.
  if '<|im_start|>assistant' in text and not text.endswith('</think>\n\n'):text+='<think>\n</think>\n\n'
  return text
 def generate(self,payload,cancel=None):
  if not self.lock.acquire(blocking=False):raise ValueError('The shared native model is busy.')
  sampler=None
  try:
   if not self.ctx:raise ValueError('Native model is not loaded.')
   if payload.get('tools'):raise ValueError('Native structured tool schema support is not enabled yet; no tool call was executed.')
   messages=payload.get('messages',[]);images=[]
   if any(isinstance(m.get('content'),list)for m in messages):
    if not self.vision:raise ValueError('The selected native model has no loaded vision projector.')
    messages,images=self.vision.prepare(messages)
   fmt=payload.get('response_format',{})
   if fmt.get('type')in ('json_object','json_schema'):
     from .structured import schema_instruction,response_schema,grammar_for
     spec=response_schema(fmt);gbnf=grammar_for(spec)
     messages=[{'role':'system','content':schema_instruction(spec)},*messages]
   text=self.prompt(messages);tokens=self.tokenize(text);limit=int(payload.get('max_tokens',512));limit=max(1,min(limit,8192))
   if len(tokens)+limit>self.context:raise ValueError('The request exceeds the selected native context. Reduce evidence or output length.')
   self.lib.memory_clear(self.lib.get_memory(self.ctx),True);start=time.monotonic()
   if images:
    count=self.vision.evaluate(text,images,limit,cancel);tokens=[0]*count
   for at in range(0,0 if images else len(tokens),256):
    if cancel and cancel.is_set():raise InterruptedError('Generation stopped.')
    values=(I*len(tokens[at:at+256]))(*tokens[at:at+256]);code=self.lib.decode(self.ctx,self.lib.batch_get_one(values,len(values)))
    if code:raise RuntimeError('Native prompt evaluation failed (code '+str(code)+').')
   sampler=self.lib.sampler_chain_init(self.lib.sampler_chain_default_params());temp=float(payload.get('temperature',.6))
   if payload.get('response_format',{}).get('type')in ('json_object','json_schema'):
    grammar=self.lib.sampler_init_grammar(self.vocab,gbnf.encode(),b'root')
    if not grammar:raise ValueError('Native JSON grammar could not initialize.')
    self.lib.sampler_chain_add(sampler,grammar)
   if temp<=0:self.lib.sampler_chain_add(sampler,self.lib.sampler_init_greedy())
   else:
    for part in (self.lib.sampler_init_top_k(40),self.lib.sampler_init_top_p(.95,1),self.lib.sampler_init_temp(temp),self.lib.sampler_init_dist(int(payload.get('seed',42)))):self.lib.sampler_chain_add(sampler,part)
   decoder=codecs.getincrementaldecoder('utf8')('replace');first=None;count=0;reason='length';ident='chatcmpl-'+uuid.uuid4().hex
   for _ in range(limit):
    if cancel and cancel.is_set():raise InterruptedError('Generation stopped.')
    token=self.lib.sampler_sample(sampler,self.ctx,-1)
    if self.lib.vocab_is_eog(self.vocab,token):reason='stop';break
    count+=1
    if first is None:first=time.monotonic()
    piece=decoder.decode(self.lib.piece(self.vocab,token))
    if piece:yield {'id':ident,'object':'chat.completion.chunk','choices':[{'index':0,'delta':{'content':piece},'finish_reason':None}]}
    value=(I*1)(token);code=self.lib.decode(self.ctx,self.lib.batch_get_one(value,1))
    if code:raise RuntimeError('Native decoding failed (code '+str(code)+').')
   tail=decoder.decode(b'',final=True)
   if tail:yield {'id':ident,'choices':[{'index':0,'delta':{'content':tail},'finish_reason':None}]}
   elapsed=time.monotonic()-start;gen=time.monotonic()-(first or start)
   prompt_seconds=(first or time.monotonic())-start
   yield {'id':ident,'choices':[{'index':0,'delta':{},'finish_reason':reason}],'usage':{'prompt_tokens':len(tokens),'completion_tokens':count,'total_tokens':len(tokens)+count},'timings':{'predicted_per_second':count/max(.001,gen),'predicted_ms':gen*1000,'prompt_per_second':len(tokens)/max(.001,prompt_seconds),'prompt_ms':prompt_seconds*1000,'total_ms':elapsed*1000}}
  finally:
   if sampler:self.lib.sampler_free(sampler)
   self.lock.release()
