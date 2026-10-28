"""One real MOSS-Image inference job in its dedicated CUDA environment.

Only reviewed, hash-pinned local pipeline code is loaded. The official tensor math,
weights, scheduler and VAE are unchanged; component placement fits a 16 GB GPU.
"""
import os,sys,json,time,hashlib,importlib.util,threading,gc,ctypes,traceback
from pathlib import Path

request=json.loads(Path(sys.argv[1]).read_text(encoding='utf8'));output=Path(request['output']);progress=output.with_suffix('.progress.json');started=time.perf_counter();lock=threading.Lock();state={};stop=threading.Event();peaks={'peakProcessRssBytes':0,'peakSystemRamUsedBytes':0,'peakGpuUsedBytes':0};phase='loading'

def report(**values):
 with lock:
  state.update(values);temp=progress.with_suffix('.tmp');temp.write_text(json.dumps(state,ensure_ascii=False),encoding='utf8')
  for attempt in range(100):
   try:temp.replace(progress);break
   except PermissionError:
    if attempt==99:raise
    time.sleep(.02)

try:
 os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_DATASETS_OFFLINE='1')
 import torch,psutil,diffusers,transformers,accelerate,safetensors
 from accelerate import cpu_offload
 torch.set_num_threads(6)
 if not torch.cuda.is_available():raise RuntimeError('The dedicated MOSS environment has no working CUDA GPU.')
 torch.cuda.set_per_process_memory_fraction(.88,0);torch.cuda.reset_peak_memory_stats()
 class Memory(ctypes.Structure):_fields_=[('total',ctypes.c_ulonglong),('free',ctypes.c_ulonglong),('used',ctypes.c_ulonglong)]
 nvml=None;handle=ctypes.c_void_p()
 try:
  nvml=ctypes.WinDLL('nvml.dll');nvml.nvmlInit_v2();nvml.nvmlDeviceGetHandleByIndex_v2(0,ctypes.byref(handle))
 except (OSError,AttributeError):nvml=None
 process=psutil.Process()
 def monitor():
  while not stop.wait(.2):
   peaks['peakProcessRssBytes']=max(peaks['peakProcessRssBytes'],process.memory_info().rss)
   peaks['peakSystemRamUsedBytes']=max(peaks['peakSystemRamUsedBytes'],psutil.virtual_memory().used)
   if nvml:
    memory=Memory()
    if nvml.nvmlDeviceGetMemoryInfo(handle,ctypes.byref(memory))==0:peaks['peakGpuUsedBytes']=max(peaks['peakGpuUsedBytes'],memory.used)
 threading.Thread(target=monitor,daemon=True).start()
 model=Path(request['modelDirectory']);approval=json.loads(Path(request['approval']).read_text(encoding='utf8'))
 if approval.get('approved') is not True or approval.get('revision')!=request['revision']:raise RuntimeError('MOSS pipeline code has not been approved at this revision.')
 for item in approval['files']:
  if hashlib.sha256((model/item['file']).read_bytes()).hexdigest()!=item['sha256']:raise RuntimeError('Reviewed pipeline code changed: '+item['file'])
 spec=importlib.util.spec_from_file_location('yoeai_reviewed_moss',model/'pipeline_moss_image.py');module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
 report(phase='loading',message='Loading verified local MOSS components into system RAM…')
 pipe=module.MOSSImagePipeline.from_components_pretrained(str(model/'transformer'),str(model/'text_encoder'),str(model/'vae'),torch_dtype=torch.bfloat16,vae_dtype=torch.float32,local_files_only=True)
 # Transformers 5.3 can omit the standalone local template for Qwen2Tokenizer.
 # Use the exact reviewed template included in this pinned model bundle.
 from transformers import AutoTokenizer
 pipe.tokenizer=AutoTokenizer.from_pretrained(str(model/'tokenizer'),local_files_only=True)
 if not pipe.tokenizer.chat_template:pipe.tokenizer.chat_template=(model/'tokenizer/chat_template.jinja').read_text(encoding='utf8')
 pipe.scheduler=module.MOSSImageScheduler.from_config(json.loads((model/'scheduler/scheduler_config.json').read_text(encoding='utf8')))
 # Qwen3.5's 9B text encoder exceeds 16 GB by itself. Supported Accelerate
 # sequential offload brings complete decoder layers onto CUDA only while used.
 report(phase='encode',message='Encoding prompt with CPU-to-GPU text-encoder offloading…')
 for text in [request['prompt'],request.get('negativePrompt','')]:
  formatted=pipe.tokenizer.apply_chat_template([{'role':'user','content':text}],tokenize=False,add_generation_prompt=True,enable_thinking=True)
  if not pipe.tokenizer(formatted)['input_ids']:raise ValueError('The installed MOSS tokenizer produced no tokens. Generation is blocked.')
  if len(pipe.tokenizer(formatted)['input_ids'])>4096:raise ValueError('The formatted prompt exceeds MOSS’s supported 4,096-token limit. Shorten it before generating.')
 cpu_offload(pipe.text_encoder,execution_device=torch.device('cuda:0'),offload_buffers=True,preload_module_classes=['Qwen3_5DecoderLayer','Qwen3_5VisionBlock'])
 # Tell Diffusers that only the text encoder participates in offload-device
 # discovery; otherwise another CPU component can make it infer a meta device.
 pipe._exclude_from_cpu_offload=['transformer','vae']
 with torch.inference_mode():
  positive,positive_mask=pipe.encode_prompt(request['prompt'])
  negative,negative_mask=pipe.encode_prompt(request.get('negativePrompt',''))
 pipe.register_modules(text_encoder=None,tokenizer=None)
 gc.collect();torch.cuda.empty_cache()
 report(phase='load-diffusion',message='Text encoder offloaded. Loading image transformer on CUDA…')
 pipe.transformer.to('cuda:0');pipe.vae.to('cuda:0');load_seconds=time.perf_counter()-started
 steps=request.get('steps',50);original=pipe.progress_bar
 def progress_bar(items):
  for index,timestep in enumerate(items):
   report(phase='denoise',step=index+1,steps=steps,message=f'Creating Design locally · step {index+1} of {steps}')
   yield timestep
  report(phase='decode',message='Decoding the actual image…')
 pipe.progress_bar=progress_bar
 begin=time.perf_counter()
 with torch.inference_mode():
  image=pipe(prompt_embeds=positive,prompt_attention_mask=positive_mask,negative_prompt_embeds=negative,negative_prompt_attention_mask=negative_mask,height=request['height'],width=request['width'],num_inference_steps=steps,guidance_scale=request.get('guidance',3.0),uncond_skip_layers=[22],generator=torch.Generator('cpu').manual_seed(request['seed'])).images[0]
 torch.cuda.synchronize();generation_seconds=time.perf_counter()-begin
 temp=output.with_suffix('.tmp.png');image.save(temp,format='PNG');temp.replace(output)
 from PIL import Image
 with Image.open(output) as saved:saved.verify()
 metrics={**peaks,'generationSeconds':round(generation_seconds,3),'loadAndEncodeSeconds':round(load_seconds,3),'totalWorkerSeconds':round(time.perf_counter()-started,3),'peakTorchAllocatedBytes':torch.cuda.max_memory_allocated(),'peakTorchReservedBytes':torch.cuda.max_memory_reserved(),'width':image.width,'height':image.height,'steps':steps,'guidance':request.get('guidance',3.0),'seed':request['seed'],'outputBytes':output.stat().st_size,'outputSha256':hashlib.sha256(output.read_bytes()).hexdigest(),'modelRevision':request['revision'],'memoryMode':'Sequential CPU offload for text encoder; release it before resident BF16 DiT + FP32 VAE','versions':{'torch':torch.__version__,'cuda':torch.version.cuda,'diffusers':diffusers.__version__,'transformers':transformers.__version__,'accelerate':accelerate.__version__,'safetensors':safetensors.__version__},'device':torch.cuda.get_device_name(0)}
 output.with_suffix('.json').write_text(json.dumps(metrics,indent=2),encoding='utf8');report(phase='complete',message='Actual MOSS image saved.',metrics=metrics);print(json.dumps(metrics),flush=True)
except Exception as e:
 report(phase='error',message=str(e),error=str(e));traceback.print_exc();sys.exit(1)
finally:stop.set()
