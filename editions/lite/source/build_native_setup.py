"""Rebuild Lite 2.0.1 app/setup from the supplied source, offline Speech files and notices.
Requires the existing Windows CPython/PyInstaller/pywin32 build environment.
Does not download or bundle the GGUF model or CUDA archives.
"""
from pathlib import Path
import hashlib,json,os,shutil,subprocess,sys
S=Path(__file__).resolve().parent;ROOT=S.parent;WORK=Path(os.environ.get('YOEAI_LITE_BUILD_WORK',str(ROOT/'Build-2.0.2')));PAYLOAD=Path(os.environ.get('YOEAI_LITE_PAYLOAD',str(WORK/'online-payload')))
def run(args,log):
 with open(WORK/log,'w',encoding='utf8') as out:subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm',*args],stdout=out,stderr=subprocess.STDOUT,check=True)
def link_or_copy(source,destination):
 if Path(destination).exists() and os.path.samefile(source,destination):return
 try:os.link(source,destination)
 except (OSError,FileExistsError):shutil.copy2(source,destination)
WORK.mkdir(exist_ok=True)
if '--app-built' not in sys.argv:
 run(['--onefile','--windowed','--name','YOEAILite','--version-file',str(S/'version-resource.txt'),'--icon',str(S/'yoeai.ico'),'--add-data',str(S/'ui.html')+';.','--add-data',str(S/'assets')+';assets','--distpath',str(WORK/'app'),'--workpath',str(WORK/'build-app'),'--specpath',str(WORK),'--collect-submodules','ddgs','--collect-all','primp','--collect-all','lxml','--copy-metadata','ddgs','--copy-metadata','primp','--copy-metadata','lxml','--collect-all','playwright','--collect-submodules','pywinauto','--collect-submodules','comtypes','--collect-all','psutil','--exclude-module','torch','--exclude-module','PySide6',str(S/'app.py')],'app-build.log')
else:
 (WORK/'app').mkdir(exist_ok=True);shutil.copy2(ROOT/'App-Dist/YOEAILite.exe',WORK/'app/YOEAILite.exe')
PAYLOAD.mkdir(exist_ok=True);shutil.copy2(WORK/'app/YOEAILite.exe',PAYLOAD/'YOEAILite.exe')
for name in ['Documents','Licenses','Speech','RuntimeSupport','NativeEngine','NativeRuntime']:
 if not (ROOT/name).is_dir():raise RuntimeError('Required package folder missing: '+name)
 shutil.copytree(ROOT/name,PAYLOAD/name,dirs_exist_ok=True,copy_function=link_or_copy if name=='Speech' else shutil.copy2)
shutil.copytree(S,PAYLOAD/'Source',dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__'))
files=[]
for file in sorted(PAYLOAD.rglob('*')):
 if file.is_file() and file!=PAYLOAD/'package-manifest.json':
  with file.open('rb') as stream:sha=hashlib.file_digest(stream,'sha256').hexdigest()
  files.append({'path':file.relative_to(PAYLOAD).as_posix(),'size':file.stat().st_size,'sha256':sha})
(PAYLOAD/'package-manifest.json').write_text(json.dumps({'version':'2.0.3','edition':'Lite 8GB','files':files},indent=2),encoding='utf8')
run(['--onefile','--windowed','--name','YOEAI-Lite-Setup','--version-file',str(S/'version-resource.txt'),'--icon',str(S/'yoeai.ico'),'--add-data',str(PAYLOAD)+';online-payload','--distpath',str(WORK/'setup'),'--workpath',str(WORK/'build-setup'),'--specpath',str(WORK),'--exclude-module','torch','--exclude-module','PySide6',str(S/'online_setup.py')],'setup-build.log')
print(json.dumps({'status':'PASS','app':str(WORK/'app/YOEAILite.exe'),'setup':str(WORK/'setup/YOEAI-Lite-Setup.exe'),'verifiedPayloadFiles':len(files)}))
