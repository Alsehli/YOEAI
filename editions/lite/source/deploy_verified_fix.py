"""Replace current Lite delivery files, preserving backups and unchanged weights."""
from pathlib import Path
import hashlib,json,shutil,time
SOURCE=Path(__file__).resolve().parent;ROOT=SOURCE.parents[2]
WORK=ROOT/'lite-development/native-setup-20261017'
app=WORK/'app/YOEAILite.exe';setup=WORK/'setup/YOEAI-Lite-Setup.exe'
compiled=json.loads((WORK/'Verification/compiled-restricted-test.json').read_text(encoding='utf-8-sig'))
integrity=json.loads((WORK/'Verification/model-runtime-integrity.json').read_text(encoding='utf-8'))
assert compiled['status']=='PASS' and all(x['status']=='PASS' for x in integrity)
stamp=time.strftime('%Y%m%d-%H%M%S');backup=Path('D:/AI-Backups')/('YOEAI-Lite-before-native-fix-'+stamp)
targets=[ROOT/'YOEAI-Lite',Path('D:/YOEAI-Lite'),Path('D:/YOEAI-Packages/8GB-Lite')]
changes=[]
def digest(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def replace(source,destination,label):
 destination.parent.mkdir(parents=True,exist_ok=True)
 if destination.exists() and digest(destination)==digest(source):return
 if destination.exists():
  saved=backup/label/destination.relative_to(next((r for r in targets if destination.is_relative_to(r)),destination.parent))
  saved.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(destination,saved)
 shutil.copy2(source,destination);assert digest(source)==digest(destination)
 changes.append(str(destination))
for target in targets:
 label='C-working' if target.drive.upper()=='C:' else target.name
 assert target.is_dir()
 replace(app,target/'YOEAILite.exe',label)
 replace(setup,target/'YOEAI-Lite-Setup.exe',label)
 for p in SOURCE.iterdir():
  if p.is_file() and p.suffix in ['.py','.html','.ico']:replace(p,target/'Source'/p.name,label)
 for p in (WORK/'online-payload/Licenses').iterdir():
  if p.is_file():replace(p,target/'Licenses'/p.name,label)
 replace(WORK/'online-payload/Documents/SETUP-AND-REPAIR.md',target/'Documents/SETUP-AND-REPAIR.md',label)
 # Retire the visibly old guides outside customer delivery folders, not in a second app folder.
 for old in list((target/'Documents').glob('Alsehli*.pdf')):
  assert old.resolve().is_relative_to(target.resolve())
  saved=backup/label/'Historical-documents'/old.name;saved.parent.mkdir(parents=True,exist_ok=True)
  shutil.move(str(old),str(saved));changes.append(str(old)+' -> archived')
 for p in [target/'START-HERE.txt',*(target/'Documents').glob('*.md')]:
  if not p.is_file():continue
  text=p.read_text(encoding='utf-8-sig')
  changed=text.replace('ALSEHLI AI LITE','YOEAI LITE').replace('Alsehli AI Lite','YOEAI Lite').replace('Alsehli-AI-Lite-TextImage','YOEAI-Lite').replace('Alsehli AI','YOEAI').replace('Update-Installed-Lite.ps1','YOEAI-Lite-Setup.exe').replace('The existing personal Q6_K/voice Alsehli AI installation is unchanged.','The existing personal application and model configuration are preserved.')
  if changed!=text:
   saved=backup/label/p.relative_to(target);saved.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,saved)
   p.write_text(changed,encoding='utf-8');changes.append(str(p))
 (target/'START-HERE.txt').write_text('YOEAI LITE - TEXT AND IMAGE EDITION\n\nSTART HERE: run YOEAI-Lite-Setup.exe in this folder.\nKeep the entire folder together when copying to another Windows PC.\nThe installer reuses the included offline model and CUDA runtime.\nExisting installations are updated without downloading models again.\n\nThe old PowerShell-script updater has been replaced with bundled native code.\nDo not change Windows execution policy. Setup creates one YOEAI Lite desktop shortcut.\n\nRequirements: Windows 11 x64, compatible NVIDIA GPU with 8 GB+ VRAM,\n16 GB system RAM minimum (32 GB recommended), Microsoft Edge, compatible\nNVIDIA driver and 25 GB free SSD space for a new installation.\nIf required, use Microsoft Visual C++ x64 runtime from the official Microsoft link\nin Documents/SETUP-AND-REPAIR.md.\n\nUnsigned development/test build: fresh second-PC and 8 GB GPU verification\nremain pending. Read Documents/YOEAI-Lite-Setup-Verification.pdf for tested scope.\nLocal text/image inference uses the existing Q4_K_M model and vision projector.\nLite context supports up to 8,192 tokens subject to memory. Existing settings\nand private histories are preserved. Historical names in a private legacy\nAppData directory exist only to retain compatibility, not as a second app.\n\nOptional browser and editor integrations are in Integrations and Documents.\nNo voice, unrestricted PC control, cloud AI or subscription is added.\n',encoding='utf-8')
 for name in ['Install-Lite.bat','Update-Installed-Lite.bat']:(target/name).write_bytes(b'@echo off\r\n"%~dp0YOEAI-Lite-Setup.exe"\r\n')
 (target/'Update-Installed-Lite.ps1').write_text("# Compatibility entry only. Current setup does not use PowerShell scripts.\n& (Join-Path $PSScriptRoot 'YOEAI-Lite-Setup.exe')\n",encoding='utf-8')
 (target/'Source/BUILD.md').write_text('YOEAI Lite native setup rebuild\n\nBuild tools: Windows x64, CPython 3.13.7, PyInstaller 6.22.3, pywin32 311.\nRun python build_native_setup.py from this development repository.\nThe build script stages the source, bundled Windows shortcut helper, notices and\nverified payload. It never includes model weights in the setup EXE.\nSource branch: fix/yoeai-lite-native-setup.\nRuntime inference remains the existing llama.cpp CUDA process.\nNo PowerShell scripts or execution-policy changes are used for setup/update.\nExisting private legacy data paths are retained for history compatibility.\n',encoding='utf-8')
 # Retire outdated build/updater scripts that could recreate the old branding.
 for old_name in ['create_guide.py','package_lite.py','package_update.py','Update-Installed-Lite.ps1','Update-Installed-Lite.bat']:
  old=target/'Source'/old_name
  if old.exists():
   saved=backup/label/'Historical-source'/old_name;saved.parent.mkdir(parents=True,exist_ok=True);shutil.move(str(old),str(saved))
 # Preserve model/runtime entries; recalculate all current small files and refreshed delivery files.
 manifest=target/'package-manifest.json';data=json.loads(manifest.read_text(encoding='utf-8-sig'))
 cached={item['path']:item for item in data['files']};entries=[]
 for p in sorted(target.rglob('*')):
  if not p.is_file() or p==manifest or '__pycache__' in p.parts:continue
  relative=p.relative_to(target).as_posix()
  if relative.startswith(('Models/','Runtime/')) and relative in cached:
   assert p.stat().st_size==cached[relative]['size'];entries.append(cached[relative])
  else:entries.append({'path':relative,'size':p.stat().st_size,'sha256':digest(p)})
 data.update(product='YOEAI Lite - Text and Image Edition',version='0.1.1-native-setup',files=entries)
 manifest.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
outer=Path('D:/YOEAI-Packages/YOEAI-Lite-Setup.exe');replace(setup,outer,'Setup-root')
summary={'status':'PASS','changedFiles':changes,'backup':str(backup),'appSha256':digest(app),'setupSha256':digest(setup),'modelsCopied':False,'targets':[str(x) for x in targets]}
(WORK/'Verification/deployment.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps({'status':'PASS','changedFiles':len(changes),'backup':str(backup),'modelsCopied':False}))
