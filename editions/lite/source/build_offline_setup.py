from pathlib import Path
import os,shutil,json,hashlib,subprocess,sys,importlib.metadata
root=Path(__file__).resolve().parent.parent;S=root/'Source'
dest=root/'Offline-Release';payload=dest/'Payload'
payload.mkdir(parents=True,exist_ok=True)
def copy(a,b):
 a=Path(a);b=Path(b);b.parent.mkdir(parents=True,exist_ok=True)
 if b.exists():
  if os.path.samefile(a,b):return str(b)
  b.unlink()
 try:os.link(a,b)
 except OSError:shutil.copy2(a,b)
 return str(b)
copy(root/'App-Dist/YOEAILite.exe',payload/'YOEAILite.exe')
for name in ['NativeRuntime','NativeEngine','Speech','Models','Licenses','Documents','RuntimeSupport','ImageGeneration','SearchRuntime']:
 print('Staging '+name,flush=True);shutil.copytree(root/name,payload/name,dirs_exist_ok=True,copy_function=copy)
shutil.copytree(S,payload/'Source',dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'),copy_function=shutil.copy2)
lic=payload/'Licenses/Build-Dependencies';lic.mkdir(parents=True,exist_ok=True);inventory=[]
for dist in importlib.metadata.distributions():
 name=dist.metadata.get('Name','unknown');record={'name':name,'version':dist.version,'license':dist.metadata.get('License-Expression') or dist.metadata.get('License'),'files':[]}
 for f in dist.files or []:
  if ('license' in str(f).lower() or 'copying' in str(f).lower()) and str(f).endswith(('.txt','.md','LICENSE','COPYING','.rst')):
   p=Path(dist.locate_file(f))
   if p.is_file():target=lic/name/str(f).replace('..','_');target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target);record['files'].append(target.relative_to(payload).as_posix())
 inventory.append(record)
(lic/'inventory.json').write_text(json.dumps(inventory,indent=2),encoding='utf8')
shutil.make_archive(str(payload/'corresponding-app-source'),'zip',S)
files=[]
for f in sorted(payload.rglob('*')):
 if f.is_file() and f.name!='package-manifest.json':
  with f.open('rb') as stream:h=hashlib.file_digest(stream,'sha256').hexdigest()
  files.append({'path':f.relative_to(payload).as_posix(),'size':f.stat().st_size,'sha256':h})
(payload/'package-manifest.json').write_text(json.dumps({'version':'2.0.4','edition':'Lite 8GB','offline':True,'files':files},indent=2),encoding='utf8')
(dest/'READ-ME.txt').write_text('YOEAI Lite 2.0.4 â€” complete offline installer\n\nRun Setup.exe. Keep it beside the Payload folder.\nIncludes the existing 9B Q4 GGUF, matching vision projector, native CUDA engine, and offline English read-aloud voice. No model downloads are needed.\nExisting installations retain their selected model and conversation history.\nSettings > Local AI model: Find models, select a GGUF, Load, or Unload. Matching projectors can be selected for vision. Voice is English read-aloud; microphone transcription is not included.\nUnsigned local build; tested on this RTX 3090 Windows PC. Clean-PC and 8GB-GPU qualification remain pending.\n',encoding='utf8')
args=['--noconfirm','--onefile','--windowed','--name','Setup','--paths',str(S),'--version-file',str(S/'version-resource.txt'),'--icon',str(S/'yoeai.ico'),'--distpath',str(dest),'--workpath',str(root/'Build-Offline-Setup'),'--specpath',str(root),'--exclude-module','torch','--exclude-module','PySide6',str(S/'offline_setup.py')]
subprocess.run([sys.executable,'-m','PyInstaller',*args],check=True)
print(json.dumps({'installer':str(dest/'Setup.exe'),'files':len(files),'payloadBytes':sum(x['size'] for x in files)}))
