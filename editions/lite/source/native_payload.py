"""No-model native dependency preflight, independent of the host Python PATH."""
import json,subprocess
from pathlib import Path
def check(root):
 root=Path(root)
 worker=root/'NativeEngine/YOEAI-Inference.exe';runtime=root/'NativeRuntime/b11784'
 if not worker.is_file()or not(runtime/'runtime-manifest.json').is_file():raise ValueError('The complete bundled native runtime is missing; use the complete YOEAI installer.')
 r=subprocess.run([str(worker),'--probe',str(runtime)],capture_output=True,text=True,encoding='utf8',timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
 if r.returncode:raise ValueError('Native dependency check failed: '+r.stderr[-500:])
 result=json.loads(r.stdout)
 if not result.get('cuda'):raise ValueError('The native CUDA backend is unavailable. Check the NVIDIA driver.')
 return result
