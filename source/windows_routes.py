"""Same-origin Windows YOE controls; screenshots are task-scoped local files."""
import json,re,time,uuid
from pathlib import Path
from urllib.parse import urlsplit
from windows_policy import SPECS,APPS,MODES,make_scope,redact,reject_secret

def route_windows(handler,e,body,post):
 path=urlsplit(handler.path).path
 if path.startswith('/mini/windows/files/'):
  from windows_explorer import route
  return route(handler,e,body,post)
 try:
  if post and path=='/mini/windows/pick':
   if body.get('approve') is not True:raise ValueError('Open the selection dialog yourself.')
   from windows_picker import pick
   value=pick(body.get('kind'),body.get('folder'))
  elif not post and path=='/mini/windows/capabilities':
   from windows_tools import app_paths,PS
   value={'enabled':e.windows_enabled,'apps':app_paths(),'modes':MODES,'tools':{name:{'description':info[0],'risk':info[1],'parameters':info[2]} for name,info in SPECS.items()},'diagnosticCommands':PS,'coordinateFallback':False,'arbitraryShell':False,'browserProfile':'Isolated; no personal browser sessions','vision':'Existing model; live image test required for each installed configuration.'}
  elif post and path=='/mini/windows/enable':
   if body.get('approve') is not True or type(body.get('enabled'))!=bool:raise ValueError('Explicit enable/disable choice is required.')
   e.windows_enabled=body['enabled']
   if not e.windows_enabled:
    if hasattr(e,'file_explorer'):
     for job in list(e.file_explorer.jobs.values()):job['cancel'].set()
    for t in e.tasks():
     if t['agent']=='windows' and t['status'] not in ['COMPLETED','FAILED','CANCELLED']:e.cancel(t['id'])
   value={'enabled':e.windows_enabled,'notice':'Session-only. Closing the app disables new Windows tasks.'}
  elif not post and path=='/mini/windows/workflows':
   with e.connect() as db:value=[{'id':r[0],'name':r[1],**json.loads(r[2])} for r in db.execute('SELECT id,name,data FROM windows_workflows ORDER BY name')]
  elif post and path=='/mini/windows/workflows':
   if body.get('approve') is not True:raise ValueError('Approve saving this local workflow.')
   t=e.get(body.get('task'));name=body.get('name','')
   if t['agent']!='windows' or not isinstance(name,str) or not 1<=len(name.strip())<=80:raise ValueError('Choose a Windows task and a workflow name of 1–80 characters.')
   reject_secret(name);data={'objective':t['objective'],'windows':t['windows']['scope'],'created':time.time(),'notice':'Template only. Loading it creates a fresh plan and permission requests, never replays actions.'};wid=uuid.uuid4().hex
   with e.connect() as db:db.execute('INSERT INTO windows_workflows VALUES(?,?,?)',(wid,name.strip(),json.dumps(data)))
   value={'id':wid,'status':'saved'}
  elif post and path=='/mini/windows/workflows/delete':
   if body.get('approve') is not True:raise ValueError('Confirm workflow deletion.')
   with e.connect() as db:db.execute('DELETE FROM windows_workflows WHERE id=?',(body.get('id'),))
   value={'status':'deleted'}
  elif not post and re.fullmatch(r'/mini/windows/screenshot/[0-9a-f]{32}/[0-9a-f]{64}\.jpg',path):
   parts=path.split('/');tid=parts[-2];name=parts[-1];t=e.get(tid)
   if t['agent']!='windows':raise ValueError('Screenshot task scope mismatch.')
   folder=e.home/'WindowsShots'/tid;p=folder/name
   if not p.is_file() or p.is_symlink() or p.stat().st_size>2_000_000:raise ValueError('Screenshot is unavailable.')
   raw=p.read_bytes();handler.send_response(200);handler.send_header('Content-Type','image/jpeg');handler.send_header('Content-Length',str(len(raw)));handler.send_header('Cache-Control','no-store');handler.send_header('X-Content-Type-Options','nosniff');handler.end_headers();handler.wfile.write(raw);return True
  else:handler.json(404,{'error':'Windows YOE route not found.'});return True
  handler.json(200,value)
 except (ValueError,TypeError,KeyError,OSError) as ex:handler.json(400,{'error':redact(str(ex))})
 return True
