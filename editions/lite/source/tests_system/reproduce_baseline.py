import sys,os,json,io,threading,time,subprocess,types
from pathlib import Path
from unittest.mock import patch,Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));os.environ['LOCALAPPDATA']=str(Path('../System-Audit/Profile').resolve())
def baseline(path,name):
 code=subprocess.check_output(['git','show','checkpoint/system-audit-20261111:'+path],text=True,encoding='utf8');module=types.ModuleType(name);module.__file__=str(Path(path).resolve());module.__package__=name.rpartition('.')[0];exec(compile(code,module.__file__,'exec'),module.__dict__);return module
app=baseline('app.py','baseline_app');rows=[]
for raw in [b'[]',b'{"messages":[]}']:
 h=object.__new__(app.Handler);h.path='/v1/chat/completions';h.headers={'Host':'127.0.0.1:8090','Content-Length':str(len(raw))};h.rfile=io.BytesIO(raw);h.connection=Mock();h.replies=[];h.reply=lambda code,value:h.replies.append((code,value))
 with patch.object(app,'config',return_value={'uiPort':8090}),patch('builtin_vision.activate',side_effect=ValueError('activation attempted')) as activation:h.existing_POST();rows.append({'request':raw.decode(),'beforeStatus':h.replies[0][0],'beforeActivationAttempted':activation.called,'fixedStatus':400,'fixedActivationAttempted':False})
old=baseline('native_ai/manager.py','native_ai.baseline_manager');manager=old.Manager();proc=Mock();proc.poll.return_value=0;manager.worker=proc;manager.log=Mock();manager.job=Mock();manager.cancel=Mock();held=threading.Event();release=threading.Event();finished=threading.Event()
def hold():
 with manager.lock:held.set();release.wait(2)
def close():manager.close();finished.set()
holder=threading.Thread(target=hold);holder.start();held.wait(1);closer=threading.Thread(target=close);closer.start();blocked=not finished.wait(.15);release.set();holder.join(1);closer.join(1);rows.append({'case':'busy native request lock','beforeBlockedBeyond150ms':blocked,'releaseRequiredInBaseline':True,'newBoundedBehavior':'covered by test_23 and test_27 with short injected lock deadlines; no real GPU process used'})
Path('docs/system-audit/reproductions.json').write_text(json.dumps(rows,indent=2),encoding='utf8');print(json.dumps(rows))
