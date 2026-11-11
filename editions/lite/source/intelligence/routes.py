"""Same-origin assistant endpoints. Selection and approval are trusted UI actions."""
import json,re,threading,time,html,uuid,os
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from .service import Service
from .native_model import call
from .registry import Context,Cancelled

INSTANCE=None;INIT=threading.RLock();JOBS={};LOCK=threading.RLock()
def service(home,root,edition):
    global INSTANCE
    with INIT:
        if INSTANCE is None:INSTANCE=Service(home,root,call,edition)
        return INSTANCE
def body(handler,maximum=40000):
    if handler.headers.get('Transfer-Encoding'):raise ValueError('Unsupported request encoding.')
    size=int(handler.headers.get('Content-Length','0'))
    if not 0<size<=maximum:raise ValueError('Invalid assistant request size.')
    handler.connection.settimeout(20);raw=handler.rfile.read(size)
    if len(raw)!=size:raise ValueError('Incomplete assistant request.')
    value=json.loads(raw)
    if not isinstance(value,dict):raise ValueError('Assistant request must be an object.')
    return value
def ident(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,100}',value):raise ValueError('Invalid conversation/request identifier.')
    return value
def picker(kind,edition):
    if edition=='Lite':
        from .process import run
        ctx=Context('native-picker',uuid.uuid4().hex,'User attachment selection',deadline=time.monotonic()+610)
        return run('pick',{'kind':kind},ctx,600)['path']
    if edition=='Full':
        import windows_picker
        if kind=='folder':return windows_picker.pick('folder').get('folder')
    if kind=='folder':
        from .pickers import choose_folder
        return choose_folder()
    from model_settings import choose_file
    return choose_file('Attach an image or file to YOEAI','Images and documents\0*.png;*.jpg;*.jpeg;*.webp;*.bmp;*.pdf;*.docx;*.xlsx;*.pptx;*.txt;*.md;*.html;*.htm;*.rtf;*.odt;*.csv\0Images\0*.png;*.jpg;*.jpeg;*.webp;*.bmp\0Documents\0*.pdf;*.docx;*.xlsx;*.pptx;*.txt;*.md;*.html;*.htm;*.rtf;*.odt;*.csv\0\0')

def selected_image(path):
    import base64,io
    from PIL import Image
    path=Path(path).resolve(strict=True)
    with path.open('rb') as stream:raw=stream.read(15*1024**2+1)
    if len(raw)>15*1024**2:raise ValueError('Choose an image smaller than 15 MB.')
    with Image.open(io.BytesIO(raw)) as source:
        if source.width*source.height>40000000:raise ValueError('Choose an image with fewer than 40 million pixels.')
        mime={'PNG':'image/png','JPEG':'image/jpeg','WEBP':'image/webp','BMP':'image/bmp'}.get(source.format)
        if not mime:raise ValueError('Choose a PNG, JPEG, WebP or BMP image.')
    return {'kind':'image','name':path.name,'mime':mime,'dataUrl':'data:'+mime+';base64,'+base64.b64encode(raw).decode('ascii')}
def send(handler,content,ctype):
    data=content.encode('utf8') if isinstance(content,str) else content
    handler.send_response(200);handler.send_header('Content-Type',ctype);handler.send_header('Content-Length',str(len(data)));handler.send_header('Cache-Control','no-store');handler.send_header('X-Content-Type-Options','nosniff');handler.send_header('Content-Security-Policy',"default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'");handler.end_headers();handler.wfile.write(data)
def route(handler,post,home,root,edition):
    path=urlsplit(handler.path).path
    if not path.startswith('/assistant/'):return False
    reply=getattr(handler,'reply',None) or handler.json
    if not handler.allowed() or post and handler.headers.get('Origin')!='http://'+handler.headers.get('Host',''):
        reply(403,{'error':'Use the local YOEAI conversation interface.'});return True
    control=False
    try:
        s=service(home,root,edition)
        if not post:
            if path=='/assistant/research-status':value=s.web.provider.backend.describe()
            elif path=='/assistant/state':value={'scopes':s.store.scopes(),'documents':s.documents.list(),'memories':s.store.memories(),'artifacts':s.store.artifacts(),'backups':s.store.backups(),'semanticAvailable':s.embeddings.available(),'sandboxAvailable':s.sandbox_ready(),'tools':s.registry.describe()}
            elif path.startswith('/assistant/progress/'):
                key=ident(path.rsplit('/',1)[-1]);value=s.progresses.get(key,{'message':'Preparing answer…'})
            elif path.startswith('/assistant/source/'):
                key=ident(path.rsplit('/',1)[-1]);ctx=Context('source-view','source-request','Open source');doc=s.documents.read(key,ctx);index=int(parse_qs(urlsplit(handler.path).query).get('chunk',['0'])[0])
                with s.store.db() as db:rows=db.execute('SELECT label,text FROM chunks WHERE document=? ORDER BY ordinal LIMIT 650',(key,)).fetchall()
                content='<!doctype html><meta charset="utf-8"><title>'+html.escape(doc['name'])+'</title><style>body{font:17px/1.6 sans-serif;max-width:850px;margin:40px auto;padding:20px}pre{white-space:pre-wrap}</style><h1>'+html.escape(doc['name'])+'</h1>'+''.join('<section id="chunk'+str(i)+'"><h2>'+html.escape(r['label'])+'</h2><pre>'+html.escape(r['text'])+'</pre></section>' for i,r in enumerate(rows))
                send(handler,content,'text/html; charset=utf-8');return True
            elif path.startswith('/assistant/artifact/'):
                key=ident(path.rsplit('/',1)[-1]);file=s.store.home/'Artifacts'/(key+'.data')
                item=next((x for x in s.store.artifacts() if x['id']==key),None)
                if not item:raise ValueError('Artifact was removed or is unavailable.')
                if not file.is_file():raise ValueError('Artifact is unavailable.')
                suffix=Path(item['name']).suffix.lower();filename='yoeai-output'+suffix
                handler.send_response(200);handler.send_header('Content-Type','application/octet-stream');handler.send_header('X-Content-Type-Options','nosniff');handler.send_header('Content-Disposition','attachment; filename="'+filename+'"');data=file.read_bytes();handler.send_header('Content-Length',str(len(data)));handler.end_headers();handler.wfile.write(data);return True
            else:reply(404,{'error':'Unknown assistant endpoint.'});return True
        else:
            value=body(handler,25000000 if path=='/assistant/fit' else 65000)
            if path in ('/assistant/revoke','/assistant/forget-document','/assistant/forget-memory','/assistant/forget-artifact','/assistant/restore','/assistant/index','/assistant/attach','/assistant/pick-folder','/assistant/authorize-folder','/assistant/backup','/assistant/remove-backup'):
                with LOCK:
                    if JOBS:raise ValueError('Stop or finish the active assistant request before removing knowledge or restoring a backup.')
                    JOBS['!control']=threading.Event();control=True
                    if path in ('/assistant/revoke','/assistant/forget-document','/assistant/forget-memory','/assistant/forget-artifact','/assistant/restore'):s.approved.clear()
            if path=='/assistant/fit':
                from .native_model import fit
                value=fit(value.get('messages'),1024)
            elif path=='/assistant/prepare':
                session=ident(value.get('session'));key=ident(value.get('requestId'));question=value.get('query')
                if not isinstance(question,str) or not 1<=len(question)<=4000 or not isinstance(value.get('history',[]),list) or len(value.get('history',[]))>100:raise ValueError('Invalid conversation context.')
                for message in value.get('history',[]):
                    if not isinstance(message,dict) or message.get('role') not in ('user','assistant') or not isinstance(message.get('content'),str) or len(message['content'])>8000:raise ValueError('Invalid conversation message.')
                docs=value.get('documents',[])
                if not isinstance(docs,list) or len(docs)>4 or any(not isinstance(d,str) for d in docs):raise ValueError('Choose up to four indexed documents.')
                event=threading.Event()
                with LOCK:
                    if JOBS:reply(409,{'error':'Another assistant preparation is still active.'});return True
                    JOBS[key]=event
                try:value=s.prepare(value,event)
                finally:
                    with LOCK:JOBS.pop(key,None)
            elif path=='/assistant/cancel':
                key=ident(value.get('requestId'))
                with LOCK:event=JOBS.get(key)
                if event:event.set()
                value={'stopped':bool(event)}
            elif path=='/assistant/approve':
                ident(value.get('session'));ident(value.get('id'));key=ident(value.get('requestId'));event=threading.Event()
                with LOCK:
                    if JOBS:raise ValueError('Wait for the active assistant operation before applying another action.')
                    JOBS[key]=event
                try:value=s.approve(value,event)
                finally:
                    with LOCK:JOBS.pop(key,None)
            elif path=='/assistant/pick-folder':
                selected=picker('folder',edition);value=s.store.authorize(selected) if selected else {'cancelled':True}
            elif path=='/assistant/authorize-folder':value=s.store.authorize(value.get('folder'))
            elif path=='/assistant/revoke':value=s.store.revoke(ident(value.get('id')))
            elif path=='/assistant/attach':
                session=ident(value.get('session'));selected=picker('file',edition)
                if selected:
                    if Path(selected).suffix.lower() in ('.png','.jpg','.jpeg','.webp','.bmp'):value=selected_image(selected)
                    else:
                        scope=s.store.authorize_file(selected);ctx=Context(session,uuid.uuid4().hex,'Attach selected document',deadline=time.monotonic()+120);value={'kind':'document',**s.documents.index(scope['id'],scope['selection'],ctx)}
                else:value={'cancelled':True}
            elif path=='/assistant/index':
                ctx=Context(ident(value.get('session')),uuid.uuid4().hex,'Index selected file',deadline=time.monotonic()+120);value=s.documents.index(ident(value.get('scope')),value.get('path'),ctx)
            elif path=='/assistant/forget-document':value=s.store.forget_document(ident(value.get('id')))
            elif path=='/assistant/forget-memory':value=s.store.forget_memory(ident(value.get('id')))
            elif path=='/assistant/forget-artifact':value=s.store.forget_artifact(ident(value.get('id')))
            elif path=='/assistant/backup':value=s.store.backup()
            elif path=='/assistant/remove-backup':value=s.store.remove_backup(value.get('name',''))
            elif path=='/assistant/restore':value=s.store.restore(value.get('name',''))
            else:reply(404,{'error':'Unknown assistant endpoint.'});return True
        reply(200,value)
    except Cancelled:reply(409,{'error':'Stopped'})
    except (ValueError,KeyError,TypeError,OSError) as error:reply(400,{'error':str(error)[:400]})
    except Exception as error:reply(503,{'error':'Assistant preparation failed: '+str(error)[:300]})
    finally:
        if control:
            with LOCK:JOBS.pop('!control',None)
    return True


def initialize(home,root,edition='Lite'):
    """Register tools only. No network, search process, embedding or LLM load."""
    return service(home,root,edition)


def shutdown():
    with LOCK:
        for event in JOBS.values():event.set()
    if INSTANCE:INSTANCE.web.provider.close()
