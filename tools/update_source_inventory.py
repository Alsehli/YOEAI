"""Refresh source inventories from version-controlled/public candidate files only."""
import hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def update():
 paths=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=ROOT).decode().split('\0')
 normal=[];lite=[]
 for name in sorted(set(paths)):
  p=ROOT/name
  if not name or not p.is_file():continue
  data=p.read_bytes();digest=hashlib.sha256(data).hexdigest()
  if name.startswith('source/'):normal.append({'path':name,'size':len(data),'sha256':digest})
  if name.startswith('editions/lite/source/'):
   rel=name[len('editions/lite/source/'):];lite.append({'path':rel,'bytes':len(data),'sha256':digest})
 (ROOT/'docs/source-inventory.json').write_text(json.dumps(normal,indent=2),encoding='utf8')
 (ROOT/'editions/lite/SOURCE-INVENTORY.json').write_text(json.dumps(lite,indent=2),encoding='utf8')
 print(json.dumps({'normal':len(normal),'lite':len(lite)}))
if __name__=='__main__':update()
