import io,json,unittest
from unittest.mock import Mock,patch
import runtime
from windows_policy import plan_schema,TOPICS

class AuditRegressions(unittest.TestCase):
 def test_windows_schema_only_allows_supported_diagnostics(self):
  topic=plan_schema()['properties']['steps']['items']['properties']['params']['properties']['topic']
  self.assertEqual(topic.get('enum'),list(TOPICS))
 def test_cancelled_chat_closes_backend_connection(self):
  body=json.dumps({'messages':[{'role':'user','content':'hello'}]}).encode()
  h=object.__new__(runtime.Handler);h.path='/v1/chat/completions';h.headers={'Content-Length':str(len(body))};h.rfile=io.BytesIO(body);h.wfile=Mock();h.wfile.write.side_effect=BrokenPipeError();h.allowed=lambda:True;h.send_response=Mock();h.send_header=Mock();h.end_headers=Mock();h.json=Mock()
  upstream=Mock();response=upstream.getresponse.return_value;response.status=200;response.getheader.return_value='text/event-stream';response.read1.return_value=b'data: {}\n\n'
  with patch.object(runtime,'read_config',return_value={'apiPort':8080}),patch.object(runtime.http.client,'HTTPConnection',return_value=upstream):h.do_POST()
  upstream.close.assert_called_once()

if __name__=='__main__':unittest.main()
