"""Versioned Lite context migration and hash-verified app-local runtime support."""
import json,hashlib,shutil,time
from pathlib import Path

def install_runtime(payload,backend):
 source=Path(payload)/'RuntimeSupport';manifest=source/'runtime-files.json'
 if not manifest.is_file():return False
 entries=json.loads(manifest.read_text(encoding='utf8'))
 allowed={'MSVCP140.dll','MSVCP140_1.dll','MSVCP140_2.dll','VCRUNTIME140.dll','VCRUNTIME140_1.dll'}
 for entry in entries:
  name=entry['name']
  if name not in allowed:raise ValueError('Unexpected runtime support file')
  if hashlib.sha256((source/name).read_bytes()).hexdigest()!=entry['sha256']:raise ValueError('Runtime support integrity check failed: '+name)
 backend=Path(backend);backend.mkdir(parents=True,exist_ok=True)
 for entry in entries:shutil.copy2(source/entry['name'],backend/entry['name'])
 return True

def start_with_context_upgrade(config_path,data,start,stop):
 config_path=Path(config_path);data=Path(data);marker=data/'context-16k-migration.json'
 if marker.exists() or not config_path.exists():return start()
 previous=json.loads(config_path.read_text(encoding='utf-8-sig'))
 # An explicit existing large context must never be downgraded by old migration.
 if type(previous.get('context')) is int and previous['context']>=16384:return start()
 # A missing model is setup state, not evidence that 16K exhausted memory.
 if not Path(previous.get('model','')).is_file():return start()
 # Never alter the active engine underneath an already running window.
 state=data/'engine-state.json'
 if state.exists():
  import psutil
  pid=json.loads(state.read_text(encoding='utf8')).get('pid')
  if pid and psutil.pid_exists(pid):return start()
 backup=data/('profile-before-16k-'+str(time.time_ns())+'.json');shutil.copy2(config_path,backup)
 candidate=dict(previous,context=16384);config_path.write_text(json.dumps(candidate,indent=2),encoding='utf8')
 try:result=start()
 except Exception as error:
  try:stop()
  except Exception:pass
  recovery=dict(previous)
  if recovery.get('context',2048)>=16384:recovery['context']=8192
  config_path.write_text(json.dumps(recovery,indent=2),encoding='utf8')
  marker.write_text(json.dumps({'status':'recovered','requestedContext':16384,'context':recovery.get('context',2048),'error':str(error),'backup':str(backup)}),encoding='utf8')
  return start()
 marker.write_text(json.dumps({'status':'loaded','context':16384,'backup':str(backup)}),encoding='utf8');return result
