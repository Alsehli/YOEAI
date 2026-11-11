import sys,json,re,subprocess,py_compile
from pathlib import Path
from urllib.parse import urlsplit
root=Path(__file__).resolve().parents[1];rows=[]
for p in sorted(root.rglob('*.py')):
 if any(n in p.parts for n in ['.git','__pycache__']):continue
 try:py_compile.compile(str(p),doraise=True);row={'file':str(p.relative_to(root)),'kind':'python','status':'passed'}
 except Exception as e:row={'file':str(p.relative_to(root)),'kind':'python','status':'failed','error':str(e)}
 rows.append(row)
for p in sorted((root/'assets').rglob('*.js')):
 r=subprocess.run(['node','--check',str(p)],capture_output=True,text=True,encoding='utf8',timeout=30);rows.append({'file':str(p.relative_to(root)),'kind':'javascript','status':'passed' if not r.returncode else 'failed','error':r.stderr[-1200:] if r.returncode else None})
html=(root/'ui.html').read_text(encoding='utf8')
for address in re.findall(r'(?:src|href)=["\'](/assets/[^"\']+)',html):
 p=root/urlsplit(address).path.lstrip('/');rows.append({'file':address,'kind':'referenced-asset','status':'passed' if p.is_file() else 'failed'})
for i,code in enumerate(re.findall(r'<script>([\s\S]*?)</script>',html)):
 r=subprocess.run(['node','--check'],input=code,capture_output=True,text=True,encoding='utf8',timeout=30);rows.append({'file':'ui.html inline '+str(i),'kind':'inline-javascript','status':'passed' if not r.returncode else 'failed','error':r.stderr[-1000:] if r.returncode else None})
(root/'docs/system-audit/syntax-assets.json').write_text(json.dumps(rows,indent=2),encoding='utf8');print(json.dumps({'checks':len(rows),'failed':[r for r in rows if r['status']=='failed']}))
