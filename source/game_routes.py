import base64,json,mimetypes,re
from urllib.parse import urlsplit,parse_qs
from game_studio import studio,detect

def route(h,post=False):
 path=urlsplit(h.path).path
 if not path.startswith('/game/'):return False
 if not h.allowed() or post and h.headers.get('Origin')!='http://'+h.headers.get('Host',''):h.json(403,{'error':'Use the local YOEAI interface.'});return True
 try:
  s=studio();body={}
  if post:
   if h.headers.get('Transfer-Encoding'):raise ValueError('Unsupported transfer encoding.')
   length=int(h.headers.get('Content-Length','0'));limit=14_000_000 if path in ['/game/import','/game/audio'] else 12000
   if not 0<length<=limit:raise ValueError('Invalid or oversized game request.')
   body=json.loads(h.rfile.read(length))
   if not isinstance(body,dict):raise ValueError('Invalid game request.')
  if not post and path=='/game/state':result={'capabilities':detect(),'projects':s.projects(),'jobs':s.read(s.jobsfile,[])[-30:],'prototypes':s.prototypes().items[-30:]}
  elif not post and path=='/game/project':result=s.inspect(parse_qs(urlsplit(h.path).query).get('id',[''])[0])
  elif not post and path=='/game/file':
   query=parse_qs(urlsplit(h.path).query);p=s.file(query.get('id',[''])[0],query.get('path',[''])[0]);raw=p.read_bytes();h.send_response(200);h.send_header('Content-Type',mimetypes.guess_type(p.name)[0] or 'text/plain');h.send_header('X-Content-Type-Options','nosniff');h.send_header('Cache-Control','no-store');h.send_header('Content-Length',str(len(raw)));h.end_headers();h.wfile.write(raw);return True
  elif post and path=='/game/pick':
   from windows_picker import pick
   result=pick('folder')
  elif post and path=='/game/prototype':
   from mini_agents import engine
   result=s.prototypes().start(engine().get(body.get('task')),body)
  elif post and path=='/game/stop-prototype':result=s.prototypes().stop(body.get('id'))
  elif post and path=='/game/create':result=s.create(body)
  elif post and path=='/game/register':result=s.register(body)
  elif post and path=='/game/revise':result=s.revise(body)
  elif post and path=='/game/upgrade':result=s.upgrade(body)
  elif post and path=='/game/apply-proposal':
   from mini_agents import engine
   t=engine().get(body.get('task'))
   if t['agent']!='game' or t['status']!='COMPLETED' or t.get('gameProject')!=body.get('project') or not t.get('gameProposal'):raise ValueError('Choose a completed proposal for this same game project.')
   result=s.revise({'project':body['project'],'spec':t['gameProposal'],'approve':body.get('approve')})
  elif post and path=='/game/run':result=s.start(body)
  elif post and path=='/game/stop':result=s.stop(body.get('job'))
  elif post and path=='/game/import':
   from game_assets import prepare
   result=prepare(s,body)
  elif post and path=='/game/audio':
   from game_assets import audio
   result=audio(s,body)
  elif post and path=='/game/handoff':
   if body.get('approve') is not True:raise ValueError('Approve the scoped handoff.')
   target=body.get('agent');objective=body.get('objective','')
   if target not in ['code','research','windows','update'] or not isinstance(objective,str) or not 1<=len(objective)<=1800:raise ValueError('Choose an existing agent and a bounded objective.')
   report=s.inspect(body['project']);project=report['project'];evidence=json.dumps({'project':{k:project.get(k) for k in ['id','title','spec','editor','status']},'files':report['files'][:40],'reports':report['reports']},ensure_ascii=False)[:10000]
   from mini_agents import engine
   e=engine();args={'agent':target,'objective':objective,'documents':[{'name':'game-project-evidence.json','text':evidence}],'permissions':{'web':target=='research' and body.get('web') is True}}
   if target=='windows':
    # Delegate a read-only diagnosed objective through the existing enabled Windows controller.
    args['documents']=[];args['windows']={'mode':'ADVISOR','folder':str(next(p['path'] for p in s.projects() if p['id']==project['id']))}
   if target=='code':
    root=next(p['path'] for p in s.projects() if p['id']==project['id']);args.update(project=root,files=[x['path'] for x in report['files'] if x['path'] in ['Assets/YOE/Scripts/YoePlayer.cs','Assets/YOE/Scripts/YoeGame.cs']],permissions={'readProject':True});args['objective']='Unity 6 C# drafting/review for the supplied game project. Return a code block and a patch explanation. No arbitrary code will be executed or applied by Game Studio. '+objective
   result=e.create(args);result['gameOrigin']=project['id'];e.save(result)
  elif post and path=='/game/generate':
   if body.get('approve') is not True:raise ValueError('Approve local Image Turbo generation and temporary shared-model pause.')
   root,doc=s.project(body['project']);prompt=body.get('prompt','')
   if not isinstance(prompt,str) or not 1<=len(prompt)<=1200:raise ValueError('Describe a single asset in 1–1200 characters.')
   from mini_agents import engine,GATE
   e=engine()
   if e.running_id or not GATE.acquire(blocking=False):raise ValueError('Wait for current model work to finish before generating an asset.')
   try:
    from image_generation_adapter import generator
    result=generator().start({'prompt':doc['spec']['style']+'. '+prompt+'. Single game asset, no letters, no labels. Plain contrasting background.','size':512,'engine':'turbo','precisionMode':'off'})
   finally:GATE.release()
   doc['pendingImage']=result.get('id');s.save(root,doc)
  elif not post and path=='/game/generated':
   query=parse_qs(urlsplit(h.path).query);root,doc=s.project(query.get('id',[''])[0]);from image_generation_adapter import generator
   g=generator();state=g.status()
   if state.get('id')!=doc.get('pendingImage') or not doc.get('pendingImage'):raise ValueError('No matching generated asset is available.')
   result={'state':state}
   if state.get('status')=='complete':
    value=g.output(doc['pendingImage']);raw=value.read_bytes() if hasattr(value,'read_bytes') else value;result['data']=base64.b64encode(raw).decode();result['review']='Artwork requires visual review before import. Transparency and coherent sprite frames are not guaranteed.'
  else:h.json(404,{'error':'Unknown Game Studio action.'});return True
  h.json(200,result)
 except Exception as ex:h.json(400,{'error':str(ex)[:1200]})
 return True
