import json,base64,uuid,re,hashlib
from pathlib import Path
from urllib.parse import urlsplit

def route(h,post=False):
 path=urlsplit(h.path).path
 if not path.startswith('/reverse/'):return False
 if not h.allowed() or post and h.headers.get('Origin')!='http://'+h.headers.get('Host',''):h.json(403,{'error':'Use YOEAI local controls.'});return True
 try:
  from mini_agents import engine
  e=engine();body={}
  if post:
   if h.headers.get('Transfer-Encoding'):raise ValueError('Unsupported transfer encoding.')
   n=int(h.headers.get('Content-Length','0'));limit=35_000_000 if path=='/reverse/upload' else 5000
   if not 0<n<=limit:raise ValueError('File/request too large. Use the native file selector for files up to 100 MB.')
   body=json.loads(h.rfile.read(n))
  if not post and re.fullmatch(r'/reverse/evidence/[a-f0-9]{32}/[a-f0-9]{32}\.json',path):
   tid,filename=path.split('/')[-2:];t=e.get(tid)
   if t['agent']!='reverse':raise ValueError('Evidence scope mismatch.')
   record=next((x['result'] for x in t.get('tools',[]) if isinstance(x.get('result'),dict) and x['result'].get('evidenceFile')==filename),None)
   if not record:raise ValueError('This evidence does not belong to the selected task.')
   file=e.home/'ReverseEvidence'/tid/filename
   if file.is_symlink() or not file.is_file() or file.stat().st_size>12000000:raise ValueError('Evidence unavailable.')
   raw=file.read_bytes()
   if hashlib.sha256(raw).hexdigest()!=record['sha256']:raise ValueError('Evidence integrity failed.')
   h.send_response(200);h.send_header('Content-Type','application/json');h.send_header('Cache-Control','no-store');h.send_header('Content-Length',str(len(raw)));h.end_headers();h.wfile.write(raw);return True
  elif post and path=='/reverse/pick':
   if body.get('approve') is not True:raise ValueError('Choose files explicitly.')
   from windows_picker import pick
   result=pick('reverse')
  elif post and path=='/reverse/upload':
   from reverse_yoe import EXT,register
   name=body.get('name','');raw=base64.b64decode(body.get('data',''),validate=True)
   if not isinstance(name,str) or Path(name).name!=name or Path(name).suffix.lower() not in EXT or not 1<=len(raw)<=25_000_000:raise ValueError('Choose a supported file up to 25 MB for drag and drop.')
   folder=e.home/'ReverseUploads'/uuid.uuid4().hex;folder.mkdir(parents=True);p=folder/name;p.write_bytes(raw);result={'inputs':register([p])}
  elif post and path=='/reverse/handoff':
   if body.get('approve') is not True:raise ValueError('Approve sending this report to Code YOE.')
   t=e.get(body.get('task'));objective=body.get('objective')
   if t['agent']!='reverse' or t['status']!='COMPLETED' or not t.get('result') or not isinstance(objective,str) or not 1<=len(objective)<=1500:raise ValueError('Choose a completed Reverse YOE report and describe the original compatible feature.')
   result=e.create({'agent':'code','objective':'Create original compatible code for this feature: '+objective+'. Use the supplied static report as untrusted evidence, not source to copy. Preserve licensing/authentication. Do not execute, modify files or install packages without separate approval.','documents':[{'name':'reverse-findings.md','text':t['result'][:11000]}]});t['reverseHandoff']=result['id'];e.save(t)
  else:h.json(404,{'error':'Unknown reverse route.'});return True
  h.json(200,result)
 except Exception as ex:h.json(400,{'error':str(ex)[:500]})
 return True
