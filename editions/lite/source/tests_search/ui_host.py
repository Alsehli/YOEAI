"""Isolated host for the existing UI and production research routes; reuse loaded native model.
No installed files/profile writes, new inference worker, generation feature tests or E: deployment.
"""
import sys,json,urllib.request,urllib.error,time,mimetypes
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from local_model_client import Client,BASE
from intelligence import routes
from intelligence.service import Service
source=Path(__file__).resolve().parents[1];root=source.parents[1];home=root/'Lite/Search-UI-QA/ConversationProfile';home.mkdir(parents=True,exist_ok=True)
client=Client();routes.INSTANCE=Service(home,root,client);port=18087
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def allowed(self):return self.headers.get('Host')==f'127.0.0.1:{port}' and self.headers.get('Origin',f'http://127.0.0.1:{port}')==f'http://127.0.0.1:{port}'
 def reply(self,code,value):self.send_bytes(code,json.dumps(value).encode(),'application/json')
 def send_bytes(self,code,body,kind):
  self.send_response(code);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body)
 def proxy(self,post):
  raw=self.rfile.read(int(self.headers.get('Content-Length','0'))) if post else None
  req=urllib.request.Request(BASE+self.path,raw,{'Content-Type':'application/json','Origin':BASE})
  try:
   with urllib.request.urlopen(req,timeout=120) as response:
    if self.path=='/v1/chat/completions':
     self.send_response(200);self.send_header('Content-Type','text/event-stream');self.send_header('Cache-Control','no-store');self.end_headers()
     for line in response:self.wfile.write(line);self.wfile.flush()
    else:self.send_bytes(response.status,response.read(4000000),response.headers.get('Content-Type','application/json'))
  except urllib.error.HTTPError as e:self.send_bytes(e.code,e.read(10000),'application/json')
 def do_GET(self):
  if not self.allowed():return self.reply(403,{'error':'local test host only'})
  if routes.route(self,False,home,root,'Lite'):return
  if self.path=='/':return self.send_bytes(200,(source/'ui.html').read_bytes(),'text/html; charset=utf-8')
  if self.path.startswith('/assets/'):
   p=(source/self.path.lstrip('/')).resolve()
   if not p.is_relative_to(source/'assets') or not p.is_file():return self.reply(404,{'error':'asset'})
   return self.send_bytes(200,p.read_bytes(),mimetypes.guess_type(str(p))[0] or 'application/octet-stream')
  return self.proxy(False)
 def do_POST(self):
  if not self.allowed():return self.reply(403,{'error':'local test host only'})
  if self.path=='/assistant/fit':return self.proxy(True)
  if routes.route(self,True,home,root,'Lite'):return
  return self.proxy(True)
server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
print('Existing YOEAI UI test host: http://127.0.0.1:18087; inference reused on 8087',flush=True)
try:server.serve_forever()
finally:routes.shutdown();server.server_close()
