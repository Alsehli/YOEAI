"""Windows-native user-driven pickers; no toolkit/event-loop on HTTP threads."""
def choose_folder(title='Choose one folder for YOEAI documents'):
    import ctypes as C
    from ctypes import wintypes as W
    class Browse(C.Structure):
        _fields_=[('owner',W.HWND),('root',C.c_void_p),('display',W.LPWSTR),('title',W.LPCWSTR),('flags',W.UINT),('callback',C.c_void_p),('param',W.LPARAM),('image',C.c_int)]
    ole=C.OleDLL('ole32');ole.CoInitializeEx.argtypes=[C.c_void_p,W.DWORD];ole.CoInitializeEx.restype=C.c_long
    shell=C.WinDLL('shell32');shell.SHBrowseForFolderW.argtypes=[C.POINTER(Browse)];shell.SHBrowseForFolderW.restype=C.c_void_p;shell.SHGetPathFromIDListEx.argtypes=[C.c_void_p,W.LPWSTR,W.DWORD,W.DWORD];shell.SHGetPathFromIDListEx.restype=W.BOOL;ole.CoTaskMemFree.argtypes=[C.c_void_p]
    initialized=ole.CoInitializeEx(None,2)>=0;pidl=None
    try:
        if not initialized:raise ValueError('Windows could not initialize the folder picker.')
        display=C.create_unicode_buffer(32768);info=Browse();info.display=C.cast(display,W.LPWSTR);info.title=title;info.flags=0x51
        pidl=shell.SHBrowseForFolderW(C.byref(info))
        if not pidl:return None
        path=C.create_unicode_buffer(32768)
        if not shell.SHGetPathFromIDListEx(pidl,path,len(path),0):raise ValueError('Choose an existing local filesystem folder.')
        return path.value
    finally:
        if pidl:ole.CoTaskMemFree(pidl)
        if initialized:ole.CoUninitialize()
