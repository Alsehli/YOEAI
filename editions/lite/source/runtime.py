"""Read-only health adapter for the existing Lite engine."""
import json,subprocess,urllib.request
def healthy(port=None):
 from lite_native import healthy as native_healthy
 return native_healthy()

def gpu_status():
 try:
  p=subprocess.run(['nvidia-smi','--query-gpu=memory.used,memory.total,utilization.gpu,temperature.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=5,creationflags=subprocess.CREATE_NO_WINDOW)
  used,total,util,temp=map(float,p.stdout.splitlines()[0].split(','))
  return dict(used=used,total=total,util=util,temp=temp)
 except Exception:return {}
