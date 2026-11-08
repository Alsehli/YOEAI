from pathlib import Path
import json,hashlib,shutil
SOURCE=Path(__file__).resolve().parent;ROOT=SOURCE.parents[2];WORK=ROOT/'lite-development/native-setup-20261017';OUT=WORK/'Verification'
def digest(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
integrity=json.loads((OUT/'model-runtime-integrity.json').read_text(encoding='utf-8'))
assert len(integrity)==12 and all(x['status']=='PASS' for x in integrity)
deployment=json.loads((OUT/'deployment.json').read_text(encoding='utf-8'))
summary={'status':'PASS for package and isolated setup tests','version':'0.1.1-native-setup','tests':{'sourceRegressions':'18 PASS','compiledRestrictedPolicy':'PASS','pinnedModelRuntimeSha256':'12 PASS','freshOtherPCInstall':'NOT TESTED - transfer current package and retest','new8GBInference':'NOT TESTED','trustedSigning':'NOT SIGNED'},'appSha256':deployment['appSha256'],'setupSha256':deployment['setupSha256'],'modelsRecopied':False,'historicalBackup':deployment['backup']}
(OUT/'final-results.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
targets=[ROOT/'YOEAI-Lite',Path('D:/YOEAI-Lite'),Path('D:/YOEAI-Packages/8GB-Lite')]
for target in targets:
 assert digest(target/'YOEAILite.exe')==deployment['appSha256'] and digest(target/'YOEAI-Lite-Setup.exe')==deployment['setupSha256']
 docs=target/'Documents/Setup-Fix-20261017';docs.mkdir(parents=True,exist_ok=True)
 copied=[]
 for name in ['unit-tests.log','compiled-restricted-test.json','model-runtime-integrity.json','deployment.json','final-results.json']:
  src=OUT/name;dest=docs/name;shutil.copy2(src,dest);copied.append(dest)
 pdf=target/'Documents/YOEAI-Lite-Setup-Verification.pdf';shutil.copy2(OUT/pdf.name,pdf);copied.append(pdf)
 for name in ['write_setup_report.py','finalize_verification.py']:
  dest=target/'Source'/name;shutil.copy2(SOURCE/name,dest);copied.append(dest)
 result=target/'verification-result.json';result.write_text(json.dumps(summary,indent=2),encoding='utf-8');copied.append(result)
 manifest=target/'package-manifest.json';data=json.loads(manifest.read_text(encoding='utf-8-sig'))
 for p in copied:
  rel=p.relative_to(target).as_posix();data['files']=[x for x in data['files'] if x['path']!=rel]+[{'path':rel,'size':p.stat().st_size,'sha256':digest(p)}]
 manifest.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
 # Every current small delivery file must match its manifest, not stale previous branding.
 count=0
 for entry in data['files']:
  if entry['path'].startswith(('Models/','Runtime/')):continue
  path=target/entry['path'];assert path.is_file() and path.stat().st_size==entry['size'] and digest(path)==entry['sha256'],str(path);count+=1
 assert not list(target.rglob('Alsehli*.pdf'))
 print(str(target)+': '+str(count)+' small file hashes PASS; current EXEs and branding verified')
assert digest(Path('D:/YOEAI-Packages/YOEAI-Lite-Setup.exe'))==deployment['setupSha256']
