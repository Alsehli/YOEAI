"""Windows AppContainer runner: no capabilities, no inherited handles, constrained job.
Trusted launcher only; generated text is never interpreted as host commands.
"""
import ctypes as C,json,os,shutil,subprocess,sys,threading,time,uuid
from ctypes import wintypes as W
from pathlib import Path
LOCK=threading.Lock()
class SECURITY_CAPABILITIES(C.Structure):_fields_=[('sid',C.c_void_p),('capabilities',C.c_void_p),('count',W.DWORD),('reserved',W.DWORD)]
class SI(C.Structure):_fields_=[('cb',W.DWORD),('reserved',W.LPWSTR),('desktop',W.LPWSTR),('title',W.LPWSTR),('x',W.DWORD),('y',W.DWORD),('xs',W.DWORD),('ys',W.DWORD),('xc',W.DWORD),('yc',W.DWORD),('fill',W.DWORD),('flags',W.DWORD),('show',W.WORD),('reserved2',W.WORD),('reserved3',C.c_void_p),('stdin',W.HANDLE),('stdout',W.HANDLE),('stderr',W.HANDLE)]
class SIX(C.Structure):_fields_=[('si',SI),('attributes',C.c_void_p)]
class PI(C.Structure):_fields_=[('process',W.HANDLE),('thread',W.HANDLE),('pid',W.DWORD),('tid',W.DWORD)]
def api():
 if os.name!='nt':raise ValueError('AppContainer requires Windows.')
 k=C.WinDLL('kernel32',use_last_error=True);u=C.WinDLL('userenv',use_last_error=True);a=C.WinDLL('advapi32',use_last_error=True)
 k.CreateProcessW.argtypes=[W.LPCWSTR,W.LPWSTR,C.c_void_p,C.c_void_p,W.BOOL,W.DWORD,C.c_void_p,W.LPCWSTR,C.POINTER(SIX),C.POINTER(PI)];k.CreateProcessW.restype=W.BOOL
 k.InitializeProcThreadAttributeList.argtypes=[C.c_void_p,W.DWORD,W.DWORD,C.POINTER(C.c_size_t)]
 k.UpdateProcThreadAttribute.argtypes=[C.c_void_p,W.DWORD,C.c_size_t,C.c_void_p,C.c_size_t,C.c_void_p,C.c_void_p]
 for name in ['ResumeThread','CloseHandle','WaitForSingleObject','TerminateProcess']:
  getattr(k,name).argtypes=[W.HANDLE]+({'WaitForSingleObject':[W.DWORD],'TerminateProcess':[W.UINT]}.get(name,[]))
 k.GetExitCodeProcess.argtypes=[W.HANDLE,C.POINTER(W.DWORD)]
 u.CreateAppContainerProfile.argtypes=[W.LPCWSTR,W.LPCWSTR,W.LPCWSTR,C.c_void_p,W.DWORD,C.POINTER(C.c_void_p)];u.CreateAppContainerProfile.restype=C.c_long
 u.DeleteAppContainerProfile.argtypes=[W.LPCWSTR];u.FreeSid=C.WinDLL('advapi32').FreeSid;u.FreeSid.argtypes=[C.c_void_p]
 a.ConvertSidToStringSidW.argtypes=[C.c_void_p,C.POINTER(W.LPWSTR)];a.OpenProcessToken.argtypes=[W.HANDLE,W.DWORD,C.POINTER(W.HANDLE)];a.GetTokenInformation.argtypes=[W.HANDLE,C.c_int,C.c_void_p,W.DWORD,C.POINTER(W.DWORD)]
 k.LocalFree.argtypes=[C.c_void_p]
 return k,u,a
def check(ok):
 if not ok:raise C.WinError(C.get_last_error())
def grant(path,sid,access):
 result=subprocess.run(['icacls.exe',str(path),'/grant:r',sid+':(OI)(CI)'+access,'/T','/Q'],capture_output=True,timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
 if result.returncode:raise ValueError('Cannot scope AppContainer files: '+result.stderr.decode(errors='replace')[-300:])
def prepare_runtime(destination,base=None):
 base=Path(base or sys.base_prefix);destination=Path(destination)
 if not (base/'python313.dll').is_file():raise ValueError('A verified local Python 3.13 runtime is required.')
 destination.mkdir(parents=True,exist_ok=True)
 for name in ['python.exe','python313.dll','python3.dll','vcruntime140.dll','vcruntime140_1.dll']:
  if (base/name).exists():shutil.copy2(base/name,destination/name)
 shutil.copytree(base/'Lib',destination/'Lib',ignore=shutil.ignore_patterns('site-packages','__pycache__','test','tests','idlelib','tkinter','ensurepip'),dirs_exist_ok=True)
 shutil.copytree(base/'DLLs',destination/'DLLs',ignore=shutil.ignore_patterns('*tk*','*tcl*','*test*'),dirs_exist_ok=True)
 (destination/'python313._pth').write_text('Lib\nDLLs\n.\n',encoding='utf8')
 return destination
BOOTSTRAP='''import os,runpy,json,traceback,contextlib,sys
os.chdir(os.path.dirname(__file__))
sys.path.insert(0,os.path.dirname(__file__))
with open('output/run.log','w',encoding='utf8') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
 try:runpy.run_path('test_main.py',run_name='__main__')
 except Exception:traceback.print_exc();sys.exit(1)
'''
def run(home,files,cancel=None,timeout=20,memory_mb=512,runtime=None):
 if not LOCK.acquire(blocking=False):raise ValueError('An isolated test is already running.')
 try:return _run(home,files,cancel,timeout,memory_mb,runtime)
 finally:LOCK.release()
def _run(home,files,cancel,timeout,memory_mb,runtime):
 import win32job,win32api
 if not isinstance(files,dict) or 'test_main.py' not in files or len(files)>12:raise ValueError('Provide test_main.py and up to 12 Python text files.')
 if not 1<=timeout<=60 or not 128<=memory_mb<=1024:raise ValueError('Invalid sandbox resource limits.')
 for name,text in files.items():
  if not isinstance(name,str) or Path(name).name!=name or not name.endswith('.py') or not name.replace('_','').replace('.','').isalnum() or not isinstance(text,str) or len(text)>100000:raise ValueError('Sandbox accepts flat, bounded Python source files only.')
 if sum(len(x) for x in files.values())>400000:raise ValueError('Sandbox input is too large.')
 home=Path(home).resolve();home.mkdir(parents=True,exist_ok=True);jobdir=home/uuid.uuid4().hex;jobdir.mkdir()
 import win32file,win32con
 handle=win32file.CreateFile(str(jobdir),0,7,None,win32con.OPEN_EXISTING,win32con.FILE_FLAG_BACKUP_SEMANTICS,None)
 try:jobdir=Path(win32file.GetFinalPathNameByHandle(handle,0).removeprefix('\\\\?\\'))
 finally:handle.Close()
 output=jobdir/'output';output.mkdir();runner=Path(runtime).resolve() if runtime else prepare_runtime(jobdir/'runtime')
 for name,text in files.items():(jobdir/name).write_text(text,encoding='utf8')
 (jobdir/'bootstrap.py').write_text(BOOTSTRAP,encoding='utf8')
 k,u,a=api();sid=C.c_void_p();name='YOEAI.Test.'+uuid.uuid4().hex;profile=False;pi=PI();job=None;attr=None;began=time.monotonic();reason=None;verified=False;exitcode=W.DWORD(1)
 try:
  hr=u.CreateAppContainerProfile(name,name,'Disposable YOEAI isolated test',None,0,C.byref(sid))
  if hr<0:raise ValueError('AppContainer creation failed: '+hex(hr&0xffffffff))
  profile=True;sidtext=W.LPWSTR();check(a.ConvertSidToStringSidW(sid,C.byref(sidtext)));sidstr=sidtext.value;k.LocalFree(C.cast(sidtext,C.c_void_p))
  foldertext=W.LPWSTR();u.GetAppContainerFolderPath.argtypes=[W.LPCWSTR,C.POINTER(W.LPWSTR)];u.GetAppContainerFolderPath.restype=C.c_long
  if u.GetAppContainerFolderPath(sidstr,C.byref(foldertext))<0:raise ValueError('Cannot determine disposable AppContainer storage.')
  profile_folder=Path(foldertext.value);C.OleDLL('ole32').CoTaskMemFree(C.cast(foldertext,C.c_void_p))
  if shutil.disk_usage(jobdir).free<2*1024**3:raise ValueError('Isolated tests require 2 GiB free disk space.')
  grant(runner,'*'+sidstr,'RX');grant(jobdir,'*'+sidstr,'RX');grant(output,'*'+sidstr,'M')
  # Low-integrity writes are allowed only in disposable output, never source/runtime.
  acl=subprocess.run(['icacls.exe',str(output),'/setintegritylevel','(OI)(CI)L','/T','/Q'],capture_output=True,timeout=20,creationflags=subprocess.CREATE_NO_WINDOW)
  if acl.returncode:raise ValueError('Cannot set disposable low-integrity output.')
  caps=SECURITY_CAPABILITIES(sid,None,0,0);size=C.c_size_t();k.InitializeProcThreadAttributeList(None,2,0,C.byref(size));attr=C.create_string_buffer(size.value);check(k.InitializeProcThreadAttributeList(attr,2,0,C.byref(size)))
  check(k.UpdateProcThreadAttribute(attr,0,0x20009,C.byref(caps),C.sizeof(caps),None,None))
  mitigation=C.c_ulonglong(0x10000000);check(k.UpdateProcThreadAttribute(attr,0,0x20007,C.byref(mitigation),C.sizeof(mitigation),None,None))
  startup=SIX();startup.si.cb=C.sizeof(SIX);startup.attributes=C.cast(attr,C.c_void_p)
  cmd=C.create_unicode_buffer(subprocess.list2cmdline([str(runner/'python.exe'),'-I','-S','-B',str(jobdir/'bootstrap.py')]))
  values={key:os.environ[key] for key in ['SystemRoot','SystemDrive','windir','USERPROFILE','LOCALAPPDATA','APPDATA','ProgramData','ALLUSERSPROFILE'] if key in os.environ};values.update(TEMP=str(output),TMP=str(output));env=C.create_unicode_buffer('\0'.join(key+'='+value for key,value in sorted(values.items()))+'\0\0')
  if cancel is not None and cancel.is_set():raise InterruptedError('Stopped before isolated execution.')
  check(k.CreateProcessW(str(runner/'python.exe'),cmd,None,None,False,0x80000|0x400|0x4|0x08000000,env,str(jobdir),C.byref(startup),C.byref(pi)))
  token=W.HANDLE();check(a.OpenProcessToken(pi.process,8,C.byref(token)))
  try:
   value=W.DWORD();length=W.DWORD();check(a.GetTokenInformation(token,29,C.byref(value),4,C.byref(length)))
   if value.value!=1:raise ValueError('Isolation verification failed: child is not AppContainer.')
   elevated=W.DWORD();check(a.GetTokenInformation(token,20,C.byref(elevated),4,C.byref(length)))
   if elevated.value:raise ValueError('Sandbox must not be elevated.')
   capbuf=C.create_string_buffer(4096);check(a.GetTokenInformation(token,30,capbuf,4096,C.byref(length)))
   if C.cast(capbuf,C.POINTER(W.DWORD))[0]!=0:raise ValueError('Unexpected sandbox capabilities.')
   verified=True
  finally:k.CloseHandle(token)
  job=win32job.CreateJobObject(None,"");limits=win32job.QueryInformationJobObject(job,win32job.JobObjectExtendedLimitInformation);limits['BasicLimitInformation']['LimitFlags']=0x2000|0x8|0x100|0x200;limits['BasicLimitInformation']['ActiveProcessLimit']=1;limits['ProcessMemoryLimit']=memory_mb*1024**2;limits['JobMemoryLimit']=memory_mb*1024**2;win32job.SetInformationJobObject(job,win32job.JobObjectExtendedLimitInformation,limits)
  win32job.SetInformationJobObject(job,win32job.JobObjectBasicUIRestrictions,{'UIRestrictionsClass':0xff})
  class CPU(C.Structure):_fields_=[('flags',W.DWORD),('rate',W.DWORD)]
  cpu=CPU(1|4,2000);k.SetInformationJobObject.argtypes=[W.HANDLE,C.c_int,C.c_void_p,W.DWORD];check(k.SetInformationJobObject(int(job),15,C.byref(cpu),C.sizeof(cpu)))
  win32job.AssignProcessToJobObject(job,int(pi.process))
  if cancel is not None and cancel.is_set():raise InterruptedError('Stopped before isolated execution.')
  check(k.ResumeThread(pi.thread)!=0xffffffff)
  while k.WaitForSingleObject(pi.process,100)==258:
   if cancel is not None and cancel.is_set():reason='CANCELLED'
   elif time.monotonic()-began>timeout:reason='TIMEOUT'
   else:
    total=0;count=0;stack=[(output,0),(profile_folder,0)]
    while stack and not reason:
     folder,depth=stack.pop()
     for entry in os.scandir(folder):
      count+=1;stat=entry.stat(follow_symlinks=False)
      if count>512 or depth>8 or stat.st_file_attributes&0x400:reason='OUTPUT_LIMIT';break
      if entry.is_dir(follow_symlinks=False):stack.append((Path(entry.path),depth+1))
      else:total+=stat.st_size
      if total>4*1024**2:reason='OUTPUT_LIMIT';break
   if reason:win32job.TerminateJobObject(job,1);break
  k.WaitForSingleObject(pi.process,3000);check(k.GetExitCodeProcess(pi.process,C.byref(exitcode)))
  log=output/'run.log';text=''
  if log.exists() and not log.is_symlink() and not (log.lstat().st_file_attributes&0x400):
   with log.open('rb') as stream:text=stream.read(65536).decode('utf8',errors='replace')
  return {'status':reason or ('PASSED' if exitcode.value==0 else 'FAILED'),'exitCode':exitcode.value,'output':text,'seconds':round(time.monotonic()-began,3),'isolation':'Windows AppContainer','verifiedAppContainer':verified,'networkCapabilities':0,'administrator':False,'memoryMiB':memory_mb,'cpuPercent':20,'processLimit':1,'timeoutSeconds':timeout,'jobDirectory':str(jobdir)}
 finally:
  if pi.process:
   k.TerminateProcess(pi.process,1);k.CloseHandle(pi.thread);k.CloseHandle(pi.process)
  if job:job.Close()
  if attr:k.DeleteProcThreadAttributeList.argtypes=[C.c_void_p];k.DeleteProcThreadAttributeList(attr)
  if profile:u.DeleteAppContainerProfile(name)
  if sid:u.FreeSid(sid)
  # Remove the unique per-job ACL from shared interpreter if one was supplied.
  if runtime and 'sidstr' in locals():subprocess.run(['icacls.exe',str(runner),'/remove:g','*'+sidstr,'/T','/Q'],capture_output=True,timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)


