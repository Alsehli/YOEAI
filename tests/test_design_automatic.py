import unittest,tempfile,threading
from pathlib import Path
from unittest.mock import Mock,patch
from design_generation import DesignGenerator

class AutomaticDesign(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.g=DesignGenerator(Path(self.temp.name)/'config.json',None,None,Path(self.temp.name)/'gpu.lock')
  def generated(c,request,job):self.g.state={'status':'complete','id':job}
  self.g.run_design=Mock(side_effect=generated)
 def tearDown(self):self.g.cancelled.set();self.g.shutdown();self.temp.cleanup()
 def start(self):
  self.g.start({'prompt':'A red cup','width':512,'height':512,'steps':16});self.g.worker.join(3);return self.g.status()
 def test_ready_skips_setup(self):
  self.g.runtime_ready=Mock(return_value={});self.g.ensure_ready=Mock();self.assertEqual(self.start()['status'],'complete');self.g.ensure_ready.assert_not_called();self.g.run_design.assert_called_once()
 def test_missing_setup_repairs_once_and_continues(self):
  self.g.runtime_ready=Mock(side_effect=[ValueError('missing'),{}]);self.g.ensure_ready=Mock();self.assertEqual(self.start()['status'],'complete');self.g.ensure_ready.assert_called_once();self.g.run_design.assert_called_once()
 def test_failed_setup_does_not_loop_or_generate(self):
  self.g.runtime_ready=Mock(side_effect=ValueError('missing'));self.g.ensure_ready=Mock(side_effect=ValueError('network offline'));s=self.start();self.assertEqual(s['status'],'error');self.assertIn('network offline',s['message']);self.g.ensure_ready.assert_called_once();self.g.run_design.assert_not_called()
 def test_cancel_setup_never_generates(self):
  self.g.runtime_ready=Mock(side_effect=[ValueError('missing'),{}]);self.g.ensure_ready=Mock(side_effect=lambda *a:self.g.cancelled.set());self.assertEqual(self.start()['status'],'cancelled');self.g.run_design.assert_not_called()
 def test_duplicate_generation_blocked_during_setup(self):
  self.g.state={'status':'installing'};self.assertRaises(ValueError,self.g.start,{'prompt':'A red cup'});self.g.run_design.assert_not_called()
 def test_media_pause_reconciles_before_stopping(self):
  import model_modes as m
  events=[]
  with patch.object(m.runtime,'healthy',return_value=True),patch.object(m,'read_config',return_value={'apiPort':8080}),patch.object(m,'assert_idle',side_effect=lambda **k:events.append('idle')),patch.object(m,'reconcile_running',side_effect=lambda:events.append('verified')),patch.object(m,'stop_current',side_effect=lambda:events.append('stop')):
   self.assertTrue(m.pause_for_media());self.assertEqual(events,['idle','verified','stop'])
 def test_unowned_model_is_never_stopped(self):
  import model_modes as m
  with patch.object(m.runtime,'healthy',return_value=True),patch.object(m,'read_config',return_value={'apiPort':8080}),patch.object(m,'assert_idle'),patch.object(m,'reconcile_running',side_effect=ValueError('unowned')),patch.object(m,'stop_current') as stop:
   self.assertRaises(ValueError,m.pause_for_media);stop.assert_not_called()
