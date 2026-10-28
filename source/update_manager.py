"""Deterministic, bounded Update YOE transactions. No LLM command executor.
Existing UI text resources only; executable, policy, model and database updates denied.
"""
import contextlib,difflib,hashlib,json,os,secrets,sqlite3,threading,time,uuid
from pathlib import Path,PurePosixPath
import update_sandbox
VERSION=1
PROTECTED={'assets/update-autonomy.js','assets/update-yoe.js','assets/mini-yoe.js','assets/windows-yoe.js','assets/code-preview.js','assets/read-aloud.js','assets/image-generation.js','assets/model-modes.js'}
PHASES={'TESTING','PENDING_NATIVE_APPROVAL','DEPLOYING','VERIFYING'}
def sha(data):return hashlib.sha256(data).hexdigest()
def atom(path,data):
 temp=path.with_name(path.name+'.yoe-stage-'+uuid.uuid4().hex);
 with temp.open('wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
 if os.name=='nt' and path.exists():
  import ctypes
  kernel=ctypes.WinDLL('kernel32',use_last_error=True);kernel.ReplaceFileW.argtypes=[ctypes.c_wchar_p,ctypes.c_wchar_p,ctypes.c_wchar_p,ctypes.c_uint,ctypes.c_void_p,ctypes.c_void_p]
  if not kernel.ReplaceFileW(str(path),str(temp),None,0,None,None):raise ctypes.WinError(ctypes.get_last_error())
 else:os.replace(temp,path)
def reject_link(path):
 for x in [path,*path.parents]:
  if x.is_symlink() or (os.name=='nt' and x.exists() and x.lstat().st_file_attributes&0x400):raise ValueError('Linked or redirected update targets are blocked.')
def target(root,name):
 if not isinstance(name,str) or '\\' in name or ':' in name or len(name)>200:raise ValueError('Invalid update path.')
 p=PurePosixPath(name)
 if p.is_absolute() or any(x in {'','..','.'} or x.startswith('.') for x in p.parts):raise ValueError('Invalid update path.')
 if name in PROTECTED or not (name=='ui.html' or name.startswith('assets/') and p.suffix in {'.css','.js','.html'}):raise ValueError('Only existing, unprotected UI text resources may be deployed. Executables, policy, dependencies, models and databases require a separate trusted release.')
 if any(x in name.lower() for x in ['update-yoe','update-fox','design-engine','worker','permissions','security','trust','vendor/']):raise ValueError('Updater, security and executable resources are protected.')
 f=root/name;reject_link(f)
 if not f.is_file() or not f.resolve().is_relative_to(root.resolve()) or f.stat().st_size>300000:raise ValueError('Target must be an existing UI text file under 300 KB.')
 return f
class Manager:
 def __init__(self,home,root,runtime,health=None,approval=None,sandbox=None,lease=None):
  self.home=Path(home)/'UpdateYOE';self.home.mkdir(parents=True,exist_ok=True);self.root=Path(root).resolve();self.runtime=Path(runtime);self.db=self.home/'improvements.sqlite3';self.lock=threading.RLock();self.execution_lock=threading.Lock();self.events={};self.workers={};self.health=health or (lambda:False);self.approval=approval or (lambda record,cancel:False);self.sandbox=sandbox or update_sandbox.run;self.closed=False;self.lease=lease or contextlib.nullcontext
  with self.connect() as db:db.executescript('CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,data TEXT NOT NULL); CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY,job TEXT,data TEXT,previous TEXT,hash TEXT); CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,data TEXT); PRAGMA user_version=1;')
  self.verify_audit();self.recover()
 @contextlib.contextmanager
 def connect(self):
  db=sqlite3.connect(self.db,timeout=15)
  try:
   with db:yield db
  finally:db.close()
 def save(self,r,message):
  r['updated']=time.time()
  with self.lock,self.connect() as db:
   db.execute('INSERT OR REPLACE INTO jobs VALUES(?,?)',(r['id'],json.dumps(r)))
   prev=db.execute('SELECT hash FROM events ORDER BY seq DESC LIMIT 1').fetchone();previous=prev[0] if prev else '0'*64
   text=json.dumps({'time':time.time(),'status':r['status'],'message':message},sort_keys=True);digest=sha((previous+r['id']+text).encode())
   db.execute('INSERT INTO events(job,data,previous,hash) VALUES(?,?,?,?)',(r['id'],text,previous,digest))
 def audit(self,job,message):
  with self.lock,self.connect() as db:
   row=db.execute('SELECT hash FROM events ORDER BY seq DESC LIMIT 1').fetchone();prev=row[0] if row else '0'*64
   text=json.dumps({'time':time.time(),'message':message},sort_keys=True);db.execute('INSERT INTO events(job,data,previous,hash) VALUES(?,?,?,?)',(job,text,prev,sha((prev+job+text).encode())))
 def verify_audit(self):
  previous='0'*64
  with self.connect() as db:
   for job,text,prev,digest in db.execute('SELECT job,data,previous,hash FROM events ORDER BY seq'):
    if prev!=previous or digest!=sha((prev+job+text).encode()):raise ValueError('Update audit integrity check failed. Autonomous operations are blocked.')
    previous=digest
 def get(self,jid):
  if not isinstance(jid,str) or len(jid)!=32:raise ValueError('Invalid improvement reference.')
  with self.connect() as db:r=db.execute('SELECT data FROM jobs WHERE id=?',(jid,)).fetchone()
  if not r:raise ValueError('Improvement not found.')
  return json.loads(r[0])
 def jobs(self):
  with self.connect() as db:return [json.loads(r[0]) for r in db.execute('SELECT data FROM jobs ORDER BY rowid DESC LIMIT 100')]
 def setting(self):
  with self.connect() as db:r=db.execute("SELECT data FROM settings WHERE key='schedule'").fetchone()
  return json.loads(r[0]) if r else {'enabled':False,'intervalMinutes':60,'cpuLimit':40,'nextRun':None,'lastTask':None}
 def schedule(self,body):
  with self.lock:return self._schedule(body)
 def _schedule(self,body):
  if body.get('approve') is not True or type(body.get('enabled'))!=bool:raise ValueError('Explicit approval of background scheduling is required.')
  minutes=body.get('intervalMinutes',60);cpu=body.get('cpuLimit',40)
  if type(minutes)!=int or not 15<=minutes<=1440 or type(cpu)!=int or not 10<=cpu<=70:raise ValueError('Schedule must be 15–1,440 minutes with a 10–70% CPU idle threshold.')
  value={**self.setting(),'enabled':body['enabled'],'intervalMinutes':minutes,'cpuLimit':cpu,'nextRun':time.time()+minutes*60}
  with self.connect() as db:db.execute("INSERT OR REPLACE INTO settings VALUES('schedule',?)",(json.dumps(value),))
  self.audit('schedule','User approved schedule configuration: '+json.dumps(value,sort_keys=True))
  return value
 def stage(self,files,task=None):
  if not isinstance(files,dict) or not 1<=len(files)<=8:raise ValueError('Stage one to eight existing UI text files.')
  if sum(len(v) for v in files.values() if isinstance(v,str))>80000:raise ValueError('Candidate exceeds the 80,000-character limit.')
  jid=uuid.uuid4().hex;folder=self.home/'Candidates'/jid;folder.mkdir(parents=True);items=[]
  for index,(name,text) in enumerate(sorted(files.items())):
   f=target(self.root,name)
   if not isinstance(text,str) or not text.strip() or '\x00' in text:raise ValueError('Candidate must contain valid nonempty text.')
   from mini_agents import reject_secrets
   reject_secrets(text)
   before=f.read_bytes();after=text.encode('utf8')
   if before==after:raise ValueError('Candidate contains no change.')
   old=before.decode('utf-8-sig');diff=''.join(difflib.unified_diff(old.splitlines(True),text.splitlines(True),fromfile=name,tofile=name))
   atom(folder/(str(index)+'.before'),before);atom(folder/(str(index)+'.after'),after)
   items.append({'path':name,'before':sha(before),'after':sha(after),'index':index,'diff':diff[:60000]})
  digest=sha(json.dumps(items,sort_keys=True).encode());r={'id':jid,'task':task,'created':time.time(),'status':'STAGED','files':items,'digest':digest,'test':None,'nonce':None,'error':None,'history':[]};self.save(r,'Candidate staged; production untouched.');return r
 def material(self,r,item,which):
  f=self.home/'Candidates'/r['id']/(str(item['index'])+'.'+which);reject_link(f);data=f.read_bytes()
  if sha(data)!=item[which]:raise ValueError('Staged candidate or recovery file changed. Operation blocked.')
  return data
 def manifest(self,force=False):
  if not force and getattr(self,'_runtimeChecked',0)>time.monotonic()-30:return self._runtimeValid
  from update_runtime_trust import MANIFEST_SHA256
  valid=False
  try:
   manifest=self.runtime/'runtime-manifest.json';raw=manifest.read_bytes()
   if sha(raw)!=MANIFEST_SHA256:return False
   info=json.loads(raw);items=info.get('files',[])
   if not isinstance(items,list) or not 1<=len(items)<=2000:return False
   for item in items:
    name=item['path']
    if not isinstance(name,str) or '\\' in name or ':' in name:return False
    rel=PurePosixPath(name)
    if rel.is_absolute() or '..' in rel.parts:return False
    f=self.runtime/str(rel);reject_link(f)
    if not f.resolve().is_relative_to(self.runtime.resolve()) or not f.is_file() or f.stat().st_size>32*1024**2 or sha(f.read_bytes())!=item['sha256']:return False
   valid=(self.runtime/'python.exe').is_file()
   return valid
  except (OSError,ValueError,TypeError,KeyError):return False
  finally:self._runtimeChecked=time.monotonic();self._runtimeValid=valid

 def start_test(self,jid,body):
  r=self.get(jid)
  if body.get('approve') is not True or body.get('digest')!=r['digest'] or r['status'] not in {'STAGED','TEST_FAILED','TEST_PASSED','CANCELLED'}:raise ValueError('Review and approve the exact candidate before isolated tests.')
  if not self.manifest(force=True):raise ValueError('Bundled isolated Python runtime is absent or changed. Execution blocked.')
  tests=body.get('tests','')
  if not isinstance(tests,str) or not 1<=len(tests)<=16000:raise ValueError('Provide explicit Python assertions to run in isolation.')
  files={'test_main.py':tests}
  # Text candidates are data inside the sandbox, never imported on the host.
  for index,item in enumerate(r['files']):files['candidate_'+str(index)+'.py']='CONTENT = '+repr(self.material(r,item,'after').decode('utf8'))+'\n'
  self.events[jid]=threading.Event();r.update(status='TESTING',test=None,nonce=None);self.save(r,'Starting isolated test with reviewed assertions.');self.spawn(jid,self.test_worker,files);return r
 def spawn(self,jid,fn,*args):
  worker=threading.Thread(target=self.guard,args=(jid,fn,args),daemon=True,name='UpdateYOE-'+jid[:6]);self.workers[jid]=worker;worker.start()
 def guard(self,jid,fn,args):
  if not self.execution_lock.acquire(blocking=False):
   r=self.get(jid);r.update(status='FAILED',error='Another Update YOE test or transaction is active. Retry when idle.');self.save(r,r['error']);return
  try:fn(jid,*args)
  except Exception as ex:
   r=self.get(jid)
   if r['status'] in {'DEPLOYING','VERIFYING'}:
    try:self.restore(r,'Automatic rollback after transaction error: '+str(ex));return
    except Exception as rollback:r.update(status='ROLLBACK_FAILED',error=str(rollback)[:1000]);self.save(r,'Recovery conflict. User intervention required.');return
   cancelled=self.events.get(jid,threading.Event()).is_set()
   r.update(status='CANCELLED' if cancelled else 'FAILED',error=None if cancelled else str(ex)[:1000],nonce=None);self.save(r,'Operation failed; no automatic replay.')
  finally:self.execution_lock.release()
 def test_worker(self,jid,files):
  r=self.get(jid);result=self.sandbox(self.home/'SandboxJobs',files,cancel=self.events[jid],timeout=30,memory_mb=512,runtime=self.runtime);r=self.get(jid)
  if r['status']=='REJECTED':return
  r['test']=result
  r.update(status='TEST_PASSED' if result['status']=='PASSED' and result.get('verifiedAppContainer') is True else 'CANCELLED' if result['status']=='CANCELLED' else 'TEST_FAILED',testedDigest=r['digest'],testScriptSha256=sha(files['test_main.py'].encode()))
  if r['status']=='TEST_FAILED':r['rejection']={'reason':'Isolated test status '+str(result.get('status'))+'; exit code '+str(result.get('exitCode'))+'. '+str(result.get('output',''))[-1500:],'policy':'ISOLATED_TEST_ASSERTIONS','next':'Inspect the test output and raw diff, correct the candidate or assertions, and rerun in isolation.'}
  r['nonce']=secrets.token_urlsafe(24) if r['status']=='TEST_PASSED' else None;r['expires']=time.time()+900;self.save(r,'Isolated tests finished. Passing assertions do not prove full application correctness.')
 def deploy(self,jid,body):
  self.verify_audit()
  r=self.get(jid)
  if r['status']!='TEST_PASSED' or body.get('approve') is not True or not r.get('nonce') or not secrets.compare_digest(str(body.get('nonce','')),r['nonce']) or body.get('digest')!=r['digest'] or r.get('testedDigest')!=r['digest'] or time.time()>r.get('expires',0):raise ValueError('Fresh, exact-hash approval after passing isolated tests is required.')
  self.events[jid]=threading.Event();r.update(status='PENDING_NATIVE_APPROVAL',nonce=None);self.save(r,'Native Windows confirmation required; web content cannot approve this update.');self.spawn(jid,self.deploy_worker);return r
 @contextlib.contextmanager
 def transaction_lock(self):
  import msvcrt
  f=(self.root/'.yoe-update-transaction.lock').open('a+b');f.seek(0);f.write(b'0');f.flush();f.seek(0)
  try:msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1);yield
  finally:
   with contextlib.suppress(OSError):f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
   f.close()
 def deploy_worker(self,jid):
  r=self.get(jid);event=self.events[jid]
  if not self.approval(r,event):r.update(status='REJECTED',rejection={'reason':r.get('_approvalDecision','Native approval declined, cancelled or unavailable; native broker supplied no finer distinction.'),'policy':'NATIVE_EXACT_CANDIDATE_APPROVAL','next':'Review the retained diff, rerun tests if approval expired, then request a fresh native confirmation.'});self.save(r,'Native approval rejected, cancelled or unavailable.');return
  with self.transaction_lock(),self.lease():
   if event.is_set():r.update(status='CANCELLED');self.save(r,'Stopped before deployment.');return
   for item in r['files']:
    if sha(target(self.root,item['path']).read_bytes())!=item['before']:raise ValueError('Production changed after staging. Nothing was deployed.')
    self.material(r,item,'before');self.material(r,item,'after')
   r['status']='DEPLOYING';self.save(r,'Recovery point verified; starting approved transaction.')
   for item in r['files']:
    if event.is_set():raise ValueError('Stopped during deployment.')
    destination=target(self.root,item['path'])
    if sha(destination.read_bytes())!=item['before']:raise ValueError('A production file changed during the transaction.')
    atom(destination,self.material(r,item,'after'))
   r['status']='VERIFYING';self.save(r,'Verifying deployed hashes and live application health.')
   if event.is_set() or not all(sha(target(self.root,i['path']).read_bytes())==i['after'] for i in r['files']) or not self.health():self.restore(r,'Health check failed or operation stopped; automatic rollback.');return
   r['status']='DEPLOYED';r['verifiedAt']=time.time();self.save(r,'Approved update verified; recovery point retained.')
 def restore(self,r,message):
  # Do not overwrite a third party edit that occurred after deployment.
  conflicts=[]
  for item in r['files']:
   current=sha(target(self.root,item['path']).read_bytes())
   if current not in {item['before'],item['after']}:conflicts.append(item['path'])
   self.material(r,item,'before')
  for item in r['files']:
   f=target(self.root,item['path'])
   if sha(f.read_bytes())==item['after']:atom(f,self.material(r,item,'before'))
  if conflicts:raise ValueError('Recovery conflict; independently edited files preserved: '+', '.join(conflicts))
  if not all(sha(target(self.root,i['path']).read_bytes())==i['before'] for i in r['files']):raise ValueError('Recovery integrity verification failed.')
  r.update(status='ROLLED_BACK',nonce=None);self.save(r,message)
  try:r['restoredHealth']=bool(self.health());r.pop('recoveryHealthError',None)
  except Exception as error:r['restoredHealth']=False;r['recoveryHealthError']=str(error)[:500]
  r['recoveryStatus']='HEALTHY' if r['restoredHealth'] else 'HEALTH_CHECK_FAILED';r['recoveryHealthCheckedAt']=time.time()
  self.save(r,'Recovery hashes verified; '+('application health verified.' if r['restoredHealth'] else 'application health not verified. Recovery needs attention.'))
 def rollback(self,jid,body):
  r=self.get(jid)
  if r['status']!='DEPLOYED' or body.get('approve') is not True or body.get('digest')!=r['digest']:raise ValueError('Approve restoring this exact deployed improvement.')
  self.events[jid]=threading.Event();r['status']='PENDING_NATIVE_RESTORE';self.save(r,'Native approval requested for restoring the preserved version.');self.spawn(jid,self.rollback_worker);return r
 def rollback_worker(self,jid):
  r=self.get(jid)
  if not self.approval({**r,'operation':'Restore previous version'},self.events[jid]):
   r['status']='DEPLOYED';self.save(r,'Restore request rejected; deployed candidate remains unchanged.');return
  with self.transaction_lock(),self.lease():
   r['status']='VERIFYING';self.save(r,'Starting approved restore transaction; restart will complete recovery.')
   self.restore(r,'User approved restoring the preserved version.')
 def reject(self,jid):
  r=self.get(jid)
  if r['status'] in {'DEPLOYING','VERIFYING','DEPLOYED','ROLLED_BACK','PENDING_NATIVE_RESTORE'}:raise ValueError('Cannot reject an applied transaction; use Restore.')
  self.events.setdefault(jid,threading.Event()).set();r.update(status='REJECTED',nonce=None,rejection={'reason':'The user explicitly selected Reject candidate. This does not mean its CSS failed validation.','policy':'USER_DECISION','next':'Inspect the raw diff. Stage a revised candidate only if you want to pursue it.'});self.save(r,'Rejected by user.');return r
 def stop(self):
  with self.lock:return self._stop()
 def _stop(self):
  for event in list(self.events.values()):event.set()
  value=self.setting();value['enabled']=False
  with self.connect() as db:db.execute("INSERT OR REPLACE INTO settings VALUES('schedule',?)",(json.dumps(value),))
  self.audit('stop','Emergency stop requested; schedule disabled and active Update YOE operations signalled.')
  return {'status':'STOP_REQUESTED','scheduleEnabled':False}
 def recover(self):
  for r in self.jobs():
   if r['status'] in {'DEPLOYING','VERIFYING'}:
    try:
     with self.transaction_lock():self.restore(r,'Interrupted deployment recovered on restart; no action repeated.')
    except Exception as ex:r.update(status='ROLLBACK_FAILED',error=str(ex));self.save(r,'Automatic recovery blocked by conflict.')
   elif r['status']=='PENDING_NATIVE_RESTORE':r.update(status='DEPLOYED');self.save(r,'Restart interrupted restore approval; deployment remains unchanged.')
   elif r['status'] in {'TESTING','PENDING_NATIVE_APPROVAL'}:r.update(status='CANCELLED',nonce=None);self.save(r,'Restart interrupted this operation; it was not replayed.')
 def scheduler_tick(self,engine,now=None,cpu=None):
  with self.lock:return self._scheduler_tick(engine,now,cpu)
 def _scheduler_tick(self,engine,now=None,cpu=None):
  value=self.setting();now=now or time.time()
  if not value['enabled'] or now<(value.get('nextRun') or now):return False
  import psutil
  from mini_agents import GATE
  if (psutil.cpu_percent() if cpu is None else cpu)>value['cpuLimit'] or GATE.locked() or engine.gpu_busy() or any(t['status'] in {'QUEUED','PLANNING','RUNNING'} for t in engine.tasks()):return False
  if not getattr(engine,'infer_override',None):
   import http.client
   conn=http.client.HTTPConnection('127.0.0.1',engine.config()['apiPort'],timeout=1)
   try:
    conn.request('GET','/slots');response=conn.getresponse()
    if response.status!=200 or any(x.get('is_processing') for x in json.loads(response.read(100000))):return False
   except Exception:return False
   finally:conn.close()
  # No private logs or source are sent. Only bounded, local structural metadata.
  measurements={'files':[],'cpuPercent':psutil.cpu_percent(),'availableRamBytes':psutil.virtual_memory().available,'time':now}
  for file in ['ui.html','assets/premium-ui.css','assets/mini-premium.css']:
   f=self.root/file
   if f.is_file():measurements['files'].append({'path':file,'bytes':f.stat().st_size,'sha256':sha(f.read_bytes())})
  task=engine.create({'agent':'update','backgroundReview':True,'objective':'Review this scheduled local application health snapshot. Propose improvements only. No source was inspected; no deployment, web access or code execution is authorized.','documents':[{'name':'health-snapshot.json','text':json.dumps(measurements)}]})
  value.update(nextRun=now+value['intervalMinutes']*60,lastTask=task['id'])
  with self.connect() as db:db.execute("INSERT OR REPLACE INTO settings VALUES('schedule',?)",(json.dumps(value),))
  return task['id']
 def start_scheduler(self,engine):
  def loop():
   while not self.closed:
    try:self.scheduler_tick(engine)
    except Exception as ex:
     value=self.setting();value.update(enabled=False,lastError=str(ex)[:500])
     with self.connect() as db:db.execute("INSERT OR REPLACE INTO settings VALUES('schedule',?)",(json.dumps(value),))

    time.sleep(5)
  threading.Thread(target=loop,daemon=True,name='UpdateYOE-scheduler').start()

 def explanation(self,r):
  with self.connect() as db:events=[json.loads(x[0]) for x in db.execute('SELECT data FROM events WHERE job=? ORDER BY seq',(r['id'],))]
  reason=r.get('rejection')
  recovery_failed=r['status']=='ROLLED_BACK' and r.get('restoredHealth') is False
  if recovery_failed:reason={'reason':'Previous file hashes were restored, but the application health check did not pass.'+(' '+r['recoveryHealthError'] if r.get('recoveryHealthError') else ''),'policy':'RECOVERY_HEALTH_CHECK','next':'Do not treat this update as successfully recovered. Inspect the health details and use the trusted repair/restart path; do not keep applying updates.'}
  if not reason and r['status']=='REJECTED':
   message=next((x.get('message','') for x in reversed(events) if x.get('status')=='REJECTED'),'Legacy rejection: no detailed reason was recorded.')
   reason={'reason':message,'policy':'USER_DECISION' if message=='Rejected by user.' else 'LEGACY_RECORDED_REASON','next':'Inspect the retained diff and test record. Missing legacy details cannot be reconstructed reliably.'}
  if not reason and r.get('error'):reason={'reason':r['error'],'policy':'TRANSACTION_VALIDATION','next':'Review the exact error; do not bypass policy. Use a separately reviewed release for protected files.'}
  return {'lifecycle':'Rollback needs attention' if recovery_failed else {'STAGED':'Improvement proposed','TEST_PASSED':'Tests passed','PENDING_NATIVE_APPROVAL':'Awaiting approval','DEPLOYED':'Verified' if r.get('verifiedAt') else 'Deployed','REJECTED':'Rejected','TEST_FAILED':'Rejected','ROLLED_BACK':'Rolled back'}.get(r['status'],r['status']),'reason':reason,'files':[x['path'] for x in r.get('files',[])],'sandboxActuallyRan':bool(r.get('test',{} ) and r['test'].get('verifiedAppContainer')),'sandboxStatus':(r.get('test') or {}).get('status','NOT_RUN'),'history':events,'verifiedAt':r.get('verifiedAt'),'recoveryStatus':r.get('recoveryStatus'),'restoredHealth':r.get('restoredHealth'),'recoveryHealthCheckedAt':r.get('recoveryHealthCheckedAt')}

 def denied_stage(self,body,error):
  from mini_agents import reject_secrets
  files=[]
  for name,text in list((body.get('files') or {}).items())[:8]:
   name=str(name)[:200];value=str(text)[:60000]
   try:reject_secrets(value)
   except ValueError:value='[Submitted content withheld: possible secret detected.]'
   files.append({'path':name,'diff':'Rejected submitted candidate (not a baseline comparison):\n'+value})
  r={'id':uuid.uuid4().hex,'created':time.time(),'status':'REJECTED','files':files,'digest':None,'test':None,'nonce':None,'error':str(error)[:1000],'history':[],'rejection':{'reason':str(error)[:1000],'policy':'STAGING_SCOPE_OR_CONTENT_VALIDATION','next':'Only existing unprotected UI text files may use this updater. Protected executable changes need a separately reviewed trusted release.'}}
  self.save(r,'Staging denied by deterministic policy before any sandbox or deployment.');return r
