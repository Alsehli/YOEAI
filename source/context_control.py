"""Controlled restart adapter for the existing, explicitly configured local engine."""
import json,os,subprocess,time
from pathlib import Path
import runtime
from configuration import APP_DIR,CONFIG_FILE,HOME,read_config

def change_context(context,confirmed):
 if type(context) is not int or context not in (4096,8192,16384):raise ValueError('Choose 4096, 8192 or 16384 tokens.')
 if confirmed is not True:raise ValueError('Confirm the shared engine restart before changing context.')
 if Path(os.environ.get('YOEAI_ENGINE_STARTER','')).resolve()!=Path('C:/AI/llama.cpp/start-deepseek.ps1').resolve():raise ValueError('This shared engine has no approved context controller. Use its own launcher.')
 with runtime.LOCK:
  script=APP_DIR/'switch_context.ps1'
  logs=HOME/'Logs';logs.mkdir(exist_ok=True)
  with (logs/f'context-controller-{time.time_ns()}.log').open('w+',encoding='utf-8') as output:
   result=subprocess.run(['powershell.exe','-NoProfile','-File',str(script),'-Context',str(context),'-ProfilePath',str(CONFIG_FILE)],stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,text=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=420)
   output.flush();output.seek(0);message=output.read()
  if result.returncode:raise RuntimeError(message.strip()[-1800:] or 'Context restart failed; check the engine logs.')
  return {'status':'ok','context':context}
