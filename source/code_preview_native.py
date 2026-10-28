"""Explicitly trusted native launches, never an automatic fallback from a browser frame.

Windows Job Objects bound lifetime/children/memory; they are NOT a file/network sandbox.
The approval screen explicitly describes this trust boundary.
"""
import os, shutil, subprocess, threading, time, uuid
from pathlib import Path
from code_preview import read, project_path

LOCK=threading.RLock(); APPROVALS={}; RUNS={}

def runtime_for(files):
    if any(n.endswith('.py') for n in files):
        exe=Path('C:/Python313/python.exe')
        if not exe.is_file():return None,None,'Python is not installed at the supported C:\\Python313\\python.exe location. Save the project and configure a trusted runtime before execution.'
        entry=next((n for n in files if n.endswith('main.py')),next(n for n in files if n.endswith('.py')))
        return str(exe),['-I','-u',entry],'Launch '+entry+' using '+str(exe)+'.'
    godot=shutil.which('godot') or shutil.which('godot4')
    if any(n.endswith(('.gd','.godot')) for n in files):
        if not godot:return None,None,'Godot is not installed on PATH. Save the project and open it with Godot; no substitute simulation will run.'
        if 'project.godot' not in files:return None,None,'A complete Godot project.godot is required. Ask Code YOE for the full project.'
        return godot,['--path','.'],'Launch this project using '+godot+'.'
    return None,None,'This source needs a compiler or native runtime that is not configured. Save Project to export the actual source; executable files are never fabricated.'

def stop(tid,reason='Stopped by user.'):
    with LOCK:
        state=RUNS.get(tid)
        if state and not state.get('jobClosed'):
            import win32job
            win32job.TerminateJobObject(state['job'],1);state['status']=reason

def operation(engine,tid,action,body,post):
    data=read(engine,tid);files=data['files'];exe,args,description=runtime_for(files)
    if action=='native-prepare' and post:
        token=uuid.uuid4().hex
        with LOCK:APPROVALS[tid]={'token':token,'revision':data['revision'],'expires':time.monotonic()+120,'exe':exe}
        return {'available':bool(exe) and os.name=='nt','token':token,'description':description+' This is a real Windows application, outside the browser sandbox. It can access your files and network. The app will stop it after 120 seconds or when Stop is pressed.'}
    if action=='native-run' and post:
        from mini_agents import GATE
        if GATE.locked():raise ValueError('Wait for local inference to finish before launching a native project.')
        with LOCK:
            approval=APPROVALS.pop(tid,None)
            if not approval or body.get('approve') is not True or body.get('token')!=approval['token'] or body.get('revision')!=data['revision'] or approval['revision']!=data['revision'] or time.monotonic()>approval['expires'] or not exe or exe!=approval['exe']:
                raise ValueError('Review and explicitly approve the current source and runtime first.')
            if any(s['process'].poll() is None for s in RUNS.values()):raise ValueError('Stop the current native preview first.')
            import win32job
            base,_=project_path(engine,tid);folder=base/('run-'+uuid.uuid4().hex);folder.mkdir()
            for name,text in files.items():
                p=folder/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf8')
            job=win32job.CreateJobObject(None,'YOEAI-preview-'+uuid.uuid4().hex);limits=win32job.QueryInformationJobObject(job,win32job.JobObjectExtendedLimitInformation)
            limits['BasicLimitInformation']['LimitFlags']=win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE|win32job.JOB_OBJECT_LIMIT_ACTIVE_PROCESS|win32job.JOB_OBJECT_LIMIT_PROCESS_MEMORY
            limits['BasicLimitInformation']['ActiveProcessLimit']=16;limits['ProcessMemoryLimit']=512*1024*1024;win32job.SetInformationJobObject(job,win32job.JobObjectExtendedLimitInformation,limits)
            env={k:v for k,v in os.environ.items() if k.upper() in {'SYSTEMROOT','WINDIR','TEMP','TMP','PATH','USERPROFILE','APPDATA','LOCALAPPDATA'}}
            process=subprocess.Popen([exe,*args],cwd=folder,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            try:win32job.AssignProcessToJobObject(job,int(process._handle))
            except Exception:
                process.kill();job.Close();raise ValueError('Windows could not constrain this process. Launch cancelled.')
            state={'process':process,'job':job,'output':'','status':'Native application running · approved Windows account access','started':time.monotonic()};RUNS[tid]=state
            def collect():
                try:
                    while True:
                        chunk=process.stdout.read1(1024)
                        if not chunk:break
                        with LOCK:state['output']=(state['output']+chunk.decode('utf8',errors='replace'))[-64000:]
                    code=process.wait()
                    with LOCK:
                        if state['status'].startswith('Native application running'):state['status']='Exited with code '+str(code)
                finally:
                    # Descendants are terminated even if the direct child exits first.
                    
                    with LOCK:
                        state['jobClosed']=True;job.Close()
                    process.stdout.close()
            threading.Thread(target=collect,daemon=True,name='Code-YOE-native-output').start()
            timer=threading.Timer(120,lambda:stop(tid,'Stopped after the 120-second runtime limit.') if RUNS.get(tid) is state else None);timer.daemon=True;timer.start()
    elif action=='native-stop' and post:stop(tid)
    elif action=='native-state' and not post:pass
    else:raise ValueError('Unsupported native runtime operation.')
    with LOCK:
        s=RUNS.get(tid)
        return {'running':bool(s and s['process'].poll() is None),'status':s['status'] if s else 'Stopped','output':s['output'] if s else ''}
