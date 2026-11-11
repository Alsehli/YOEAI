import json,sys,tempfile,time,threading,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from ph3_image import PH3Generator
from lite_image_generation import ImageRouter
from ph3_worker import graph

class PH3Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.resume=Mock();self.video=PH3Generator(self.root/'config.json',self.root/'images',Mock(return_value=True),self.resume);self.addCleanup(self.video.shutdown)
 def test_gate_keeps_unfinished_model_disabled(self):
  (self.root/'config.json').write_text(json.dumps({'enabled':False,'python':'missing','worker':'missing','backendRoot':'.'}))
  with self.assertRaisesRegex(ValueError,'installed and tested'):self.video.config()
 def test_invalid_size_rejected_before_config_or_worker(self):
  with patch.object(self.video,'config') as cfg:
   with self.assertRaises(ValueError):self.video.start({'prompt':'A cat','size':512})
   cfg.assert_not_called()
 def test_unknown_engine_never_uses_turbo(self):
  turbo=Mock();turbo.home=self.root/'images';turbo.config_path=self.root/'turbo.json';turbo.status.return_value={'status':'idle'}
  router=ImageRouter(turbo,self.root)
  with self.assertRaisesRegex(ValueError,'no alternate'):router.start({'prompt':'A cat','engine':'unknown'})
  turbo.start.assert_not_called()
 def test_held_lock_preserves_other_owner_and_history(self):
  lock=self.root/'generation.lock';lock.write_text('another job');self.video.home.mkdir();historic=self.video.home/'historic.png';historic.write_bytes(b'keep')
  self.video.run({'backendRoot':str(self.root)},'A cat',2048,'a'*32)
  self.assertEqual(self.video.status()['status'],'error');self.assertEqual(lock.read_text(),'another job');self.assertEqual(historic.read_bytes(),b'keep');self.resume.assert_not_called()
 def test_stop_terminates_worker_descendants_and_restores_gate(self):
  import psutil
  worker=self.root/'worker.py';worker.write_text("import subprocess,sys,time\nfrom pathlib import Path\np=subprocess.Popen([sys.executable,'-c','import time;time.sleep(300)'])\nPath(__file__).with_suffix('.pid').write_text(str(p.pid))\ntime.sleep(300)\n")
  cfg={'python':sys.executable,'worker':str(worker),'backendRoot':str(self.root)}
  thread=threading.Thread(target=self.video.run,args=(cfg,'A cat',2048,'b'*32));thread.start()
  for _ in range(100):
   if worker.with_suffix('.pid').exists():break
   time.sleep(.05)
  pid=int(worker.with_suffix('.pid').read_text());self.video.cancel();thread.join(timeout=20)
  self.assertFalse(thread.is_alive());self.assertFalse(psutil.pid_exists(pid));self.assertEqual(self.video.status()['status'],'cancelled');self.resume.assert_called_once();self.assertFalse((self.root/'generation.lock').exists())
 def test_official_eight_step_graph_uses_quantized_components(self):
  g=graph('A cat',2912,42)
  self.assertEqual(g['1']['inputs']['unet_name'],'p-h3-image_w4a8.safetensors');self.assertEqual(g['7']['inputs']['width'],2912)
  self.assertEqual(len(g['11']['inputs']['sigmas'].split(',')),9);self.assertEqual(g['9']['class_type'],'BasicGuider')

if __name__=='__main__':unittest.main(verbosity=2)
