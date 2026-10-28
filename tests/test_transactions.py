import tempfile,unittest,json,time,threading
from pathlib import Path
from unittest.mock import patch
import update_manager as u
class Transactions(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).parent);self.base=Path(self.tmp.name);self.root=self.base/'app';(self.root/'assets').mkdir(parents=True);self.file=self.root/'assets/test.css';self.file.write_text('body { color: blue; }');self.m=u.Manager(self.base/'profile',self.root,self.base/'runtime',health=lambda:True,approval=lambda *a:True,sandbox=lambda *a,**kw:{'status':'PASSED','verifiedAppContainer':True})
 def tearDown(self):
  self.m.closed=True
  for thread in self.m.workers.values():thread.join(5)
  self.tmp.cleanup()
 def stage(self):return self.m.stage({'assets/test.css':'body { color: teal; }'})
 def wait(self,jid):
  for _ in range(200):
   thread=self.m.workers.get(jid)
   if not thread or not thread.is_alive():return self.m.get(jid)
   time.sleep(.01)
  self.fail('Worker timeout')
 def passed(self):
  r=self.stage()
  with patch.object(self.m,'manifest',return_value=True):self.m.start_test(r['id'],{'approve':True,'digest':r['digest'],'tests':'assert True'})
  return self.wait(r['id'])
 def deploy(self,r):self.m.deploy(r['id'],{'approve':True,'digest':r['digest'],'nonce':r['nonce']});return self.wait(r['id'])
 def test_stage_does_not_write_production(self):
  r=self.stage();self.assertEqual(r['status'],'STAGED');self.assertEqual(self.file.read_text(),'body { color: blue; }')
 def test_protected_and_traversal_blocked(self):
  for name in ['../outside.css','assets/update-yoe.js','YOEAI.exe','Source/runtime.py','assets/design-engine/worker.py','database.sqlite3','C:/Windows/x.js']:
   self.assertRaises(ValueError,self.m.stage,{name:'new'})
 def test_existing_updater_controls_cannot_update_themselves(self):
  control=self.root/'assets/update-autonomy.js';control.write_text('trusted controls')
  self.assertRaises(ValueError,self.m.stage,{'assets/update-autonomy.js':'changed controls'})
  self.assertEqual(control.read_text(),'trusted controls')
 def test_no_approval_and_untested_deploy_blocked(self):
  r=self.stage();self.assertRaises(ValueError,self.m.deploy,r['id'],{'approve':True,'digest':r['digest']})
  self.assertRaises(ValueError,self.m.start_test,r['id'],{'tests':'assert True'})
 def test_missing_runtime_blocks_execution(self):
  r=self.stage();self.assertRaises(ValueError,self.m.start_test,r['id'],{'approve':True,'digest':r['digest'],'tests':'assert True'})
 def test_success_and_manual_restore(self):
  r=self.deploy(self.passed());self.assertEqual(r['status'],'DEPLOYED');self.assertIn('teal',self.file.read_text());self.m.rollback(r['id'],{'approve':True,'digest':r['digest']});r=self.wait(r['id']);self.assertEqual(r['status'],'ROLLED_BACK');self.assertIn('blue',self.file.read_text());self.m.verify_audit()
 def test_failed_health_automatically_rolls_back(self):
  r=self.passed();self.m.health=lambda:False;r=self.deploy(r);self.assertEqual(r['status'],'ROLLED_BACK');self.assertIn('blue',self.file.read_text())
 def test_restored_health_is_distinct_from_hash_recovery(self):
  r=self.passed();self.m.health=lambda:False;r=self.deploy(r)
  self.assertEqual(r['recoveryStatus'],'HEALTH_CHECK_FAILED');self.assertFalse(r['restoredHealth'])
  why=self.m.explanation(r);self.assertEqual(why['lifecycle'],'Rollback needs attention');self.assertEqual(why['reason']['policy'],'RECOVERY_HEALTH_CHECK')
 def test_recovery_health_exception_is_recorded(self):
  r=self.deploy(self.passed())
  def broken():raise RuntimeError('fixture health unavailable')
  self.m.health=broken;self.m.rollback(r['id'],{'approve':True,'digest':r['digest']});r=self.wait(r['id'])
  self.assertEqual(r['status'],'ROLLED_BACK');self.assertEqual(r['recoveryStatus'],'HEALTH_CHECK_FAILED');self.assertIn('fixture health unavailable',r['recoveryHealthError']);self.assertIn('blue',self.file.read_text())
 def test_healthy_restore_records_checked_time(self):
  r=self.deploy(self.passed());self.m.rollback(r['id'],{'approve':True,'digest':r['digest']});r=self.wait(r['id'])
  self.assertEqual(r['recoveryStatus'],'HEALTHY');self.assertTrue(r['restoredHealth']);self.assertGreater(r['recoveryHealthCheckedAt'],0);self.assertEqual(self.m.explanation(r)['lifecycle'],'Rolled back')
 def test_disk_full_during_deploy_preserves_stable_file(self):
  r=self.passed();original=u.atom
  def fail_destination(path,data):
   if path==self.file:raise OSError(28,'fixture disk full')
   return original(path,data)
  with patch.object(u,'atom',side_effect=fail_destination):r=self.deploy(r)
  self.assertEqual(r['status'],'ROLLED_BACK');self.assertTrue(r['restoredHealth']);self.assertIn('blue',self.file.read_text())
 def test_locked_resource_during_deploy_preserves_stable_file(self):
  r=self.passed();original=u.atom
  def locked(path,data):
   if path==self.file:raise PermissionError('fixture resource locked')
   return original(path,data)
  with patch.object(u,'atom',side_effect=locked):r=self.deploy(r)
  self.assertEqual(r['status'],'ROLLED_BACK');self.assertTrue(r['restoredHealth']);self.assertIn('blue',self.file.read_text())
 def test_interrupted_staging_never_changes_production(self):
  with patch.object(u,'atom',side_effect=OSError('fixture interrupted staging')):self.assertRaises(OSError,self.stage)
  self.assertIn('blue',self.file.read_text())
  with self.m.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],0)
 def test_changed_source_not_overwritten(self):
  r=self.passed();self.file.write_text('third party change');r=self.deploy(r);self.assertEqual(r['status'],'FAILED');self.assertEqual(self.file.read_text(),'third party change')
 def test_staging_tampering_blocks_deploy(self):
  r=self.passed();(self.m.home/'Candidates'/r['id']/'0.after').write_text('tampered');r=self.deploy(r);self.assertEqual(r['status'],'FAILED');self.assertIn('blue',self.file.read_text())
 def test_wrong_nonce_and_hash(self):
  r=self.passed();self.assertRaises(ValueError,self.m.deploy,r['id'],{'approve':True,'digest':r['digest'],'nonce':'wrong'});self.assertRaises(ValueError,self.m.deploy,r['id'],{'approve':True,'digest':'wrong','nonce':r['nonce']})
 def test_native_rejection(self):
  r=self.passed();self.m.approval=lambda *a:False;r=self.deploy(r);self.assertEqual(r['status'],'REJECTED');self.assertIn('blue',self.file.read_text())
 def test_failed_test_cannot_deploy(self):
  self.m.sandbox=lambda *a,**k:{'status':'FAILED','verifiedAppContainer':True};r=self.passed();self.assertEqual(r['status'],'TEST_FAILED');self.assertRaises(ValueError,self.m.deploy,r['id'],{'approve':True,'digest':r['digest'],'nonce':'x'})
 def test_nonisolated_success_rejected(self):
  self.m.sandbox=lambda *a,**k:{'status':'PASSED','verifiedAppContainer':False};r=self.passed();self.assertEqual(r['status'],'TEST_FAILED')
 def test_restart_recovers_interrupted_deployment(self):
  r=self.passed();self.file.write_text('body { color: teal; }');r['status']='VERIFYING';self.m.save(r,'fixture interruption');other=u.Manager(self.base/'profile',self.root,self.base/'runtime',health=lambda:True);self.assertEqual(other.get(r['id'])['status'],'ROLLED_BACK');self.assertIn('blue',self.file.read_text());other.closed=True
 def test_recovery_conflict_preserves_independent_change(self):
  r=self.passed();self.file.write_text('independent');r['status']='VERIFYING';self.m.save(r,'fixture interruption');other=u.Manager(self.base/'profile',self.root,self.base/'runtime');self.assertEqual(other.get(r['id'])['status'],'ROLLBACK_FAILED');self.assertEqual(self.file.read_text(),'independent');other.closed=True
 def test_audit_corruption_blocks_manager(self):
  self.stage()
  with self.m.connect() as db:db.execute("UPDATE events SET data='corrupt'")
  self.assertRaises(ValueError,u.Manager,self.base/'profile',self.root,self.base/'runtime')
 def test_schedule_defaults_and_validation(self):
  self.assertFalse(self.m.setting()['enabled']);self.assertRaises(ValueError,self.m.schedule,{'enabled':True});self.assertRaises(ValueError,self.m.schedule,{'approve':True,'enabled':True,'intervalMinutes':1})
 def test_scheduler_dedup_and_busy_pause(self):
  class Engine:
   infer_override=True
   def __init__(self):self.items=[]
   def gpu_busy(self):return False
   def tasks(self):return self.items
   def create(self,body):self.items.append({'id':'scheduled','status':'QUEUED',**body});return self.items[-1]
  e=Engine();self.m.schedule({'approve':True,'enabled':True,'intervalMinutes':15});now=time.time()+1000
  self.assertFalse(self.m.scheduler_tick(e,now,cpu=90));self.assertEqual(self.m.scheduler_tick(e,now,cpu=0),'scheduled');self.assertFalse(self.m.scheduler_tick(e,now+1000,cpu=0));self.assertEqual(len(e.items),1)
 def test_expired_approval(self):
  r=self.passed();r['expires']=time.time()-1;self.m.save(r,'Fixture expired approval');self.assertRaises(ValueError,self.m.deploy,r['id'],{'approve':True,'digest':r['digest'],'nonce':r['nonce']})
 def test_changed_runtime_manifest_blocked(self):
  self.m.runtime.mkdir();(self.m.runtime/'runtime-manifest.json').write_text('{"files":[]}');self.assertFalse(self.m.manifest(force=True))
 def test_rejected_restore_preserves_deployment(self):
  r=self.deploy(self.passed());self.m.approval=lambda *a:False;self.m.rollback(r['id'],{'approve':True,'digest':r['digest']});r=self.wait(r['id']);self.assertEqual(r['status'],'DEPLOYED');self.assertIn('teal',self.file.read_text())
 def test_emergency_stop_disables_schedule(self):
  self.m.schedule({'approve':True,'enabled':True});self.m.events['test']=threading.Event();self.m.stop();self.assertTrue(self.m.events['test'].is_set());self.assertFalse(self.m.setting()['enabled'])
if __name__=='__main__':unittest.main()
