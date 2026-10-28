"""Read-only source checks; report file names, never matched secret values."""
import hashlib,json,re,subprocess,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1]
findings=[];count=0
bad={'.gguf','.safetensors','.onnx','.sqlite','.sqlite3','.db','.exe','.dll','.pfx','.p12','.pem','.key'}
tokens=re.compile(r'(?:gh[pousr]_[A-Za-z0-9]{25,}|github_pat_[A-Za-z0-9_]{30,}|sk_live_[A-Za-z0-9]{16,}|re_[A-Za-z0-9]{24,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')
public = subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=R).decode('utf-8').split('\0')
for folder in (public,):
 for relpath in folder:
  if not relpath:continue
  p=R/relpath
  if not p.is_file() or '__pycache__' in p.parts:continue
  count+=1;rel=p.relative_to(R).as_posix()
  if p.suffix.lower() in bad or p.name.startswith('.env') or p.name in {'config.json','cookies.json','credentials.json'}:findings.append({'file':rel,'check':'private or binary payload'})
  if p.stat().st_size>45_000_000:findings.append({'file':rel,'check':'oversized source asset'})
  if p.suffix.lower() in {'.py','.json','.txt','.md','.js','.cjs','.html','.yml','.yaml','.ps1','.bat','.css'}:
   text=p.read_text(encoding='utf-8-sig')
   if tokens.search(text):findings.append({'file':rel,'check':'possible embedded credential; manual review required'})
   if p.suffix=='.py':
    try:compile(text,str(p),'exec')
    except SyntaxError as ex:findings.append({'file':rel,'check':'Python syntax','line':ex.lineno})
  if p.suffix in ('.js','.cjs'):
   c=subprocess.run(['node','--check',str(p)],capture_output=True,text=True)
   if c.returncode:findings.append({'file':rel,'check':'JavaScript syntax'})
result={'passed':not findings,'filesChecked':count,'findings':findings,'scope':'Git tracked and nonignored candidate files including documentation and workflow metadata; heuristic credential scan, not a guarantee of absence.'}
(R/'release-check.json').write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(result,indent=2));sys.exit(0 if not findings else 1)
