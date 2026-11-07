"""Resource-aware native offload plans. Estimates are labelled and measured later."""
import os,subprocess
from pathlib import Path

def resources():
 import psutil
 mem=psutil.virtual_memory();out={'ramAvailableBytes':mem.available,'ramTotalBytes':mem.total,'gpu':None}
 try:
  raw=subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.total,memory.free','--format=csv,noheader,nounits'],text=True,timeout=5,creationflags=subprocess.CREATE_NO_WINDOW)
  name,total,free=raw.splitlines()[0].rsplit(',',2);out['gpu']={'name':name.strip(),'totalBytes':int(total)*1048576,'freeBytes':int(free)*1048576}
 except (OSError,ValueError,subprocess.SubprocessError):pass
 return out

def plans(path,context,projector=None):
 from gguf_metadata import inspect_model
 info=inspect_model(path);meta=info['metadata'];arch=meta.get('general.architecture');layers=int(meta.get(str(arch)+'.block_count',0))
 if not layers:raise ValueError('Cannot determine model layer count from GGUF metadata.')
 size=Path(path).stat().st_size;r=resources();available=(r['gpu']or{}).get('freeBytes',0)
 # Conservative headroom for desktop, context, recurrent state and compute buffers.
 reserve=1536*1048576+int(context)*131072;budget=max(0,available-reserve)
 estimate=int(size/(layers+1)*1.12);gpu_layers=min(layers+1,int(budget/max(1,estimate)))
 # Full offload was measured with these installed Qwen models. Still require
 # space for weights plus context/desktop headroom, and retain smaller retries.
 if available>=int(size*1.05)+reserve:gpu_layers=layers+1
 if size*.4>r['ramAvailableBytes']+max(0,available):raise ValueError('Insufficient available memory for the selected model; close other heavy applications.')
 choices=[]
 for n in (gpu_layers,max(0,gpu_layers-8),max(0,gpu_layers//2),0):
  if n not in choices:choices.append(n)
 return {'resources':r,'modelBytes':size,'layerCount':layers,'estimatedBytesPerLayer':estimate,'reserveBytes':reserve,'context':context,'gpuLayerAttempts':choices}
