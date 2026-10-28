import unittest,tempfile,json,threading,time,http.server,socketserver
from pathlib import Path
from unittest.mock import patch
from mini_agents import Engine,GATE
import writing_check as w
class FlowAudit(unittest.TestCase):
 def test_task_summaries_preserve_selected_and_hide_private_fields(self):
  with tempfile.TemporaryDirectory() as tmp:
   e=Engine(Path(tmp),infer=lambda *a:'fixture')
   try:
    with e.connect() as db:
     for i in range(3):
      t={'id':str(i),'agent':'code','objective':'Fixture','status':'COMPLETED','created':1,'updated':2,'result':'x'*10000,'documents':[{'text':'private fixture'}],'snapshots':{'a':'b'},'memory':{},'recall':[]};db.execute('INSERT INTO tasks VALUES(?,?,?)',(t['id'],'code',json.dumps(t)))
    rows=e.state_tasks('1');self.assertEqual(len(rows),3);selected=next(t for t in rows if t['id']=='1');self.assertEqual(len(selected['result']),10000);self.assertNotIn('documents',selected);self.assertNotIn('snapshots',selected);self.assertNotIn('result',next(t for t in rows if t['id']=='2'));self.assertEqual(len(e.state_tasks(None)),3)
   finally:e.closed=True;e.worker.join(3)
 def test_cancel_before_request_is_not_lost(self):
  identifier='a'*32;self.assertTrue(w.cancel_job(identifier));job=w.begin_job(identifier)
  try:self.assertTrue(job['cancel'].is_set())
  finally:
   with w._jobs_lock:w._jobs.pop(identifier,None)
 def test_cancellable_stream_decodes_chunked_model_reply(self):
  content=json.dumps({'edits':[{'original':'I has','replacement':'I have','reason':'Agreement'}]})
  body=('data: '+json.dumps({'choices':[{'delta':{'content':None}}]})+'\n\n'+'data: '+json.dumps({'choices':[{'delta':{'content':content}}]})+'\n\ndata: [DONE]\n\n').encode()
  class Model(http.server.BaseHTTPRequestHandler):
   protocol_version='HTTP/1.1'
   def log_message(self,*a):pass
   def do_POST(self):
    self.rfile.read(int(self.headers['Content-Length']));self.send_response(200);self.send_header('Transfer-Encoding','chunked');self.send_header('Connection','close');self.end_headers();self.wfile.write(('%x\r\n'%len(body)).encode()+body+b'\r\n0\r\n\r\n')
  server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Model);threading.Thread(target=server.serve_forever,daemon=True).start()
  try:self.assertEqual(w.check('I has a dog.',server.server_port,{'cancel':threading.Event()})[0]['replacement'],'I have')
  finally:server.shutdown();server.server_close()
 def test_asset_revalidation_and_changed_file(self):
  import urllib.request,urllib.error
  from presentation import PresentationHandler
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);asset=root/'assets';asset.mkdir();file=asset/'fixture.js';file.write_text('window.fixture=1',encoding='utf-8')
   server=http.server.ThreadingHTTPServer(('127.0.0.1',0),PresentationHandler);threading.Thread(target=server.serve_forever,daemon=True).start();url='http://127.0.0.1:'+str(server.server_port)+'/assets/fixture.js'
   try:
    with patch('presentation.APP_DIR',root),patch('runtime.read_config',return_value={'uiPort':server.server_port}):
     response=urllib.request.urlopen(url);etag=response.headers['ETag'];self.assertEqual(response.read(),b'window.fixture=1');self.assertEqual(response.headers['Cache-Control'],'private, no-cache');response.close()
     with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(urllib.request.Request(url,headers={'If-None-Match':etag}))
     self.assertEqual(error.exception.code,304)
     file.write_text('window.fixture=22',encoding='utf-8');response=urllib.request.urlopen(urllib.request.Request(url,headers={'If-None-Match':etag}));self.assertNotEqual(response.headers['ETag'],etag);self.assertEqual(response.read(),b'window.fixture=22');response.close()
   finally:server.shutdown();server.server_close()
 def test_writing_yields_to_send_and_releases_shared_gate(self):
  entered=threading.Event();release=threading.Event();result={}
  class Model(http.server.BaseHTTPRequestHandler):
   def log_message(self,*a):pass
   def do_POST(self):
    self.rfile.read(int(self.headers['Content-Length']));entered.set();release.wait(5)
    with __import__('contextlib').suppress(OSError):self.send_response(200);self.end_headers();self.wfile.write(b'{}')
  server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Model);threading.Thread(target=server.serve_forever,daemon=True).start();identifier='b'*32
  class Request:
   path='/writing/check';headers={'Content-Length':'0','Origin':'http://127.0.0.1:8098','Host':'127.0.0.1:8098'}
   def allowed(self):return True
   def json(self,status,value):result.update(value)
  import io
  h=Request();body=json.dumps({'id':identifier,'text':'I has a dog.'}).encode();h.headers=dict(h.headers,**{'Content-Length':str(len(body))});h.rfile=io.BytesIO(body)
  try:
   with patch('configuration.read_config',return_value={'apiPort':server.server_port}):
    thread=threading.Thread(target=lambda:w.route(h,True));thread.start();self.assertTrue(entered.wait(3));started=time.perf_counter();self.assertTrue(w.cancel_job(identifier));thread.join(2);self.assertFalse(thread.is_alive());self.assertLess(time.perf_counter()-started,1.5);self.assertTrue(GATE.acquire(False));GATE.release()
  finally:release.set();server.shutdown();server.server_close()
if __name__=='__main__':unittest.main()


