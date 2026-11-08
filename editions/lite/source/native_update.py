"""Native Windows Lite update and shortcuts; no PowerShell scripts or policy changes."""

import json,os,shutil,socket,subprocess,time,uuid

from pathlib import Path



def data_home():

    base=Path(os.environ['LOCALAPPDATA']);legacy=base/'AlsehliAILite'

    # Keep existing histories/configuration in place. New installations use YOEAI.

    return legacy if (legacy/'profile.json').exists() or (legacy/'App').exists() else base/'YOEAILite'



def desktop_folder():

    from win32com.shell import shell,shellcon

    return Path(shell.SHGetFolderPath(0,shellcon.CSIDL_DESKTOPDIRECTORY,0,0))



def shortcut(target,destination=None):

    import pythoncom,win32com.client

    destination=Path(destination) if destination else desktop_folder()/'YOEAI Lite 2.0.lnk'

    destination.parent.mkdir(parents=True,exist_ok=True)

    pythoncom.CoInitialize()

    try:

        link=win32com.client.Dispatch('WScript.Shell').CreateShortCut(str(destination))

        link.TargetPath=str(Path(target).resolve());link.WorkingDirectory=str(Path(target).resolve().parent)

        link.Description='YOEAI Lite - local text and image AI';link.IconLocation=str(Path(target).resolve())+',0';link.Save();link=None

    finally:pythoncom.CoUninitialize()

    return destination



def busy_ports(profile):

    for key in ['apiPort','uiPort']:

        with socket.socket() as probe:

            probe.settimeout(.3)

            if probe.connect_ex(('127.0.0.1',int(profile[key])))==0:return True

    return False



def update(payload,data=None,make_shortcut=shortcut,stopper=None,selection=None):

    payload=Path(payload);data=Path(data) if data else data_home()

    profile_path=data/'profile.json'

    if not profile_path.is_file():raise RuntimeError('An incomplete Lite installation was found. No files changed. Use the complete offline package to repair it.')

    profile=json.loads(profile_path.read_text(encoding='utf-8-sig'))

    root=data/'App/0.1.0';source=payload/'YOEAILite.exe'

    if not source.is_file():raise RuntimeError('The verified YOEAI Lite application is missing from setup.')

    backend=profile.get('backend')

    if backend and Path(backend).resolve()!=(root/'Backend/llama-server.exe').resolve():raise RuntimeError('Custom backend configuration found; preserved without changes.')

    from native_payload import check

    check(payload)

    old=next((p for p in [root/'YOEAILite.exe',root/'AlsehliAILite.exe'] if p.is_file()),None)

    if old is None:raise RuntimeError('Installed Lite executable is missing. Model and profile were preserved.')

    effective=dict(profile);effective.update(selection or {})

    for key in ['model','projector']:

        if key=='projector' and not effective.get(key):continue

        if not Path(effective.get(key,'')).is_file():raise RuntimeError('Existing '+key+' file is missing. Reconnect its drive; no model download was started.')

    staged=root/('.yoeai-update-'+uuid.uuid4().hex+'.exe');shutil.copy2(source,staged)

    backup=data/'UpdateBackups'/time.strftime('%Y%m%d-%H%M%S')/uuid.uuid4().hex[:8];backup.mkdir(parents=True)

    shutil.copy2(profile_path,backup/'profile.json')

    shutil.copy2(old,backup/old.name)

    if stopper is None:

        def stopper(exe):

            result=subprocess.run([str(exe),'--stop','--headless'],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW,timeout=35)

            if result.returncode:raise RuntimeError('Lite could not close gracefully. Close its window and retry. The previous application is preserved.')

    stopper(staged)

    deadline=time.monotonic()+20

    while busy_ports(profile):

        if time.monotonic()>deadline:raise RuntimeError('A Lite port is still occupied. No process was forcibly stopped; retry after closing Lite.')

        time.sleep(.2)

    target=root/'YOEAILite.exe'

    while True:

        try:os.replace(staged,target);break

        except PermissionError:

            if time.monotonic()>deadline:raise RuntimeError('The existing app is still closing. Its backup and profile were preserved; retry shortly.')

            time.sleep(.2)

    # Rename an owned legacy EXE only after successful promotion; keep it in backup.

    if old!=target and old.exists():os.replace(old,backup/old.name)

    for name in ['Documents','Licenses','Source','Speech','NativeEngine','NativeRuntime']:

        if (payload/name).is_dir():shutil.copytree(payload/name,root/name,dirs_exist_ok=True)

    if selection:

        profile.update(selection,loadOnDemand=True)

        temporary=profile_path.with_suffix('.json.selection');temporary.write_text(json.dumps(profile,indent=2),encoding='utf8');os.replace(temporary,profile_path)

    link=make_shortcut(target)

    # The old branding shortcut is archived only if it targets this same installation.

    legacy=Path(link).with_name('Alsehli AI Lite.lnk')

    if legacy.exists():

        import pythoncom,win32com.client

        pythoncom.CoInitialize()

        try:

            prior=win32com.client.Dispatch('WScript.Shell').CreateShortCut(str(legacy))

            if Path(prior.TargetPath).resolve() in [old.resolve(),target.resolve()]:os.replace(legacy,backup/legacy.name)

            prior=None

        finally:pythoncom.CoUninitialize()

    return {'status':'PASS','app':str(target),'backup':str(backup),'shortcut':str(link),'profilePreserved':not bool(selection),'modelSelectionChanged':bool(selection),'powershellUsed':False}
