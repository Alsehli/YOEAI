"""Advanced multimodal chat extension; protected legacy runtime stays unchanged.
The caller holds the existing shared inference gate for this whole request.
"""
import json,http.client
from configuration import read_config

def route(handler):
 c=read_config()
 if handler.path!='/v1/chat/completions' or c.get('modelMode')!='advanced':return False
 if not handler.allowed():handler.json(403,{'error':'Only the local interface may access this service.'});return True
 try:
  if handler.headers.get('Transfer-Encoding'):raise ValueError('Transfer encoding is not supported.')
  raw=handler.headers.get('Content-Length')
  if raw is None:handler.json(411,{'error':'Content-Length is required.'});return True
  length=int(raw)
  if length<0:raise ValueError('Invalid Content-Length.')
  if length>25000000:handler.json(413,{'error':'Image or request is too large.'});return True
  body=handler.rfile.read(length);payload=json.loads(body)
  if not isinstance(payload,dict) or not isinstance(payload.get('messages'),list):raise ValueError('Invalid chat messages.')
  if any(isinstance(m.get('content'),list) and any(x.get('type')=='image_url' for x in m['content']) for m in payload['messages']):
   from model_modes import require_advanced_vision
   require_advanced_vision(c)
  upstream=http.client.HTTPConnection('127.0.0.1',c['apiPort'],timeout=180)
  try:
   upstream.request('POST',handler.path,body,{'Content-Type':'application/json'});response=upstream.getresponse()
   handler.send_response(response.status);handler.send_header('Content-Type',response.getheader('Content-Type','application/json'));handler.send_header('Cache-Control','no-store');handler.end_headers()
   while True:
    chunk=response.read1(8192)
    if not chunk:break
    handler.wfile.write(chunk);handler.wfile.flush()
  finally:upstream.close()
 except (BrokenPipeError,ConnectionResetError):pass
 except Exception as ex:
  try:handler.json(400,{'error':str(ex)})
  except Exception:pass
 return True
