import json,unittest
from unittest.mock import patch,MagicMock
import interactive_voice as v
class InteractiveTests(unittest.TestCase):
 def setUp(self):self.s=v.VoiceSession()
 def tearDown(self):self.s.end()
 def test_explicit_start(self):
  with self.assertRaisesRegex(ValueError,'explicitly'):self.s.start({})
 def test_no_models_when_settings_missing(self):
  with patch.object(v,'APP_DIR',__import__('pathlib').Path('Z:/missing-test-folder')):
   with self.assertRaisesRegex(ValueError,'not installed'):self.s.settings()
 def test_snapshot_is_deep_copy(self):
  copy=self.s.snapshot();copy['messages'].append({});self.assertEqual(self.s.state['messages'],[])
 def test_old_worker_failure_cannot_end_new_session(self):
  self.s.state.update(id='old',active=True);p=MagicMock();p.poll.return_value=None
  def stale():
   self.s.state['id']='new';raise OSError('Old worker ended');yield ''
  p.stdout=stale()
  with patch.object(v.subprocess,'Popen',return_value=p),patch.object(self.s,'end') as end:
   self.s.run({'python':'python.exe','worker':'worker.py'},'old');end.assert_not_called()
  self.assertTrue(self.s.state['active'])
 def test_stale_speech_dropped(self):
  p=MagicMock();p.poll.return_value=None;self.s.worker=p;self.s.generation=3;self.s.send({'op':'speak','generation':2,'text':'old'});p.stdin.write.assert_not_called()
 def test_current_speech_allowed(self):
  p=MagicMock();p.poll.return_value=None;self.s.worker=p;self.s.generation=3;self.s.send({'op':'speak','generation':3,'text':'new'});p.stdin.write.assert_called_once()
 def test_end_stops_audio_process(self):
  p=MagicMock();p.poll.return_value=None;self.s.worker=p;self.s.state['active']=True;self.s.end();p.terminate.assert_called_once();self.assertFalse(self.s.state['active'])
 def test_active_blocks_model_changes(self):
  self.s.state['active']=True
  with self.assertRaisesRegex(ValueError,'End Interactive'):self.s.release_idle()
 def test_handoff_requires_exact_confirmation(self):
  self.s.state['handoff']={'agent':'windows','objective':'delete something','turn':5}
  for body in ({},{'approve':True,'agent':'windows','turn':4},{'approve':True,'agent':'code','turn':5}):
   with self.assertRaisesRegex(ValueError,'exact'):self.s.handoff(body)
 def test_windows_handoff_advisor_only(self):
  self.s.state['handoff']={'agent':'windows','objective':'open notepad','turn':5};e=MagicMock();e.create.return_value={'id':'test'}
  with patch('mini_agents.engine',return_value=e):self.s.handoff({'approve':True,'agent':'windows','turn':5})
  args=e.create.call_args.args[0];self.assertEqual(args['windows']['mode'],'ADVISOR');self.assertFalse(args['permissions']['web']);self.assertFalse(args['permissions']['readProject'])
 def test_utterance_does_not_execute_tools(self):
  self.s.target='main';self.s.worker=MagicMock();self.s.worker.poll.return_value=None
  with patch.object(v.threading,'Thread') as thread,patch('mini_agents.engine') as engine:self.s.event({'event':'utterance','text':'delete all files','asrSeconds':.1});engine.assert_not_called();thread.assert_called_once()
 def test_speech_profile_has_no_markdown_or_action_claims(self):
  self.assertIn('No Markdown',v.PROFILE);self.assertIn('no execution tools',v.PROFILE)
 def test_clean_spoken_text(self):self.assertEqual(v.clean_speech('**Hello** [world](https://example.com)'),'Hello world')
 def test_external_origin_blocked(self):
  h=MagicMock();h.path='/interactive/start';h.allowed.return_value=True;h.headers={'Host':'127.0.0.1:8092','Origin':'https://external.example'};v.route(h,True);self.assertEqual(h.json.call_args.args[0],403)
 def test_oversized_body_blocked(self):
  h=MagicMock();h.path='/interactive/start';h.allowed.return_value=True;h.headers={'Host':'127.0.0.1:8092','Origin':'http://127.0.0.1:8092','Content-Length':'2000'}
  with patch.object(v,'session',return_value=self.s):v.route(h,True)
  self.assertEqual(h.json.call_args.args[0],400)
if __name__=='__main__':unittest.main()
