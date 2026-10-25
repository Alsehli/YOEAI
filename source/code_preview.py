"""Task-owned visual projects. Browser execution is isolated from the application API.

No dependency installers, shell commands, arbitrary folder scans or model instances.
"""
import hashlib, io, json, re, threading, time, uuid, zipfile
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit, parse_qs
from configuration import APP_DIR

LOCK = threading.RLock()
SESSIONS = {}
EXTENSIONS = {'.html', '.css', '.js', '.jsx', '.ts', '.tsx', '.json', '.svg', '.py', '.gd', '.godot', '.md'}
LIMIT = 700000

def filename(value):
    if not isinstance(value, str) or '\\' in value or ':' in value or value.startswith('/'):
        raise ValueError('Use relative project filenames.')
    p = PurePosixPath(value)
    if not p.parts or len(value)>160 or any(x in {'.','..'} or x.startswith('.') for x in p.parts) or p.suffix.lower() not in EXTENSIONS:
        raise ValueError('Unsupported or unsafe project filename.')
    return str(p)

def validate(files):
    if not isinstance(files, dict) or not 1 <= len(files) <= 24:
        raise ValueError('A preview supports 1–24 text files.')
    result = {}
    for name, text in files.items():
        name = filename(name)
        if name.casefold() in {x.casefold() for x in result}:raise ValueError('Duplicate Windows filename.')
        if not isinstance(text,str) or len(text.encode('utf8'))>250000:
            raise ValueError('Each project file must be UTF-8 text under 250 KB.')
        result[name] = text
    if sum(len(x.encode('utf8')) for x in result.values())>LIMIT:
        raise ValueError('Project exceeds the 700 KB source limit.')
    return result

def revision(files):
    return hashlib.sha256(json.dumps(files, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

def extract(text):
    """Only complete fenced source; never execute prose, reviews or incomplete streams."""
    files={}; counts={}
    for m in re.finditer(r'^```([^\n`]*)\n(.*?)^```\s*$', text or '', re.M|re.S):
        info=m[1].strip(); code=m[2].rstrip(); language=info.split(' ',1)[0].lower()
        named=re.search(r'(?:filename=|file=)?([\w/-]+\.(?:html|css|jsx?|tsx?|py|gd|godot|json))',info)
        if named: name=named[1]
        else:
            ext={'html':'html','htm':'html','css':'css','javascript':'js','js':'js','jsx':'jsx','tsx':'tsx','typescript':'ts','python':'py','py':'py','gdscript':'gd'}.get(language)
            if not ext:continue
            counts[ext]=counts.get(ext,0)+1
            name=('index' if ext=='html' else 'style' if ext=='css' else 'main')+('' if counts[ext]==1 else str(counts[ext]))+'.'+ext
        if name in files:continue
        files[name]=code
    if not files and re.match(r'\s*(?:<!doctype html|<html)',text or '',re.I):files={'index.html':text.strip()}
    return validate(files) if files else None

def project_path(engine, tid):
    if not re.fullmatch('[a-f0-9]{32}',tid):raise ValueError('Invalid task ID.')
    t=engine.get(tid)
    if t['agent']!='code':raise ValueError('Only Code YOE tasks have executable previews.')
    base=engine.home/'Projects';base.mkdir(exist_ok=True)
    p=base/tid
    if p.is_symlink() or (p.exists() and getattr(p.lstat(),'st_file_attributes',0)&0x400):raise ValueError('Linked projects are blocked.')
    p.mkdir(exist_ok=True)
    return p,t

def store(engine,tid,files,expected=None):
    files=validate(files)
    with LOCK:
        p,t=project_path(engine,tid); target=p/'project.json'
        if expected is not None and target.exists() and read(engine,tid)['revision']!=expected:
            raise ValueError('Project changed. Refresh before saving this edit.')
        previous=json.loads(target.read_text(encoding='utf8')) if target.exists() else {}
        data={'files':files,'revision':revision(files),'updated':time.time(),'linkedHashes':previous.get('linkedHashes',{})}
        temp=p/'project.tmp';temp.write_text(json.dumps(data,ensure_ascii=False),encoding='utf8');temp.replace(target)
        return data

def read(engine,tid):
    with LOCK:
        p,t=project_path(engine,tid); target=p/'project.json'
        if target.exists():
            data=json.loads(target.read_text(encoding='utf8'));files=validate(data['files'])
        else:
            files=extract(t.get('draft') or t.get('result',''))
            if not files:raise ValueError('No complete executable source is available in this response.')
            return store(engine,tid,files)
        # Re-read only explicitly approved source files, never scan a directory.
        if t.get('permissions',{}).get('readProject') and t.get('files'):
            from mini_agents import scoped,clean_root
            approved={}; hashes=dict(data.get('linkedHashes',{}));changed=False
            for rel in t['files']:
                name=filename(rel); source=scoped(clean_root(t['project']),rel).read_text(encoding='utf-8-sig');sha=hashlib.sha256(source.encode()).hexdigest()
                if hashes.get(name)!=sha:approved[name]=source;hashes[name]=sha;changed=True
            if changed:
                files.update(approved);files=validate(files);data.update(files=files,linkedHashes=hashes,revision=revision(files),updated=time.time())
                temp=p/'project.tmp';temp.write_text(json.dumps(data,ensure_ascii=False),encoding='utf8');temp.replace(target)
        rev=revision(files)
        return {'files':files,'revision':rev,'updated':data.get('updated',0)}

def publish(engine,t):
    files=extract(t.get('draft') or t.get('result',''))
    if t.get('permissions',{}).get('readProject') and t.get('files'):
        from mini_agents import scoped,clean_root
        files={filename(rel):scoped(clean_root(t['project']),rel).read_text(encoding='utf-8-sig') for rel in t['files']}
    if files and t.get('previewParent'):
        previous=read(engine,t['previewParent'])
        if previous['revision']!=t['previewRevision']:raise ValueError('The previous project changed during generation. Its source was not overwritten.')
        files={**previous['files'],**files}
    if files:
        data=store(engine,t['id'],files)
        t['preview']={'revision':data['revision'],'files':list(files),'runtime':'browser' if any(Path(x).suffix in {'.html','.js','.jsx','.tsx','.ts'} for x in files) else 'native'}

def script(text):return '<script>'+re.sub(r'</script',r'<\\/script',text,flags=re.I)+'</script>'

def render(data,channel):
    if not re.fullmatch('[a-f0-9]{32}',channel):raise ValueError('Invalid preview channel.')
    # CSP is an HTTP response header: generated <meta> tags cannot relax it.
    bootstrap=(APP_DIR/'assets/code-preview-runtime.js').read_text(encoding='utf8')
    payload=json.dumps({'files':data['files'],'channel':channel},ensure_ascii=True).replace('<','\\u003c')
    files=data['files']; source='\n'.join(files.values()); vendor=APP_DIR/'assets/preview-vendor'
    libraries=''
    if any(Path(n).suffix in {'.jsx','.tsx','.ts'} for n in files) or re.search(r'\b(?:React|react|import|export)\b',source):
        libraries+=''.join(script((vendor/n).read_text(encoding='utf8')) for n in ['react.js','react-dom.js','babel.js'])
    if re.search(r'\b(?:THREE|three)\b',source):libraries+=script((vendor/'three.js').read_text(encoding='utf8'))
    if 'echarts' in source:libraries+=script((APP_DIR/'assets/vendor/echarts.min.js').read_text(encoding='utf8'))
    return ('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'+script('window.__YOE_PROJECT__='+payload)+'<style>body{margin:0;font:16px system-ui;background:white;color:#172337}#yoe-boot-error{white-space:pre-wrap;padding:20px;color:#a12626}</style>'+script(bootstrap)+libraries+'</head><body><script>window.__YOE_BOOT__()</script></body></html>').encode('utf8')

CSP="sandbox allow-scripts allow-forms; default-src 'none'; script-src 'unsafe-inline' 'unsafe-eval'; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; media-src data: blob:; connect-src 'none'; frame-src 'none'; worker-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'"

def route(handler,post=False):
    path=urlsplit(handler.path).path
    if not path.startswith('/code-preview/'):return False
    origin='http://'+handler.headers.get('Host','')
    is_render=not post and path.startswith('/code-preview/render/')
    if not handler.allowed() or (post and handler.headers.get('Origin')!=origin) or (handler.headers.get('Sec-Fetch-Site')=='cross-site' and not is_render):
        handler.json(403,{'error':'Only the Code YOE conversation can control previews.'});return True
    try:
        from mini_agents import engine
        e=engine(); parts=path.strip('/').split('/')
        if len(parts)!=3:raise ValueError('Unknown preview route.')
        _,action,tid=parts;body={}
        if post:
            n=int(handler.headers.get('Content-Length','-1'))
            if handler.headers.get('Transfer-Encoding') or not 0<n<=2000000:raise ValueError('Invalid preview request size.')
            body=json.loads(handler.rfile.read(n))
            if not isinstance(body,dict):raise ValueError('Expected a project object.')
        if action=='session' and post:
            project_path(e,tid)
            with LOCK:
                now=time.monotonic()
                for key in list(SESSIONS):
                    if SESSIONS[key][1]<now:del SESSIONS[key]
                token=uuid.uuid4().hex;SESSIONS[token]=(tid,now+300)
            handler.json(200,{'token':token})
        elif action=='project':
            if post:
                if body.get('approve') is not True:raise ValueError('Approve the displayed project edits first.')
                value=store(e,tid,body.get('files'),body.get('revision'))
            else:value=read(e,tid)
            handler.json(200,value)
        elif action=='render' and not post:
            token=parse_qs(urlsplit(handler.path).query).get('channel',[''])[0]
            with LOCK:session=SESSIONS.pop(token,None)
            if not session or session[0]!=tid or session[1]<time.monotonic():raise ValueError('Preview session expired. Refresh from Code YOE.')
            data=render(read(e,tid),token);handler.send_response(200)
            for name,value in [('Content-Type','text/html; charset=utf-8'),('Content-Security-Policy',CSP),('Cache-Control','no-store'),('Referrer-Policy','no-referrer'),('Permissions-Policy','camera=(), microphone=(), geolocation=(), clipboard-read=(), clipboard-write=()'),('Content-Length',str(len(data)))]:handler.send_header(name,value)
            handler.end_headers();handler.wfile.write(data)
        elif action=='export' and not post:
            data=read(e,tid);buf=io.BytesIO()
            with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
                for name,text in data['files'].items():z.writestr(name,text)
                if any(Path(n).suffix in {'.html','.js','.jsx','.ts','.tsx'} for n in data['files']):
                    standalone=render(data,uuid.uuid4().hex).decode('utf8')
                    policy=CSP.replace('sandbox allow-scripts allow-forms; ','')
                    standalone=standalone.replace('<head>','<head><meta http-equiv="Content-Security-Policy" content="'+policy+'">',1)
                    z.writestr('YOEAI-standalone.html',standalone)
                    for name in ['React-LICENSE.txt','Babel-LICENSE.txt','Three-LICENSE.txt']:
                        z.writestr('YOEAI-Licenses/'+name,(APP_DIR/'assets/preview-vendor'/name).read_bytes())
                    z.writestr('YOEAI-Licenses/ECharts-LICENSE.txt',(APP_DIR/'assets/vendor/echarts-LICENSE.txt').read_bytes())
                z.writestr('YOEAI-README.txt','Code YOE generated source. Review before running outside the isolated app preview. For browser projects, open YOEAI-standalone.html offline; it includes the bundled runtime and libraries. Original source files are also included. No dependency installation or native execution occurs automatically. Native programs use your Windows account permissions when separately approved.\n')
            payload=buf.getvalue();handler.send_response(200);handler.send_header('Content-Type','application/zip');handler.send_header('Content-Length',str(len(payload)));handler.end_headers();handler.wfile.write(payload)
        elif action in {'native-prepare','native-run','native-stop','native-state'}:
            from code_preview_native import operation
            handler.json(200,operation(e,tid,action,body,post))
        else:raise ValueError('Unknown preview action.')
    except (ValueError,TypeError,KeyError,OSError) as error:handler.json(400,{'error':str(error)[:500]})
    return True
