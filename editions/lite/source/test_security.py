import io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
import app
class Tests(unittest.TestCase):
 def handler(self,path,body=b'{}',headers=None):
  h=object.__new__(app.Handler);h.path=path;h.headers=headers or {'Host':'127.0.0.1:8090','Content-Length':str(len(body))};h.rfile=io.BytesIO(body);h.connection=Mock();h.server=Mock();h.replies=[];h.reply=lambda code,data:h.replies.append((code,data));return h
 def test_negative_length_does_not_read(self):
  h=self.handler('/v1/chat/completions',headers={'Host':'127.0.0.1:8090','Content-Length':'-1'})
  with patch.object(app,'config',return_value={'uiPort':8090}),patch.object(h.rfile,'read',side_effect=AssertionError('Negative body length must not be read')):h.do_POST()
  self.assertEqual(h.replies[0][0],400)
 def test_foreign_origin(self):
  h=self.handler('/context',headers={'Host':'127.0.0.1:8090','Origin':'https://foreign.invalid','Content-Length':'2'})
  with patch.object(app,'config',return_value={'uiPort':8090}):h.do_POST()
  self.assertEqual(h.replies[0][0],403)
 def test_shutdown_requires_token(self):
  with tempfile.TemporaryDirectory() as folder:
   state=Path(folder)/'ui.json';state.write_text(json.dumps({'token':'expected'}));h=self.handler('/shutdown',b'{"token":"wrong"}')
   with patch.object(app,'config',return_value={'uiPort':8090}),patch.object(app,'UI_STATE',state):h.do_POST()
   self.assertEqual(h.replies[0][0],403);h.server.shutdown.assert_not_called()
 def test_context_never_stops_original(self):
  h=self.handler('/context',b'{"context":16384}')
  with patch.object(app,'config',return_value={'uiPort':8090}),patch.object(app,'stop_engine') as stop:h.do_POST();stop.assert_not_called()
  self.assertEqual(h.replies[0][0],400)
 def test_stale_pid_is_not_stopped(self):
  with tempfile.TemporaryDirectory() as folder:
   state=Path(folder)/'engine.json';state.write_text(json.dumps({'pid':10,'identity':{'exe':'expected','created':1}}))
   with patch.object(app,'STATE',state),patch.object(app,'identity',return_value={'exe':'different','created':2}),self.assertRaises(RuntimeError):app.stop_engine()
 def test_8192_context_is_accepted(self):
  h=self.handler('/context',b'{"context":8192}')
  with tempfile.TemporaryDirectory() as folder,patch.object(app,'config',return_value={'uiPort':8090,'context':2048}),patch.object(app,'CONFIG',Path(folder)/'profile.json'),patch.object(app,'stop_engine'),patch.object(app,'start') as start:
   h.do_POST();start.assert_called_once();self.assertEqual(h.replies[0][0],200)
 def test_failed_context_restores_previous_profile(self):
  h=self.handler('/context',b'{"context":8192}')
  with tempfile.TemporaryDirectory() as folder:
   config_file=Path(folder)/'profile.json'
   with patch.object(app,'config',return_value={'uiPort':8090,'context':2048}),patch.object(app,'CONFIG',config_file),patch.object(app,'stop_engine'),patch.object(app,'start',side_effect=[RuntimeError('memory exhausted'),None]) as start:
    h.do_POST();self.assertEqual(h.replies[0][0],500);self.assertEqual(json.loads(config_file.read_text())['context'],2048);self.assertEqual(start.call_count,2)
if __name__=='__main__':unittest.main(verbosity=2)
