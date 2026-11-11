"""Installation-local sandbox qualification. Only fixed diagnostic code runs."""
import hashlib,json,os,uuid,shutil
from pathlib import Path
def owner():
    import win32api,win32security,winreg
    token=win32security.OpenProcessToken(win32api.GetCurrentProcess(),8)
    try:sid=win32security.ConvertSidToStringSid(win32security.GetTokenInformation(token,win32security.TokenUser)[0])
    finally:token.Close()
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r'SOFTWARE\Microsoft\Cryptography',0,winreg.KEY_READ|winreg.KEY_WOW64_64KEY) as key:machine=winreg.QueryValueEx(key,'MachineGuid')[0]
    return hashlib.sha256((machine+'\0'+sid).encode()).hexdigest()
def qualify(root,home):
    from update_sandbox import run
    root=Path(root);runtime=root/'SandboxRuntime';home=Path(home)/'Qualification';home.mkdir(parents=True,exist_ok=True)
    canary=home/('host-'+uuid.uuid4().hex+'.txt');canary.write_text('synthetic isolation canary');result={}
    code="""import socket,subprocess,sys
try:open(CANARY).read();raise AssertionError('host read allowed')
except OSError:pass
try:
 s=socket.socket();s.settimeout(1);s.connect(('127.0.0.1',8087));raise AssertionError('network allowed')
except OSError:pass
try:subprocess.run([sys.executable,'-c','pass'],check=True);raise AssertionError('child allowed')
except (OSError,subprocess.SubprocessError):pass
print('isolation verified')
""".replace('CANARY',repr(str(canary)))
    try:
        result=run(home,{'test_main.py':code},timeout=12,runtime=runtime)
        if result['status']!='PASSED' or not result.get('verifiedAppContainer'):raise ValueError('The fixed AppContainer qualification failed.')
        value={'passed':True,'owner':owner(),'runtimeManifestSHA256':hashlib.sha256((runtime/'runtime-manifest.json').read_bytes()).hexdigest(),'checks':['hostRead','loopbackNetwork','childProcess'],'isolation':'Windows AppContainer'}
        (runtime/'qualification.json').write_text(json.dumps(value,indent=2),encoding='utf8');return value
    finally:
        canary.unlink(missing_ok=True)
        if result.get('jobDirectory'):
            path=Path(result['jobDirectory']).resolve()
            if path.is_relative_to(home.resolve()) and len(path.name)==32:shutil.rmtree(path)
