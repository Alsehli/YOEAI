"""Direct libllama ABI bindings for bundled llama.cpp b11784 (Windows x64).

No sockets, model server or downloaded weights. Keep this ABI paired with the
verified runtime manifest; never load an arbitrary DLL found on PATH.
"""
import ctypes as C
import os
from pathlib import Path
P=C.c_void_p; I=C.c_int32; U=C.c_uint32; F=C.c_float; B=C.c_bool
Progress=C.CFUNCTYPE(B,F,P)
class ModelParams(C.Structure):
 _fields_=[('devices',P),('tensor_buft_overrides',P),('n_gpu_layers',I),('split_mode',I),('load_mode',I),('lazy_mode',I),('main_gpu',I),('tensor_split',P),('progress_callback',Progress),('progress_callback_user_data',P),('kv_overrides',P)]+[(x,B)for x in ('vocab_only','check_tensors','use_extra_bufts','no_host','no_alloc','load_mtp')]
class ContextParams(C.Structure):
 _fields_=[(x,U)for x in ('n_ctx','n_batch','n_ubatch','n_seq_max','n_rs_seq','n_outputs_max','n_outputs_max_per_seq')]+[(x,I)for x in ('n_threads','n_threads_batch','ctx_type','rope_scaling_type','pooling_type','attention_type','flash_attn_type')]+[(x,F)for x in ('rope_freq_base','rope_freq_scale','yarn_ext_factor','yarn_attn_factor','yarn_beta_fast','yarn_beta_slow')]+[('yarn_orig_ctx',U),('defrag_thold',F),('cb_eval',P),('cb_eval_user_data',P),('type_k',I),('type_v',I),('moe_cache_size',C.c_size_t),('abort_callback',P),('abort_callback_data',P)]+[(x,B)for x in ('embeddings','offload_kqv','no_perf','op_offload','swa_full','kv_unified')]+[('samplers',P),('n_samplers',C.c_size_t),('ctx_other',P)]
class Batch(C.Structure):
 _fields_=[('n_tokens',I),('token',C.POINTER(I)),('embd',P),('pos',P),('n_seq_id',P),('seq_id',P),('logits',P)]
class Message(C.Structure):_fields_=[('role',C.c_char_p),('content',C.c_char_p)]
class ChainParams(C.Structure):_fields_=[('no_perf',B)]
class Library:
 def __init__(self,directory):
  self.directory=Path(directory).resolve()
  if os.name!='nt':raise RuntimeError('This native runtime package targets Windows x64.')
  from .integrity import verify
  self.manifest=verify(self.directory)
  self.search=os.add_dll_directory(str(self.directory))
  self.cuda_dependencies=[]
  self.cuda_error=None
  try:
   for name in ('cudart64_13.dll','cublasLt64_13.dll','cublas64_13.dll','ggml-cuda.dll'):self.cuda_dependencies.append(C.CDLL(str(self.directory/name)))
  except OSError as ex:self.cuda_error=str(ex)
  self.dll=C.CDLL(str(self.directory/'llama.dll'))
  def bind(name,restype,args):
   f=getattr(self.dll,name);f.restype=restype;f.argtypes=args;setattr(self,name.removeprefix('llama_'),f)
  signatures=[('n_ctx',U,[P]),('model_n_ctx_train',U,[P]),('backend_init',None,[]),('backend_free',None,[]),('model_default_params',ModelParams,[]),('context_default_params',ContextParams,[]),('model_load_from_file',P,[C.c_char_p,ModelParams]),('model_free',None,[P]),('init_from_model',P,[P,ContextParams]),('free',None,[P]),('model_get_vocab',P,[P]),('model_chat_template',C.c_char_p,[P,C.c_char_p]),('get_memory',P,[P]),('memory_clear',None,[P,B]),('tokenize',I,[P,C.c_char_p,I,C.POINTER(I),I,B,B]),('token_to_piece',I,[P,I,C.c_char_p,I,I,B]),('vocab_is_eog',B,[P,I]),('batch_get_one',Batch,[C.POINTER(I),I]),('decode',I,[P,Batch]),('chat_apply_template',I,[C.c_char_p,C.POINTER(Message),C.c_size_t,B,C.c_char_p,I]),('sampler_chain_default_params',ChainParams,[]),('sampler_chain_init',P,[ChainParams]),('sampler_chain_add',None,[P,P]),('sampler_init_grammar',P,[P,C.c_char_p,C.c_char_p]),('sampler_init_greedy',P,[]),('sampler_init_top_k',P,[I]),('sampler_init_top_p',P,[F,C.c_size_t]),('sampler_init_temp',P,[F]),('sampler_init_dist',P,[U]),('sampler_sample',I,[P,P,I]),('sampler_accept',None,[P,I]),('sampler_free',None,[P]),('supports_gpu_offload',B,[])]
  for name,result,args in signatures:bind('llama_'+name,result,args)
  self.ggml=C.CDLL(str(self.directory/'ggml.dll'))
  load=self.ggml.ggml_backend_load_all_from_path;load.argtypes=[C.c_char_p];load.restype=None;load(os.fsencode(self.directory))
  self.backend_init()
 def tokenize_text(self,vocab,text):
  data=text.encode('utf8');n=self.tokenize(vocab,data,len(data),None,0,True,True)
  if n>=0:return []
  out=(I*(-n))();n=self.tokenize(vocab,data,len(data),out,len(out),True,True)
  if n<0:raise RuntimeError('Native tokenizer buffer mismatch.')
  return list(out[:n])
 def piece(self,vocab,token):
  out=C.create_string_buffer(256);n=self.token_to_piece(vocab,token,out,len(out),0,False)
  if n<0:out=C.create_string_buffer(-n);n=self.token_to_piece(vocab,token,out,len(out),0,False)
  return out.raw[:n]
