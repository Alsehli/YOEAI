"""Private JSON worker entry. Its operation names are fixed by trusted host code."""
import sys,json,contextlib
from pathlib import Path
if __package__ in (None,''):sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
def main(operation=None):
    # PyInstaller windowed apps do not create Python stdio wrappers. The trusted
    # parent supplies anonymous pipes; restore wrappers for those handles only.
    if sys.stdin is None or sys.stdout is None:
        import os,io,ctypes,msvcrt
        get=ctypes.WinDLL('kernel32',use_last_error=True).GetStdHandle;get.argtypes=[ctypes.c_ulong];get.restype=ctypes.c_void_p
        for name,number,mode,flags in [('stdin',-10,'rb',os.O_RDONLY),('stdout',-11,'wb',os.O_WRONLY),('stderr',-12,'wb',os.O_WRONLY)]:
            if getattr(sys,name) is None:
                handle=get(number&0xffffffff)
                if not handle or handle==ctypes.c_void_p(-1).value:raise ValueError('The assistant worker requires private inherited pipes.')
                stream=os.fdopen(msvcrt.open_osfhandle(handle,flags),mode,buffering=0)
                setattr(sys,name,io.TextIOWrapper(stream,encoding='utf8',write_through=True))
    for stream in (sys.stdin,sys.stdout,sys.stderr):
        if stream is not None and hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf8',errors='strict')
    operation=operation or sys.argv[-1]
    try:
        raw=sys.stdin.buffer.read(450001)
        if len(raw)>450000:raise ValueError('Tool request exceeds its budget.')
        body=json.loads(raw)
        import threading
        cancellation=threading.Event()
        if body.get('_cancel_event'):
            import win32event
            event=win32event.OpenEvent(0x00100000,False,body['_cancel_event'])
            def watch():
                try:
                    if win32event.WaitForSingleObject(event,120000)==0:cancellation.set()
                finally:event.Close()
            threading.Thread(target=watch,daemon=True).start()
        with contextlib.redirect_stdout(sys.stderr):
            if operation=='extract':
                from intelligence.documents import extract
                result=extract(body['path'])
            elif operation=='windows':
                from windows_tools import execute
                result=execute(body)
            elif operation=='pick':
                if body['kind']=='model':
                    from model_settings import choose_file
                    result={'path':choose_file()}
                elif body['kind']=='model-folder':
                    from intelligence.pickers import choose_folder
                    result={'path':choose_folder('Choose your local GGUF models folder')}
                elif body['kind'] in ('file','folder'):
                    from intelligence.routes import picker
                    result={'path':picker(body['kind'],'NativeWorker')}
                else:raise ValueError('Choose an image, document, model or folder through the app controls.')
            elif operation=='sandbox':
                from update_sandbox import run
                result=run(body['home'],body['files'],cancel=cancellation,timeout=body.get('timeout',20),memory_mb=512,runtime=body['runtime'])
            else:raise ValueError('Unsupported worker operation.')
        print(json.dumps({'result':result},ensure_ascii=False),flush=True)
    except Exception as error:print(json.dumps({'error':str(error)[:500]},ensure_ascii=False),flush=True);sys.exit(1)
if __name__=='__main__':main()
