"""Same-origin autonomy API. All state transitions validated by trusted Python."""
import json,threading,contextlib
from pathlib import Path
from configuration import APP_DIR
from update_manager import Manager,target
INSTANCE=None;LOCK=threading.Lock()
def manager(engine):
 global INSTANCE
 with LOCK:
  if INSTANCE is None:
   import update_native
   @contextlib.contextmanager
   def quiet():
    from mini_agents import GATE
    if not GATE.acquire(blocking=False):raise ValueError('Wait for the active shared-model request before deploying.')
    try:
     from model_modes import assert_idle
     assert_idle()
     yield
    finally:GATE.release()
   INSTANCE=Manager(engine.home,APP_DIR,APP_DIR/'UpdateRuntime',health=update_native.health,approval=update_native.approve,lease=quiet);INSTANCE.start_scheduler(engine)
 return INSTANCE
def stage_code(engine,m,tid):
 t=engine.get(tid)
 if t['agent']!='code' or not t.get('patch') or t['status']!='WAITING_FOR_APPROVAL':raise ValueError('Choose a Code YOE task with an unapplied exact patch preview.')
 from mini_agents import scoped,clean_root,digest
 p=t['patch'];engine.check_patch(t,p);f=scoped(clean_root(t['project']),p['path']);relative=f.resolve().relative_to(m.root).as_posix();target(m.root,relative)
 original=f.read_bytes()
 if digest(original)!=t['snapshots'][p['path']]['sha256']:raise ValueError('Source changed after Code YOE inspected it.')
 return m.stage({relative:original.decode('utf-8-sig').replace(p['find'],p['replace'],1)},tid)
def dispatch(handler,engine,body,post):
 path=handler.path.split('?',1)[0];m=manager(engine);value=None
 if not post and path=='/mini/update/state':
  from urllib.parse import urlsplit,parse_qs
  selected=parse_qs(urlsplit(handler.path).query).get('selected',[None])[0];jobs=m.jobs()
  detail=None
  if selected:
   try:detail=m.get(selected);detail['explanation']=m.explanation(detail)
   except ValueError:pass
  summaries=[{k:r.get(k) for k in ['id','status','created','updated','digest','error']} for r in jobs]
  value={'jobs':summaries,'selected':detail,'schedule':m.setting(),'runtimeReady':m.manifest(),'isolation':'Windows AppContainer; no network capabilities; 512 MiB; 20% CPU; 30-second tests','scope':'Existing unprotected UI text resources only. Executables, dependencies, policy, models and databases are blocked.'}
 elif path.startswith('/mini/update/acquire'):
  from update_acquire import Acquisition
  a=Acquisition(m)
  if not post and path=='/mini/update/acquire':value=a.list()
  elif post and path=='/mini/update/acquire/download':value=a.download(body)
  elif post and path=='/mini/update/acquire/install':value=a.install(body)
  elif post and path=='/mini/update/acquire/rollback':value=a.rollback(body)
  else:raise ValueError('Unknown acquisition action.')
 elif post and path=='/mini/update/scan':
  value=engine.create({'agent':'update','auditOnly':True,'updateParent':body.get('updateParent'),'objective':'Can you improve anything? Perform the authorized read-only YOEAI health audit, cite real evidence and distinguish missing checks. Prepare scoped Code YOE follow-ups only for confirmed findings. No production change or external network is approved.'})
 elif post and path=='/mini/update/stage':
  if body.get('approve') is not True:raise ValueError('Approve staging this explicit source or file content.')
  value=stage_code(engine,m,body.get('codeTask')) if body.get('codeTask') else m.stage(body.get('files'))
 elif post and path=='/mini/update/schedule':value=m.schedule(body)
 elif post and path=='/mini/update/stop':
  value=m.stop()
  for parent in engine.tasks():
   if parent.get('healthAudit'):parent['auditFollowupsStopped']=True;engine.save(parent)
  for t in engine.tasks():
   if (t['agent']=='update' or t.get('auditOrigin')) and t['status'] in {'QUEUED','PLANNING','RUNNING','WAITING_FOR_APPROVAL'}:engine.cancel(t['id'])
 elif post and path=='/mini/update/test':value=m.start_test(body.get('id'),body)
 elif post and path=='/mini/update/deploy':value=m.deploy(body.get('id'),body)
 elif post and path=='/mini/update/restore':value=m.rollback(body.get('id'),body)
 elif post and path=='/mini/update/reject':value=m.reject(body.get('id'))
 else:handler.json(404,{'error':'Unknown or prohibited update operation.'});return True
 handler.json(200,value);return True

def route(handler,engine,body,post):
 try:return dispatch(handler,engine,body,post)
 except ValueError as error:
  if handler.path.split('?')[0]=='/mini/update/stage' and isinstance(body.get('files'),dict) and INSTANCE is not None:
   denied=INSTANCE.denied_stage(body,error)
   handler.json(400,{'error':str(error),'rejectedCandidate':denied['id']});return True
  if INSTANCE is not None:
   with contextlib.suppress(Exception):INSTANCE.audit('denied','Request denied: '+handler.path.split('?')[0][:150]+' — '+str(error)[:300])
  raise
