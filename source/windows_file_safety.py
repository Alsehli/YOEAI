"""Deterministic cleanup protection shared by the agent and explorer UI."""
import os,ctypes
from pathlib import Path

PROTECTED_SUFFIXES={'.gguf','.safetensors','.onnx','.ckpt','.dll','.sys','.pyd','.db','.sqlite','.sqlite3','.vhd','.vhdx','.py','.js','.ts','.tsx','.jsx','.cpp','.c','.h','.cs','.java','.rs','.go','.sln','.vcxproj','.lock','.ps1','.bat','.cmd'}
def cleanup_allowed(path):
 p=Path(path);parts={x.lower() for x in p.parts}
 if p.suffix.lower() in PROTECTED_SUFFIXES or parts & {'steamapps','drivers','backend','modelbackends','runtime','_internal','.git'}:raise ValueError('This model, dependency, game data, database or project file is protected from agent cleanup. Use its application/uninstaller or manage it manually.')
 if p.suffix.lower() in {'.json','.yaml','.yml','.ini','.toml','.cfg'} and any(word in p.stem.lower() for word in ['model','config','tokenizer','generation','manifest']):raise ValueError('Application/model configuration is protected from cleanup.')

def available(path):
 if os.name!='nt':return
 from ctypes import wintypes
 k=ctypes.WinDLL('kernel32',use_last_error=True);k.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE];k.CreateFileW.restype=wintypes.HANDLE;k.CloseHandle.argtypes=[wintypes.HANDLE]
 # A point-in-time exclusive attribute handle. The actual filesystem operation
 # must still handle locks/permission changes occurring after this check.
 h=k.CreateFileW(str(Path(path)),0x80000000,0,None,3,0x00200000|(0x02000000 if Path(path).is_dir() else 0),None)
 if h==ctypes.c_void_p(-1).value:
  code=ctypes.get_last_error();raise OSError(code,'File is in use or access is denied. Close the application and review a fresh action.',str(path))
 k.CloseHandle(h)

def native_copy(source,destination,cancel,progress):
 """Windows CopyFileEx: fail on collisions, preserve streams, cancel cooperatively."""
 from ctypes import wintypes
 k=ctypes.WinDLL('kernel32',use_last_error=True)
 callback_type=ctypes.WINFUNCTYPE(wintypes.DWORD,ctypes.c_longlong,ctypes.c_longlong,ctypes.c_longlong,ctypes.c_longlong,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE,wintypes.HANDLE,ctypes.c_void_p)
 def callback(total,transferred,stream_size,stream_transferred,number,reason,src,dst,data):
  progress(transferred)
  return 1 if cancel() else 0
 callback_ref=callback_type(callback);flag=wintypes.BOOL(False)
 k.CopyFileExW.argtypes=[wintypes.LPCWSTR,wintypes.LPCWSTR,callback_type,ctypes.c_void_p,ctypes.POINTER(wintypes.BOOL),wintypes.DWORD];k.CopyFileExW.restype=wintypes.BOOL
 def extended(p):
  value=str(Path(p).absolute())
  if len(value)>=240 and not value.startswith('\\\\?\\'):value=('\\\\?\\UNC\\'+value[2:]) if value.startswith('\\\\') else '\\\\?\\'+value
  return value
 if not k.CopyFileExW(extended(source),extended(destination),callback_ref,None,ctypes.byref(flag),0x1|0x800):
  code=ctypes.get_last_error()
  if code==1235 or cancel():raise InterruptedError('Copy cancelled. Original retained; inspect destination for any partial copy.')
  raise ctypes.WinError(code)
