"""Disposable trusted tool workers with job cleanup, memory and output budgets."""
import subprocess,sys,threading,time,json,os,uuid
from pathlib import Path
from .registry import Cancelled

def run(operation,body,ctx,timeout=30):
    if operation not in ('extract','windows','sandbox','pick'):raise ValueError('Unknown tool worker operation.')
    ctx.check();body=dict(body);cancel_handle=None
    if os.name=='nt' and operation=='sandbox':
        import win32event
        event_name='Local\\YOEAI.Assistant.Cancel.'+uuid.uuid4().hex;cancel_handle=win32event.CreateEvent(None,True,False,event_name);body['_cancel_event']=event_name
    command=[sys.executable,'--assistant-tool-worker',operation] if getattr(sys,'frozen',False) else [sys.executable,'-u',str(Path(__file__).with_name('worker.py')),operation]
    startup=None
    if os.name=='nt' and operation=='pick':
        startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=1
    try:process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=dict(os.environ,PYTHONPATH=os.pathsep.join(sys.path)),creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),startupinfo=startup)
    except Exception:
        if cancel_handle:cancel_handle.Close()
        raise
    job=None;outcome={}
    try:
        if os.name=='nt':
            import win32job,win32api
            job=win32job.CreateJobObject(None,'');limits=win32job.QueryInformationJobObject(job,win32job.JobObjectExtendedLimitInformation);limits['BasicLimitInformation']['LimitFlags']=0x2000|0x8|0x200;limits['BasicLimitInformation']['ActiveProcessLimit']=4;limits['JobMemoryLimit']=(1024 if operation=='sandbox' else 640)*1024**2
            win32job.SetInformationJobObject(job,win32job.JobObjectExtendedLimitInformation,limits)
            handle=win32api.OpenProcess(0x1f0fff,False,process.pid)
            try:win32job.AssignProcessToJobObject(job,handle)
            finally:handle.Close()
        def exchange():
            try:outcome['streams']=process.communicate(json.dumps(body,ensure_ascii=False).encode('utf8'),timeout=timeout)
            except Exception as e:outcome['error']=e
        thread=threading.Thread(target=exchange,daemon=True);thread.start();end=min(ctx.deadline,time.monotonic()+timeout)
        while thread.is_alive():
            try:
                ctx.check()
                if time.monotonic()>end:raise TimeoutError('Tool worker timed out.')
            except (Cancelled,TimeoutError):
                if cancel_handle:
                    win32event.SetEvent(cancel_handle);thread.join(timeout=15)
                raise
            ctx.cancel.wait(.05)
        if 'error' in outcome:raise TimeoutError('Tool worker did not finish.')
        stdout,stderr=outcome['streams']
        if len(stdout)>2600000:raise ValueError('Tool worker output exceeded its budget.')
        if not stdout:raise RuntimeError('Tool worker failed: '+stderr.decode('utf8',errors='replace')[-350:])
        result=json.loads(stdout.decode('utf-8-sig'))
        if process.returncode or 'error' in result:raise ValueError(result.get('error','Tool worker failed.'))
        return result['result']
    finally:
        if job:job.Close()
        if process.poll() is None:process.kill()
        process.wait(timeout=5)
        if 'thread' in locals():thread.join(timeout=2)
        if cancel_handle:cancel_handle.Close()

