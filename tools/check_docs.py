"""Verify release documentation links, official banner and preserved source inventory."""
import hashlib,json,re,subprocess,sys
from pathlib import Path
from urllib.parse import unquote
from PIL import Image
R=Path(__file__).resolve().parents[1]
errors=[];links=0;documents=0
paths=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=R).decode().split('\0')
for name in paths:
 p=R/name
 if p.suffix!='.md' or not p.is_file():continue
 if name.startswith('source/'):
  # Verbatim vendor README excerpts retain upstream-relative references.
  # This check covers project-authored release docs, not upstream mirrors.
  continue
 documents+=1
 for url in re.findall(r'\]\(([^)\s]+)',p.read_text(encoding='utf-8-sig')):
  if url.startswith(('https:','http:','mailto:','#')):continue
  target=unquote(url.split('#')[0])
  if not target:continue
  links+=1
  if not (p.parent/target).exists():errors.append(f'{name}: broken relative link {target}')
banner=R/'docs/images/social-preview.png'
if not banner.exists() or Image.open(banner).size!=(1280,640):errors.append('Social banner must be 1280x640')
inventory=json.loads((R/'docs/source-inventory.json').read_text(encoding='utf-8-sig'))
for row in inventory:
 # Inventory records Git object bytes, which can differ from checkout CRLF bytes.
 data=subprocess.check_output(['git','show',f'HEAD:{row["path"]}'],cwd=R)
 if len(data)!=row['size'] or hashlib.sha256(data).hexdigest()!=row['sha256']:errors.append('Source inventory mismatch: '+row['path'])
 changed=subprocess.run(['git','diff','--quiet','HEAD','--',row['path']],cwd=R).returncode
 if changed:errors.append('Inventoried source modified: '+row['path'])
result={'passed':not errors,'documents':documents,'relativeLinks':links,'inventoryFiles':len(inventory),'errors':errors}
print(json.dumps(result,indent=2));sys.exit(bool(errors))
