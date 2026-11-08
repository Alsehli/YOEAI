"""Windows Shell links through documented COM interfaces; no pywin32 runtime."""
import ctypes as C,uuid,contextlib
from pathlib import Path
P=C.c_void_p;H=C.c_long;U=C.c_uint32;W=C.c_wchar_p

def guid(value):return (C.c_ubyte*16).from_buffer_copy(uuid.UUID(value).bytes_le)
def checked(hr,action):
 if hr<0:raise OSError(action+' failed (Windows HRESULT 0x%08X).'%(hr&0xffffffff))
def method(ptr,index,result,*args):
 table=C.cast(ptr,C.POINTER(C.POINTER(P))).contents
 return C.WINFUNCTYPE(result,P,*args)(table[index])
def release(ptr):
 if ptr:method(ptr,2,U)(ptr)
@contextlib.contextmanager
def link_object():
 ole=C.WinDLL('ole32');ole.CoInitializeEx.argtypes=[P,U];ole.CoInitializeEx.restype=H
 initialized=ole.CoInitializeEx(None,2)
 if initialized<0 and initialized!=-2147417850:checked(initialized,'Windows COM initialization')
 obj=P();persist=P()
 try:
  ole.CoCreateInstance.argtypes=[P,P,U,P,C.POINTER(P)];ole.CoCreateInstance.restype=H
  checked(ole.CoCreateInstance(guid('00021401-0000-0000-c000-000000000046'),None,1,guid('000214f9-0000-0000-c000-000000000046'),C.byref(obj)),'Create Shell link')
  checked(method(obj,0,H,P,C.POINTER(P))(obj,guid('0000010b-0000-0000-c000-000000000046'),C.byref(persist)),'Get shortcut persistence')
  yield obj,persist
 finally:
  release(persist);release(obj)
  if initialized>=0:ole.CoUninitialize()
def desktop_folder():
 shell=C.WinDLL('shell32');ole=C.WinDLL('ole32');value=P();shell.SHGetKnownFolderPath.argtypes=[P,U,P,C.POINTER(P)];shell.SHGetKnownFolderPath.restype=H;ole.CoTaskMemFree.argtypes=[P]
 checked(shell.SHGetKnownFolderPath(guid('b4bfcc3a-db2c-424c-b029-7fe99a87c641'),0,None,C.byref(value)),'Find Desktop folder')
 try:return Path(C.cast(value,W).value)
 finally:ole.CoTaskMemFree(value)
def shortcut_target(path):
 with link_object() as (obj,persist):
  checked(method(persist,5,H,W,U)(persist,str(Path(path).resolve()),0),'Read shortcut')
  buffer=C.create_unicode_buffer(32768);checked(method(obj,3,H,W,C.c_int,P,U)(obj,buffer,len(buffer),None,4),'Read shortcut target');return Path(buffer.value)
def shortcut(target,destination=None):
 target=Path(target).resolve();destination=Path(destination).resolve() if destination else desktop_folder()/'YOEAI Lite 2.0.lnk'
 if not target.is_file():raise ValueError('The shortcut target is missing.')
 if destination.exists() and shortcut_target(destination).resolve()!=target:raise ValueError('A different shortcut already uses this name; it was preserved.')
 destination.parent.mkdir(parents=True,exist_ok=True)
 with link_object() as (obj,persist):
  checked(method(obj,20,H,W)(obj,str(target)),'Set shortcut target');checked(method(obj,9,H,W)(obj,str(target.parent)),'Set working folder');checked(method(obj,7,H,W)(obj,'YOEAI Lite - local text and image AI'),'Set shortcut description');checked(method(obj,17,H,W,C.c_int)(obj,str(target),0),'Set shortcut icon');checked(method(persist,6,H,W,C.c_int)(persist,str(destination),1),'Save shortcut')
 if not destination.is_file() or shortcut_target(destination).resolve()!=target:raise OSError('Windows could not verify the saved shortcut.')
 return destination
