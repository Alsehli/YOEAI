import io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,MagicMock
import speech_input as module

class SpeechInputTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
  self.home=patch.object(module,'HOME',self.root);self.home.start()
  self.s=module.Dictation(self.root/'config.json')
 def tearDown(self):self.s.cancel();self.home.stop();self.tmp.cleanup()
 def test_explicit_activation_required(self):
  with self.assertRaisesRegex(ValueError,'explicitly'):self.s.start(False)
 def test_missing_install_is_clear(self):
  with self.assertRaisesRegex(ValueError,'not installed'):self.s.start(True)
 def test_second_recording_rejected(self):
  self.s.state={'status':'recording'}
  with patch.object(self.s,'settings',return_value={}):
   with self.assertRaisesRegex(ValueError,'current'):self.s.start(True)
 def test_stop_requires_recording(self):
  with self.assertRaisesRegex(ValueError,'No active'):self.s.stop()
 def test_stop_signals_capture_only(self):
  self.s.state={'status':'recording'};p=MagicMock();p.poll.return_value=None;self.s.capture=p;self.s.stop();p.stdin.write.assert_called_once_with('stop\n');p.terminate.assert_not_called()
 def test_cancel_terminates_capture_and_inference(self):
  p=MagicMock();p.poll.return_value=None;self.s.capture=p;self.s.worker=p;self.s.cancel();self.assertTrue(self.s.cancelled.is_set());self.assertIsNone(self.s.worker)
 def test_worker_environment_offline(self):
  with patch.object(module.subprocess,'Popen') as launch:
   self.s.launch(['record'],{'python':'python.exe','worker':'worker.py','cache':'local-cache'})
   env=launch.call_args.kwargs['env'];self.assertEqual(env['HF_HUB_OFFLINE'],'1');self.assertEqual(env['HF_HOME'],'local-cache');self.assertNotIn('PYTHONPATH',env)
 def test_cancel_interrupts_result_wait(self):
  self.s.cancelled.set()
  with self.assertRaises(InterruptedError):self.s.reply(1)
 def test_worker_exit_is_error(self):
  p=MagicMock();p.stdout=io.StringIO('not-json\n');self.s.reader(p,self.s.messages);self.assertEqual(self.s.messages.get()['status'],'error')
 def test_status_is_snapshot(self):
  a=self.s.status();a['status']='recording';self.assertEqual(self.s.state['status'],'idle')
 def test_route_blocks_external_origin(self):
  h=MagicMock();h.path='/dictation/start';h.allowed.return_value=True;h.headers={'Origin':'https://other.example','Host':'127.0.0.1:8092'};self.assertTrue(module.route(h,True));self.assertEqual(h.json.call_args.args[0],403)
 def test_route_blocks_transfer_encoding(self):
  h=MagicMock();h.path='/dictation/start';h.allowed.return_value=True;h.headers={'Origin':'http://127.0.0.1:8092','Host':'127.0.0.1:8092','Transfer-Encoding':'chunked','Content-Length':'1'}
  with patch.object(module,'service',return_value=self.s):module.route(h,True)
  self.assertEqual(h.json.call_args.args[0],400)
 def test_ui_never_submits(self):
  js=(Path(module.__file__).parent/'assets/speech-input.js').read_text(encoding='utf8')
  self.assertNotIn('.click()',js);self.assertNotIn('requestSubmit',js);self.assertIn("type='button'",js)

if __name__=='__main__':unittest.main()
