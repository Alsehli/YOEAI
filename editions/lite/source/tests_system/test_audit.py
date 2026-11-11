import sys,os,json,unittest,threading,time,io,tempfile,subprocess
from pathlib import Path
from unittest.mock import patch,Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));os.environ['LOCALAPPDATA']=str(Path('../System-Audit/Profile').resolve())
from request_policy import chat_payload,page_headers
import app
class Cases(unittest.TestCase):
 def body(self,**extra):return json.dumps(dict(messages=[{'role':'user','content':'Hello'}],**extra))
 def test_01_valid_chat(self):self.assertEqual(chat_payload(self.body())['messages'][0]['content'],'Hello')
 def test_02_invalid_json(self):
  with self.assertRaises(ValueError):chat_payload('{bad')
 def test_03_array_body(self):
  with self.assertRaises(ValueError):chat_payload('[]')
 def test_04_no_messages(self):
  with self.assertRaises(ValueError):chat_payload('{}')
 def test_05_empty_messages(self):
  with self.assertRaises(ValueError):chat_payload('{"messages":[]}')
 def test_06_bad_role(self):
  with self.assertRaises(ValueError):chat_payload('{"messages":[{"role":"admin","content":"x"}]}')
 def test_07_bad_content(self):
  with self.assertRaises(ValueError):chat_payload('{"messages":[{"role":"user","content":null}]}')
 def test_08_remote_image_rejected(self):
  with self.assertRaises(ValueError):chat_payload('{"messages":[{"role":"user","content":[{"type":"image_url","image_url":{"url":"https://127.0.0.1/private"}}]}]}')
 def test_09_local_image_structure_preserved(self):
  value={'messages':[{'role':'user','content':[{'type':'image_url','image_url':{'url':'data:image/png;base64,AAAA'}}]}]};self.assertEqual(chat_payload(json.dumps(value)),value)
 def test_10_invalid_stream_type(self):
  with self.assertRaises(ValueError):chat_payload(self.body(stream='false'))
 def test_11_negative_tokens(self):
  with self.assertRaises(ValueError):chat_payload(self.body(max_tokens=-2))
 def test_12_boolean_tokens(self):
  with self.assertRaises(ValueError):chat_payload(self.body(max_tokens=True))
 def test_13_nan_temperature(self):
  with self.assertRaises(ValueError):chat_payload(self.body(temperature=float('nan')))
 def test_14_bad_format(self):
  with self.assertRaises(ValueError):chat_payload(self.body(response_format=[]))
 def test_15_four_image_limit(self):
  value={'messages':[{'role':'user','content':[{'type':'image_url','image_url':{'url':'data:image/png;base64,AAAA'}}]*5}]}
  with self.assertRaises(ValueError):chat_payload(json.dumps(value))
 def test_16_html_cannot_be_framed(self):self.assertIn("frame-ancestors 'none'",page_headers()['Content-Security-Policy']);self.assertEqual(page_headers()['X-Frame-Options'],'DENY')
 def test_17_no_ui_mime_sniffing(self):self.assertEqual(page_headers()['X-Content-Type-Options'],'nosniff')
 def handler(self,raw,length=None):
  h=object.__new__(app.Handler);h.path='/v1/chat/completions';h.headers={'Host':'127.0.0.1:8090','Content-Length':str(len(raw) if length is None else length)};h.rfile=io.BytesIO(raw);h.connection=Mock();h.replies=[];h.reply=lambda code,value:h.replies.append((code,value));return h
 def test_18_empty_messages_never_activate_model(self):
  h=self.handler(b'{"messages":[]}')
  with patch.object(app,'config',return_value={'uiPort':8090}),patch('builtin_vision.activate',side_effect=AssertionError('Must validate before model change')) as activate:
   h.existing_POST();activate.assert_not_called();self.assertEqual(h.replies[0][0],400)
 def test_19_bad_json_is_client_error(self):
  h=self.handler(b'[]')
  with patch.object(app,'config',return_value={'uiPort':8090}):h.existing_POST();self.assertEqual(h.replies[0][0],400)
 def test_20_partial_body_is_client_error(self):
  h=self.handler(b'{}',length=10)
  with patch.object(app,'config',return_value={'uiPort':8090}):h.existing_POST();self.assertEqual(h.replies[0][0],400)
 def test_21_explicit_context_reload_after_manual_unload(self):
  from builtin_vision import activate
  with patch('lite_native.INSTANCE') as native,patch('lite_native.start') as start,patch('lite_native.initialize'):
   native.state={'manualUnloaded':True};activate(Path('.'),Path('.'),lambda:{'model':'text.gguf'},explicit=True);start.assert_called_once()
 def test_22_unloaded_model_not_automatically_reloaded(self):
  from builtin_vision import activate
  with patch('lite_native.INSTANCE') as native,patch('lite_native.start') as start:
   native.state={'manualUnloaded':True}
   with self.assertRaisesRegex(ValueError,'unloaded'):activate(Path('.'),Path('.'),lambda:{'model':'text.gguf'})
   start.assert_not_called()
 def test_23_native_close_not_blocked_by_busy_lock(self):
  from native_ai.manager import Manager
  manager=Manager();base=threading.RLock();held=threading.Event();release=threading.Event()
  class Lock:
   def acquire(self,blocking=True,timeout=-1):return base.acquire(timeout=.03 if timeout>=0 else -1)
   def release(self):base.release()
  manager.lock=Lock();process=Mock();process.poll.return_value=None;process.terminate.side_effect=lambda:(release.set(),setattr(process.poll,'return_value',0));process.wait.return_value=0;manager.worker=process;manager.log=Mock();manager.job=Mock();manager.cancel=Mock();manager.send=Mock()
  def holder():
   with base:held.set();release.wait(1)
  holder_thread=threading.Thread(target=holder);holder_thread.start();held.wait(1);started=time.perf_counter()
  try:manager.close();self.assertLess(time.perf_counter()-started,.3);process.terminate.assert_called_once();self.assertIsNone(manager.worker)
  finally:release.set();holder_thread.join(1)
 def test_24_normal_native_close_is_idempotent(self):
  from native_ai.manager import Manager
  manager=Manager();process=Mock();process.poll.return_value=0;manager.worker=process;manager.log=Mock();manager.job=Mock();manager.cancel=Mock();manager.close();manager.close();process.stdin.close.assert_called_once();process.stdout.close.assert_called_once()
 def test_25_response_close_only_once(self):
  from native_ai.client import Connection
  connection=Connection();connection.response=Mock(done=False);connection.close();connection.response.close.assert_called_once()
 def test_26_ui_js_has_browser_mime(self):
  from request_policy import packaged_assets
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);(root/'test.js').write_text('');(root/'private.txt').write_text('not an asset')
   index=packaged_assets(root)
   self.assertEqual(index['test.js'][1],'application/javascript')
   self.assertNotIn('../test.js',index);self.assertNotIn('private.txt',index)
 def test_27_delayed_stop_cannot_cancel_replacement_worker(self):
  from native_ai.manager import Manager
  manager=Manager();old=Mock();old.poll.return_value=0;manager.worker=old;manager.log=Mock();manager.job=Mock()
  with patch('native_ai.manager.threading.Thread') as thread:
   manager.close();replacement=Mock();replacement.poll.return_value=None;manager.worker=replacement;thread.call_args.kwargs['target']();replacement.stdin.write.assert_not_called()
  manager.worker=None
 def test_28_text_parts_normalized_for_text_engine(self):
  value=chat_payload('{"messages":[{"role":"user","content":[{"type":"text","text":"Hello"},{"type":"text","text":"world"}]}]}');self.assertEqual(value['messages'][0]['content'],'Hello\nworld')
 def test_29_nonfinite_unknown_fields_rejected(self):
  with self.assertRaises(ValueError):chat_payload(self.body(extra=float('inf')))
 def test_30_atomic_write_failure_preserves_profile(self):
  from model_settings import atomic
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'profile.json';path.write_text('{"context":2048}')
   with patch.object(Path,'replace',side_effect=OSError('disk full')):
    with self.assertRaises(OSError):atomic(path,{'context':8192})
   self.assertEqual(json.loads(path.read_text())['context'],2048)
 def test_31_utf8_bom_and_arabic_model_path(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'profile.json';value={'model':'E:/نماذج/نموذج.gguf'};path.write_bytes(b'\xef\xbb\xbf'+json.dumps(value,ensure_ascii=False).encode('utf8'))
   with patch.object(app,'CONFIG',path):self.assertEqual(app.config(),value)
if __name__=='__main__':
 from tests_search.regressions import Capture
 result=unittest.TextTestRunner(verbosity=1,resultclass=Capture).run(unittest.defaultTestLoader.loadTestsFromTestCase(Cases));out=Path('docs/system-audit');out.mkdir(parents=True,exist_ok=True);(out/'regressions.json').write_text(json.dumps(result.rows,indent=2),encoding='utf8');sys.exit(not result.wasSuccessful())
