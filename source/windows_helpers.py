"""Read-only Windows helpers with the existing task scope and identity checks."""
import os,time,contextlib
from pathlib import Path

def known(name):
 from ctypes import windll,wintypes,byref,Structure,c_ushort,c_ubyte,c_ulong,POINTER
 import uuid
 ids={'downloads':'374de290-123f-4565-9164-39c4925e467b','documents':'fdd39ad0-238f-46af-adb4-6c85480369c7','pictures':'33e28130-4e1e-4676-835a-98395c3bc3bb','desktop':'b4bfcc3a-db2c-424c-b029-7fe99a87c641'}
 class GUID(Structure):_fields_=[('a',c_ulong),('b',c_ushort),('c',c_ushort),('d',c_ubyte*8)]
 g=GUID.from_buffer_copy(uuid.UUID(ids[name]).bytes_le);p=wintypes.LPWSTR();shell=windll.shell32;shell.SHGetKnownFolderPath.argtypes=[POINTER(GUID),wintypes.DWORD,wintypes.HANDLE,POINTER(wintypes.LPWSTR)]
 if shell.SHGetKnownFolderPath(byref(g),0,None,byref(p))!=0:raise ValueError('Windows could not locate that folder.')
 try:return {'name':name,'path':p.value,'verified':Path(p.value).is_dir(),'accessGranted':False}
 finally:windll.ole32.CoTaskMemFree(p)

def app_info(app,scope):
 from windows_tools import app_paths,identify_app
 import psutil
 if app not in scope['apps']:raise ValueError('Select this application in the task scope first.')
 result=app_paths().get(app,{}).copy();rows=[]
 for process in psutil.process_iter(['pid','name','exe','memory_info']):
  try:
   if identify_app(process.info['exe'] or '')!=app:continue
   process.cpu_percent();rows.append((process,process.info))
  except (psutil.Error,OSError):continue
 time.sleep(.2);readings=[]
 for process,info in rows[:50]:
  try:readings.append({'pid':info['pid'],'cpuPercent':process.cpu_percent(),'ramBytes':process.memory_info().rss})
  except psutil.Error:continue
 return {'app':app,**result,'running':bool(readings),'processes':readings,'samplingSeconds':.2,'verified':True,'notice':'Measured process usage does not by itself prove the cause of a slowdown.'}

def selected(scope,context):
 from windows_tools import target_window
 from windows_policy import scoped_path
 import pythoncom,win32com.client
 hwnd,app=target_window(scope,context.get('window'))
 if app!='explorer':raise ValueError('Choose an approved File Explorer window first.')
 pythoncom.CoInitialize()
 try:
  for window in win32com.client.Dispatch('Shell.Application').Windows():
   with contextlib.suppress(AttributeError):
    if int(window.HWND)!=hwnd:continue
    items=window.Document.SelectedItems();out=[]
    if items.Count>40:raise ValueError('Select at most 40 files.')
    for item in items:
     actual=Path(item.Path).resolve()
     try:relative=str(actual.relative_to(Path(scope['folder'])))
     except (ValueError,TypeError):raise ValueError('The selection is outside the approved folder. Choose that folder in task permissions first.')
     checked=scoped_path(scope['folder'],relative)
     if checked.is_file():out.append(relative)
    return {'selectedFiles':out,'verified':True,'source':'Approved Explorer selection; not guessed from the filename.'}
  raise ValueError('The selected Explorer window was not found.')
 finally:pythoncom.CoUninitialize()

def stat(path,scope):
 from windows_policy import scoped_path
 root=Path(scope['folder']);total=0;count=0;truncated=False;start=time.monotonic()
 if path.is_file():return {'path':str(path.relative_to(root)),'bytes':path.stat().st_size,'modified':path.stat().st_mtime,'type':'file','verified':True}
 for current,dirs,files in os.walk(path,followlinks=False):
  safe=[]
  for d in dirs:
   with contextlib.suppress(ValueError,OSError):scoped_path(root,str((Path(current)/d).relative_to(root)));safe.append(d)
  dirs[:]=safe
  for f in files:
   try:total+=scoped_path(root,str((Path(current)/f).relative_to(root))).stat().st_size;count+=1
   except (ValueError,OSError):continue
   if count>=2000 or time.monotonic()-start>4:truncated=True;break
  if truncated:break
 return {'path':str(path.relative_to(root)),'bytesCounted':total,'filesCounted':count,'truncated':truncated,'verified':True,'notice':'Partial totals only.' if truncated else 'Bounded traversal completed; protected paths were excluded.'}


def shortcut(p,scope):
 from windows_policy import scoped_path
 from windows_tools import app_paths
 import pythoncom,win32com.client
 app=p['app'];entry=app_paths().get(app,{})
 if app not in scope['apps'] or not entry.get('installed'):raise ValueError('Choose an approved installed application.')
 dest=scoped_path(scope['folder'],p['destination'],False)
 if dest.exists():raise ValueError('A shortcut already exists at that name.')
 pythoncom.CoInitialize()
 try:
  import tempfile
  with tempfile.TemporaryDirectory(prefix='YOEAI-shortcut-',dir=dest.parent) as directory:
   temp=Path(directory)/'new.lnk';link=win32com.client.Dispatch('WScript.Shell').CreateShortcut(str(temp));link.TargetPath=entry['path'];link.WorkingDirectory=str(Path(entry['path']).parent);link.Save()
   with dest.open('xb') as output:output.write(temp.read_bytes())
  check=win32com.client.Dispatch('WScript.Shell').CreateShortcut(str(dest))
  return {'saved':str(dest),'target':check.TargetPath,'verified':dest.is_file() and Path(check.TargetPath).resolve()==Path(entry['path']).resolve()}
 finally:pythoncom.CoUninitialize()
