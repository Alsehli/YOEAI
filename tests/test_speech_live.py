import importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,MagicMock
import speech_input,speech_live
class LiveTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.p=patch.object(speech_input,'HOME',Path(self.tmp.name));self.p.start();self.s=speech_live.LiveDictation(Path(self.tmp.name)/'config.json')
 def tearDown(self):self.s.cancel();self.p.stop();self.tmp.cleanup()
 def test_activation_required(self):
  with self.assertRaisesRegex(ValueError,'explicitly'):self.s.start(False)
 def test_advanced_rejected(self):
  with patch('configuration.read_config',return_value={'modelMode':'advanced'}),patch('model_modes.reconcile_running') as reconcile:
   with self.assertRaisesRegex(ValueError,'9B'):self.s.fast_only()
   reconcile.assert_not_called()
 def test_saved_fast_but_actual_advanced_rejected(self):
  with patch('configuration.read_config',return_value={'modelMode':'fast'}),patch('model_modes.reconcile_running',return_value='advanced'):
   with self.assertRaises(ValueError):self.s.fast_only()
 def test_actual_fast_allowed(self):
  with patch('configuration.read_config',return_value={'modelMode':'fast'}),patch('model_modes.reconcile_running',return_value='fast'):self.s.fast_only()
 def test_active_model_change_blocked(self):
  self.s.state={'status':'recording'}
  with self.assertRaisesRegex(ValueError,'Stop'):self.s.release_idle()
 def test_idle_model_released(self):
  p=MagicMock();p.poll.return_value=None;self.s.worker=p;self.s.release_idle();p.terminate.assert_called_once();p.wait.assert_called_once();self.assertIsNone(self.s.worker)
 def test_stop_signals_live_worker(self):
  p=MagicMock();p.poll.return_value=None;self.s.worker=p;self.s.state={'status':'recording'};self.s.stop();p.stdin.write.assert_called_once_with('{"op":"stop"}\n');self.assertEqual(self.s.state['status'],'transcribing')
 def test_unstarted_stop_rejected(self):
  with self.assertRaises(ValueError):self.s.stop()
 def test_no_chat_pause_in_live_controller(self):
  source=Path(speech_live.__file__).read_text(encoding='utf8');self.assertNotIn('pause_for_media',source);self.assertNotIn('ensure_selected',source)
 def test_join_boundaries(self):
  worker=Path(speech_input.__file__).parent/'assets/speech-input/pro_worker.py';spec=importlib.util.spec_from_file_location('pro_test',worker);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
  self.assertEqual(mod.join_text('hello world','world again'),'hello world again');self.assertEqual(mod.join_text('Hello,','hello there'),'Hello, there');self.assertEqual(mod.join_text('','test'),'test')
 def test_no_auto_send(self):
  js=(Path(speech_input.__file__).parent/'assets/speech-input.js').read_text(encoding='utf8');self.assertIn('s.partial',js);self.assertIn('stopImmediatePropagation',js);self.assertIn("e.detail.active==='fast'",js)
if __name__=='__main__':unittest.main()
