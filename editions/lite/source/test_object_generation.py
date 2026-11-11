import json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
from object_generation import ObjectGenerator

class ObjectTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.resume=Mock();self.gen=ObjectGenerator(self.root/'config.json',self.root/'GeneratedObjects',Mock(return_value=True),self.resume);self.gen.gpu_lock=self.root/'generation.lock';self.addCleanup(self.gen.shutdown)
 def test_unready_backend_cannot_run(self):
  (self.root/'config.json').write_text(json.dumps({'engine':'triposr','enabled':False}))
  with self.assertRaisesRegex(ValueError,'not enabled'):self.gen.start({'image':'invalid'})
 def test_shared_lock_is_not_stolen_and_historical_object_survives(self):
  self.gen.gpu_lock.write_text('other job');self.gen.home.mkdir();prior=self.gen.home/'previous.glb';prior.write_bytes(b'user object')
  self.gen.run({},b'fixture','a'*32)
  self.assertEqual(self.gen.status()['status'],'error');self.assertEqual(self.gen.gpu_lock.read_text(),'other job');self.assertEqual(prior.read_bytes(),b'user object');self.resume.assert_not_called()
 def test_pause_failure_releases_only_our_lock(self):
  self.gen.pause=Mock(side_effect=ValueError('Chat busy'));self.gen.run({},b'fixture','b'*32)
  self.assertEqual(self.gen.status()['status'],'error');self.assertFalse(self.gen.gpu_lock.exists());self.resume.assert_not_called()
 def test_stopped_before_spawn_restores_chat_gate(self):
  self.gen.cancelled.set();self.gen.run({'backendRoot':str(self.root)},b'fixture','c'*32)
  self.assertEqual(self.gen.status()['status'],'cancelled');self.assertFalse(self.gen.gpu_lock.exists());self.resume.assert_called_once()

if __name__=='__main__':unittest.main(verbosity=2)
