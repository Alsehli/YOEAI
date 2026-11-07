from native_ai.client import Connection as NativeConnection
"""Portable localhost engine and UI. No Node.js or system Python dependency."""
import ctypes,json,os,socket,subprocess,threading,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from configuration import APP_DIR,HOME,read_config
LOCK=threading.RLock();ENGINE=None;SERVER=None;STATE=HOME/'engine-state.json'
def healthy(port=None):
    from native_ai.manager import INSTANCE
    return bool(INSTANCE.state['loaded'])

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
    from model_modes import stop_current
    return stop_current()
def ensure_engine():
    from model_modes import ensure_selected
    return ensure_selected()

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
                from model_modes import change_context
                value=json.loads(body)
                return self.json(200,change_context(value.get('context'),value.get('confirmedEngineRestart')))
            if self.path!='/v1/chat/completions':return self.json(404,{'error':'Not found'})
            upstream=NativeConnection(timeout=180)
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
