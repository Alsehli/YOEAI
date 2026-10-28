"""Portable localhost engine and UI. No Node.js or system Python dependency."""
import ctypes,http.client,json,os,socket,subprocess,threading,time,urllib.request
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from configuration import APP_DIR,HOME,read_config
HTTP=urllib.request.build_opener(urllib.request.ProxyHandler({}))
LOCK=threading.RLock();ENGINE=None;SERVER=None;STATE=HOME/'engine-state.json'
def healthy(port):
    try:
        with HTTP.open(f'http://127.0.0.1:{port}/health',timeout=2) as r:return json.load(r).get('status')=='ok'
    except Exception:return False
def identity(pid):
    from ctypes import wintypes
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    k.OpenProcess.restype=wintypes.HANDLE;k.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    k.QueryFullProcessImageNameW.argtypes=[wintypes.HANDLE,wintypes.DWORD,wintypes.LPWSTR,ctypes.POINTER(wintypes.DWORD)]
    k.GetProcessTimes.argtypes=[wintypes.HANDLE,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p]
    k.CloseHandle.argtypes=[wintypes.HANDLE]
    h=k.OpenProcess(0x1000,False,pid)
    if not h:return None
    try:
        name=ctypes.create_unicode_buffer(32768);length=wintypes.DWORD(len(name))
        created,ended,kernel,user=(ctypes.c_ulonglong() for _ in range(4))
        if not k.QueryFullProcessImageNameW(h,0,name,ctypes.byref(length)) or not k.GetProcessTimes(h,ctypes.byref(created),ctypes.byref(ended),ctypes.byref(kernel),ctypes.byref(user)):return None
        return {'exe':str(Path(name.value).resolve()),'created':created.value}
    finally:k.CloseHandle(h)
def stop_engine():
    with LOCK:
        if not STATE.exists():return
        s=json.loads(STATE.read_text());current=identity(s['pid'])
        if current is None:return
        if current!=s['identity'] or Path(current['exe'])!=(APP_DIR/'backend/llama-server.exe').resolve():raise RuntimeError('Refusing to stop a process that this installation does not own.')
        k=ctypes.WinDLL('kernel32');k.FreeConsole()
        if not k.AttachConsole(s['pid']):raise RuntimeError('Could not attach for graceful shutdown.')
        try:
            k.SetConsoleCtrlHandler(None,True)
            if not k.GenerateConsoleCtrlEvent(1,s['pid']):raise RuntimeError('Graceful shutdown signal failed.')
        finally:k.FreeConsole()
        for _ in range(100):
            if identity(s['pid']) is None:return
            time.sleep(.1)
        raise RuntimeError('Engine is still closing. No process was forcibly killed.')
def ensure_engine():
    global ENGINE
    with LOCK:
        c=read_config();port=c['apiPort']
        if healthy(port):
            if c.get('externalBackend'):return
            if STATE.exists():
                s=json.loads(STATE.read_text())
                if identity(s['pid'])==s['identity'] and Path(s['identity']['exe'])==(APP_DIR/'backend/llama-server.exe').resolve():return
            raise RuntimeError(f'Port {port} is used by another AI server. Close it before starting this installation.')
        with socket.socket() as test:
            if test.connect_ex(('127.0.0.1',port))==0:raise RuntimeError(f'Port {port} is occupied.')
        exe=APP_DIR/'backend/llama-server.exe'
        for f in [exe,Path(c['model']),Path(c['projector'])]:
            if not f.exists():raise RuntimeError('Required installation file missing: '+f.name)
        logs=HOME/'Logs';logs.mkdir(exist_ok=True);stamp=time.strftime('%Y%m%d-%H%M%S')
        startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
        args=[str(exe),'-m',c['model'],'--mmproj',c['projector'],'--host','127.0.0.1','--port',str(port),'-ngl','99','-c',str(c.get('context',4096)),'-t',str(min(6,os.cpu_count() or 4)),'-b','512','-ub','256','-fa','on','-ctk','q8_0','-ctv','q8_0','--alias','deepseek-local']
        args += ['-np','1','--jinja','--reasoning','off','--image-min-tokens','1024']
        with open(logs/f'engine-{stamp}.out.log','w') as out,open(logs/f'engine-{stamp}.err.log','w') as err:
            ENGINE=subprocess.Popen(args,cwd=str(exe.parent),stdout=out,stderr=err,startupinfo=startup,creationflags=subprocess.CREATE_NEW_CONSOLE|subprocess.CREATE_NEW_PROCESS_GROUP)
        STATE.write_text(json.dumps({'pid':ENGINE.pid,'identity':identity(ENGINE.pid),'context':c.get('context',4096),'model':c['model'],'port':port}),encoding='utf8')
        for _ in range(180):
            if ENGINE.poll() is not None:raise RuntimeError('The AI engine could not start. See the installation Logs folder.')
            if healthy(port):return
            time.sleep(1)
        raise RuntimeError('The AI engine took too long to start. See the installation Logs folder.')
def gpu_status():
    raw=subprocess.check_output(['nvidia-smi.exe','--query-gpu=memory.used,memory.total,utilization.gpu,temperature.gpu','--format=csv,noheader,nounits'],creationflags=subprocess.CREATE_NO_WINDOW,text=True,timeout=10)
    values=[float(x) for x in raw.splitlines()[0].split(',')]
    return dict(zip(['used','total','util','temp'],values))
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def json(self,code,data):
        payload=json.dumps(data).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
    def allowed(self):
        port=read_config()['uiPort'];return self.headers.get('Host') in [f'127.0.0.1:{port}',f'localhost:{port}'] and (not self.headers.get('Origin') or self.headers['Origin']==f'http://127.0.0.1:{port}')
    def do_GET(self):
        if not self.allowed():return self.json(403,{'error':'Only the local interface may access this service.'})
        try:
            c=read_config()
            if self.path=='/':
                page=(APP_DIR/'ui.html').read_bytes();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'");self.send_header('Content-Length',str(len(page)));self.end_headers();self.wfile.write(page)
            elif self.path=='/status':self.json(200,{**gpu_status(),'status':'ok' if healthy(c['apiPort']) else 'offline','context':c.get('context',4096),'model':c['model'],'changing':False})
            else:self.json(404,{'error':'Not found'})
        except Exception as e:self.json(500,{'error':str(e)})
    def do_POST(self):
        if not self.allowed():return self.json(403,{'error':'Only the local interface may access this service.'})
        try:
            if self.headers.get('Transfer-Encoding'):return self.json(400,{'error':'Transfer encoding is not supported.'})
            raw_length=self.headers.get('Content-Length')
            if raw_length is None:return self.json(411,{'error':'Content-Length is required.'})
            try:length=int(raw_length)
            except ValueError:return self.json(400,{'error':'Invalid Content-Length.'})
            if length<0:return self.json(400,{'error':'Invalid Content-Length.'})
            if length>25000000:return self.json(413,{'error':'Image or request is too large.'})
            body=self.rfile.read(length);c=read_config()
            if self.path=='/context':
                context=json.loads(body).get('context')
                if context not in [4096,8192,16384]:return self.json(400,{'error':'Unsupported context'})
                if c.get('externalBackend'):return self.json(409,{'error':'This test uses an existing engine. Context changes are disabled.'})
                stop_engine();c['context']=context
                from configuration import CONFIG_FILE
                CONFIG_FILE.write_text(json.dumps(c));ensure_engine();return self.json(200,{'status':'ok','context':context})
            if self.path!='/v1/chat/completions':return self.json(404,{'error':'Not found'})
            if c.get('modelMode')=='advanced' and any(isinstance(m.get('content'),list) and any(x.get('type')=='image_url' for x in m['content']) for m in json.loads(body).get('messages',[])):
                return self.json(409,{'error':'Advanced Mode has no verified vision projector. Select Fast Mode to analyse images.'})
            upstream=http.client.HTTPConnection('127.0.0.1',c['apiPort'],timeout=180)
            try:
                upstream.request('POST',self.path,body,{'Content-Type':'application/json'});response=upstream.getresponse()
                self.send_response(response.status);self.send_header('Content-Type',response.getheader('Content-Type','application/json'));self.send_header('Cache-Control','no-store');self.end_headers()
                while True:
                    chunk=response.read1(8192)
                    if not chunk:break
                    self.wfile.write(chunk);self.wfile.flush()
            finally:upstream.close()
        except (BrokenPipeError,ConnectionResetError):pass
        except Exception as e:
            try:self.json(500,{'error':str(e)})
            except Exception:pass
def start_ui():
    global SERVER
    if SERVER:return
    SERVER=ThreadingHTTPServer(('127.0.0.1',read_config()['uiPort']),Handler)
    threading.Thread(target=SERVER.serve_forever,daemon=True).start()
