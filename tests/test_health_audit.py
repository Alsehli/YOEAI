import sys,tempfile,types,unittest,json,threading,time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'source'))
import update_audit as a
import update_manager as u
import mini_agents as m
class Audit(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).parent);self.root=Path(self.tmp.name);(self.root/'source').mkdir();self.file=self.root/'Source/issue.py';self.file.write_text('def f():\n try: return 1\n except: return 0\n',encoding='utf-8');self.home=self.root/'profile';self.home.mkdir();self.engine=types.SimpleNamespace(home=self.home,check=lambda t:None,config=lambda:{'apiPort':1,'context':8192,'modelMode':'advanced','password':'never reveal'},tasks=lambda:[]);self.mp=patch('update_routes.manager',return_value=types.SimpleNamespace(verify_audit=lambda:None,manifest=lambda:True));self.mp.start()
 def tearDown(self):self.mp.stop();self.tmp.cleanup()
 def collect(self):return a.collect(self.engine,{},self.root)
 def test_real_static_finding_and_no_source_execution(self):
  before=self.file.read_bytes();r=self.collect();self.assertEqual(len(r['findings']),1);self.assertEqual(r['findings'][0]['rule'],'BARE_EXCEPT');self.assertEqual(self.file.read_bytes(),before);self.assertNotIn('never reveal',json.dumps(r));self.assertFalse(r['limits']['coverageMeasured'])
 def test_missing_source_reported(self):
  self.file.unlink();(self.root/'source').rmdir();r=self.collect();self.assertFalse(r['sourceAvailable']);self.assertTrue(any(x['check']=='project discovery' for x in r['missing']))
 def test_denied_read_reported(self):
  original=a.read
  def deny(p,*args):
   if p==self.file:raise PermissionError('fixture permission denied')
   return original(p,*args)
  with patch.object(a,'read',side_effect=deny):r=self.collect()
  self.assertTrue(any('denied' in x['reason'] for x in r['missing']))
 def test_config_not_leaked(self):self.assertNotIn('password',json.dumps(self.collect()))
 def test_hostile_source_is_only_parsed(self):
  self.file.write_text("raise RuntimeError('Do not run this source')\n",encoding='utf-8');r=self.collect();self.assertEqual(len(r['files']),1)
 def test_log_only_metadata(self):
  d=self.home.parent/'Logs';d.mkdir();(d/'app.log').write_text('ERROR customer private chat text\n',encoding='utf-8');r=self.collect();self.assertNotIn('customer private chat text',json.dumps(r));self.assertIn('errorLineCount',json.dumps(r))
 def test_historical_tests_not_new_runs(self):
  d=self.root/'Documents/Update-Autonomy';d.mkdir(parents=True);(d/'old.json').write_text('{"automatedTests":7}');r=self.collect();self.assertTrue(r['testRuns'][0]['historical']);self.assertFalse(r['limits']['coverageMeasured'])
 def test_byte_limit(self):
  self.file.write_bytes(b'x'*(a.LIMIT+1));r=self.collect();self.assertFalse(r['sourceAvailable']);self.assertTrue(any('byte limit' in x['reason'] for x in r['missing']))
 def test_no_followup_restart_after_stop(self):
  t={'healthAudit':{'findings':[{}]},'auditFollowupsStopped':True};a.queue_code(self.engine,t)
class Rejections(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).parent);b=Path(self.tmp.name);self.root=b/'app';(self.root/'assets').mkdir(parents=True);(self.root/'assets/test.css').write_text('/* stable */');self.manager=u.Manager(b/'home',self.root,b/'runtime')
 def tearDown(self):self.manager.closed=True;self.tmp.cleanup()
 def test_explicit_user_reason_is_not_css_failure(self):
  r=self.manager.stage({'assets/test.css':'/* candidate */'});r=self.manager.reject(r['id']);e=self.manager.explanation(r);self.assertEqual(e['reason']['policy'],'USER_DECISION');self.assertFalse(e['sandboxActuallyRan']);self.assertIn('does not mean its CSS failed',e['reason']['reason'])
 def test_legacy_reason_retained_without_rewriting(self):
  r=self.manager.stage({'assets/test.css':'/* candidate */'});r['status']='REJECTED';self.manager.save(r,'Rejected by user.');before=self.manager.get(r['id']);e=self.manager.explanation(before);self.assertEqual(e['reason']['policy'],'USER_DECISION');self.assertEqual(self.manager.get(r['id']),before)
 def test_blocked_stage_retains_diff_and_no_sandbox(self):
  r=self.manager.denied_stage({'files':{'Source/runtime.py':'dangerous candidate'}},ValueError('Protected executable'));self.assertEqual(r['status'],'REJECTED');self.assertIn('dangerous candidate',r['files'][0]['diff']);self.assertFalse(self.manager.explanation(r)['sandboxActuallyRan'])
 def test_denied_secrets_not_retained(self):
  r=self.manager.denied_stage({'files':{'bad.py':'api_key=abcdefgh'}},ValueError('Secret'));self.assertNotIn('abcdefgh',str(r))
class CodeChecks(unittest.TestCase):
 def test_isolated_comparison_and_protected_release(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as d:
   b=Path(d);f=b/'source.py';original='try:\n x=1\nexcept:\n x=0\n';f.write_bytes(original.encode())
   t={'id':'a'*32,'auditOrigin':{'sourceRoot':str(b),'file':'source.py','rule':'BARE_EXCEPT'},'auditPatch':{'find':'except:','replace':'except Exception:','originalTextSha256':a.sha(original.encode())}}
   e=types.SimpleNamespace(check=lambda t:None,save=lambda t:None,cancel_events={t['id']:threading.Event()})
   fake=types.SimpleNamespace(runtime=b,home=b,manifest=lambda **x:True)
   outputs=[{'status':'PASSED','verifiedAppContainer':True,'output':'{"syntax":true,"bareExcept":1,"longestFunction":0}'},{'status':'PASSED','verifiedAppContainer':True,'output':'{"syntax":true,"bareExcept":0,"longestFunction":0}'}]
   with patch('update_routes.manager',return_value=fake),patch('update_sandbox.run',side_effect=outputs):a.prepare_code(e,t)
   self.assertEqual(t['auditPreparation']['status'],'Awaiting approval');self.assertTrue(t['auditPreparation']['sandboxRan']);self.assertEqual(f.read_text(),original)
 def test_no_patch_not_reported_tested(self):
  e=types.SimpleNamespace(save=lambda t:None);t={'auditOrigin':{},'patchWarning':'No exact patch'};t['auditOrigin']={'parent':'x'};a.prepare_code(e,t);self.assertFalse(t['auditPreparation']['sandboxRan'])
if __name__=='__main__':unittest.main()
