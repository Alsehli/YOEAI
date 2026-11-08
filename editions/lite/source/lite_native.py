"""Lite's existing Q4 model, loaded through the shared private native worker."""

import json,threading

from pathlib import Path

from native_ai.manager import INSTANCE

LOCK=threading.RLock()

PROFILE_LOCK=None



def acquire_profile(home):

 global PROFILE_LOCK

 import msvcrt

 handle=Path(home,'desktop-native.lock').open('a+b')

 handle.seek(0);handle.write(b'0');handle.flush();handle.seek(0)

 try:msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)

 except OSError:handle.close();return False

 PROFILE_LOCK=handle;return True



def initialize(app,home,config):

 import configuration

 configuration.bind(home,app,config)



def healthy():

 return bool(INSTANCE.state['loaded'])



def start(app,home,config):

 initialize(app,home,config)

 from native_ai.resources import plans

 c=config();model=Path(c['model']).resolve();projector=Path(c['projector']).resolve() if c.get('projector') else None

 if not model.is_file() or (projector and not projector.is_file()):raise ValueError('The existing Lite model or vision file is missing. Reconnect its drive; no download was started.')

 with LOCK:

  if INSTANCE.state['busy']:raise ValueError('Stop the current local task before changing its model context.')

  if INSTANCE.worker and INSTANCE.worker.poll()is None and INSTANCE.state['loaded']and INSTANCE.state.get('context')==c['context']and INSTANCE.state.get('model')==str(model):return

  if INSTANCE.worker:list(INSTANCE.request('unload'))

  profile=plans(model,c['context'],projector);errors=[]

  for layers in profile['gpuLayerAttempts']:

   try:

    INSTANCE.start();list(INSTANCE.request('load',runtime=str(INSTANCE.runtime),model=str(model),context=c['context'],layers=layers,projector=str(projector) if projector else None));break

   except Exception as e:

    errors.append(str(e));INSTANCE.close()

    if not any(x in str(e).lower()for x in ('alloc','memory','cuda','worker closed')):raise

  else:raise ValueError('The Lite model could not load safely: '+errors[-1])

  INSTANCE.state['resourcePlan']=profile

  Path(home,'engine-state.json').write_text(json.dumps(INSTANCE.state,indent=2),encoding='utf8')



def stop():

 with LOCK:INSTANCE.close()



def shutdown():INSTANCE.shutdown()
