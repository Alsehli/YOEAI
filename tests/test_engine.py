import sys,tempfile,time,json,unittest,threading,subprocess,os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'source'))
import mini_agents as m

class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).parent);self.root=Path(self.tmp.name);self.project=self.root/'project';self.project.mkdir();(self.project/'calc.py').write_text('def add(a, b):\n    return a - b\n')
  self.calls=[]
  def infer(t,msg,tokens):
   self.calls.append((t['agent'],msg));system=msg[0]['content']
   if 'ONLY a JSON' in system:return json.dumps({'path':'calc.py','find':'return a - b','replace':'return a + b','explanation':'Fix arithmetic'})
   return 'Test analysis. No tools were executed by the model.'
  self.e=m.Engine(self.root,infer=infer,search=lambda *a:{'results':[{'title':'Official test','url':'https://example.com/docs','snippet':'Example facts'}],'provider':'test fixture','searchedAt':'2026-10-19'})
 def tearDown(self):self.e.closed=True;self.e.worker.join(2);self.tmp.cleanup()
 def wait(self,t):
  for _ in range(200):
   t=self.e.get(t['id'])
   if t['status'] not in m.ACTIVE and self.e.running_id!=t['id']:return t
   time.sleep(.02)
  self.fail('Task did not finish')
 def code(self):return self.e.create({'agent':'code','objective':'Fix add','project':str(self.project),'files':['calc.py'],'permissions':{'readProject':True}})
 def test_research_offline_and_separate_memory(self):
  self.e.set_memory('research',{'preferences':'Use concise reports','maxTokens':512});self.assertEqual(self.e.memory('code')['preferences'],'');t=self.wait(self.e.create({'agent':'research','objective':'Compare two choices'}));self.assertEqual(t['status'],'COMPLETED');self.assertIn('Web search disabled',t['result']);self.assertFalse(any(x['name']=='Web search' for x in t['tools']))
 def test_web_requires_explicit_approval(self):
  t=self.wait(self.e.create({'agent':'research','objective':'Research test','permissions':{'web':True}}));self.assertEqual(t['tools'][0]['name'],'Web search');self.assertIn('https://example.com/docs',t['result'])
 def test_patch_approval_validation(self):
  t=self.wait(self.code());self.assertEqual(t['status'],'WAITING_FOR_APPROVAL');self.assertIn('a - b',(self.project/'calc.py').read_text());self.assertRaises(ValueError,self.e.approve_patch,t['id'],{});self.e.approve_patch(t['id'],{'approve':True});self.assertIn('a + b',(self.project/'calc.py').read_text());t=self.wait(self.e.request_validation(t['id'],{'approve':True}));self.assertEqual(t['validation'][0]['status'],'PASS')
 def test_changed_source_not_overwritten(self):
  t=self.wait(self.code());(self.project/'calc.py').write_text('CHANGED');self.assertRaises(ValueError,self.e.approve_patch,t['id'],{'approve':True});self.assertEqual((self.project/'calc.py').read_text(),'CHANGED')
 def test_scoped_paths_and_secrets(self):
  for rel in ['../calc.py','C:/Windows/a.py','.env','secrets.py','x:stream.py']:
   self.assertRaises((ValueError,FileNotFoundError),m.scoped,self.project,rel)
  self.assertRaises(ValueError,self.e.set_memory,'code',{'preferences':'password=abc','maxTokens':512})
  self.assertRaises(ValueError,self.e.create,{'agent':'code','objective':'test','files':['calc.py'],'project':str(self.project),'permissions':{}})
 def test_commands_are_not_a_tool(self):
  self.assertFalse(hasattr(self.e,'execute'));self.assertRaises(ValueError,self.e.request_validation,self.wait(self.e.create({'agent':'code','objective':'Run shell command'}))['id'],{'approve':True})
 def test_credentials_and_patch_scope(self):
  self.assertRaises(ValueError,self.e.create,{'agent':'research','objective':'test','documents':[{'name':'notes.txt','text':'api_key="private-value"'}]})
  t=self.wait(self.code());self.assertRaises(ValueError,self.e.check_patch,t,{'path':'../outside.py','find':'x','replace':'y'})
 def test_history_clear_keeps_other_agent_and_memory(self):
  self.e.set_memory('research',{'preferences':'Concise','maxTokens':512});self.wait(self.e.create({'agent':'research','objective':'Disposable task'}));self.wait(self.e.create({'agent':'code','objective':'Explain a loop'}));self.e.q.join();self.e.clear('research');self.assertTrue(all(t['agent']=='code' for t in self.e.tasks()));self.assertEqual(self.e.memory('research')['preferences'],'Concise')
 def test_linked_project_root_blocked(self):
  link=self.root/'linked-project'
  if os.name=='nt':
   script="New-Item -ItemType Junction -Path '"+str(link).replace("'","''")+"' -Target '"+str(self.project).replace("'","''")+"' | Out-Null"
   subprocess.run(['powershell.exe','-NoProfile','-Command',script],check=True,capture_output=True)
  else:link.symlink_to(self.project,target_is_directory=True)
  self.assertRaises(ValueError,m.clean_root,str(link))
 def test_cancel_queue(self):
  m.GATE.acquire()
  try:t=self.e.create({'agent':'research','objective':'Queued task'});self.e.cancel(t['id'])
  finally:m.GATE.release()
  self.assertEqual(self.wait(t)['status'],'CANCELLED')
 def test_restart_recovers_without_repeat(self):
  t=self.wait(self.e.create({'agent':'research','objective':'Original'}));t['status']='RUNNING';self.e.save(t);self.e.closed=True;self.e.worker.join(2);e2=m.Engine(self.root,infer=lambda *a:self.fail('Unexpected repeated action'));self.assertEqual(e2.get(t['id'])['status'],'CANCELLED');e2.closed=True;e2.worker.join(2)
 def test_queue_bound(self):
  m.GATE.acquire()
  try:
   for i in range(8):self.e.create({'agent':'research','objective':str(i)})
   self.assertRaises(ValueError,self.e.create,{'agent':'research','objective':'overflow'})
   for t in self.e.tasks():self.e.cancel(t['id'])
  finally:m.GATE.release()

if __name__=='__main__':unittest.main(verbosity=2)
