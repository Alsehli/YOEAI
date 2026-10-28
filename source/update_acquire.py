"""Bounded acquisition. Downloaded code is data, never a host command."""
import hashlib,json,re,threading,time,uuid,urllib.request,urllib.parse
from pathlib import Path
from update_manager import atom,reject_link
HOSTS={'raw.githubusercontent.com'}
MAX=8*1024*1024
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args):raise ValueError('Redirect blocked; supply the exact approved source URL.')
def check_url(url):
 u=urllib.parse.urlsplit(url)
 if u.scheme!='https' or u.hostname not in HOSTS or u.port not in (None,443) or u.username or u.password or u.query or u.fragment:raise ValueError('Only direct HTTPS raw.githubusercontent.com source URLs are supported.')
 if not re.fullmatch(r'/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/[0-9a-f]{40}/[^?#]+',u.path) or '..' in urllib.parse.unquote(u.path).split('/'):raise ValueError('Pin the GitHub URL to an exact 40-character commit, not a mutable branch.')
 return u

def fetch(url):
 check_url(url)
 with urllib.request.build_opener(NoRedirect).open(urllib.request.Request(url,headers={'User-Agent':'YOEAI-Reviewed-Acquisition/1.0'}),timeout=20) as r:
  if r.headers.get('Content-Encoding','identity')!='identity':raise ValueError('Compressed transfer is not accepted.')
  data=r.read(MAX+1)
  if len(data)>MAX:raise ValueError('Download exceeds 8 MiB limit.')
  return data
class Acquisition:
 def __init__(self,m):self.m=m;self.base=m.home/'Acquisitions';self.base.mkdir(exist_ok=True);self.lock=threading.Lock()
 def record(self,id):
  if not re.fullmatch('[0-9a-f]{32}',str(id)):raise ValueError('Invalid acquisition ID.')
  p=self.base/id;reject_link(p)
  try:return p,json.loads((p/'record.json').read_text(encoding='utf-8'))
  except FileNotFoundError:raise ValueError('Acquisition not found.')
 def save(self,p,r):atom(p/'record.json',json.dumps(r,indent=2).encode())
 def list(self):return [json.loads(p.read_text(encoding='utf-8')) for p in sorted(self.base.glob('*/record.json'),reverse=True)][:50]
 def download(self,b):
  if b.get('approve') is not True:raise ValueError('Approve contacting these exact public URLs first.')
  u=check_url(b.get('url',''));lu=check_url(b.get('licenseUrl',''))
  if u.path.split('/')[:4]!=lu.path.split('/')[:4]:raise ValueError('License must come from the same repository and commit.')
  suffix=Path(u.path).suffix.lower();kind='font' if suffix=='.ttf' else 'source'
  if suffix not in {'.ttf','.py','.js','.css','.html','.json','.md','.txt'}:raise ValueError('Only TrueType fonts and source text may be acquired; no installers, archives or executables.')
  license=fetch(b['licenseUrl']).decode('utf-8-sig')
  if not any(x in license for x in ['SIL OPEN FONT LICENSE','MIT License','Apache License','Redistribution and use in source and binary forms']):raise ValueError('Recognized permissive license text required; this is not a legal compatibility determination.')
  data=fetch(b['url']);expected=str(b.get('sha256','')).lower()
  if not re.fullmatch('[0-9a-f]{64}',expected) or hashlib.sha256(data).hexdigest()!=expected:raise ValueError('An independently checked SHA-256 is required and must match.')
  if kind=='font':
   if not data.startswith(b'\x00\x01\x00\x00'):raise ValueError('Only standalone TrueType fonts accepted.')
   count=int.from_bytes(data[4:6],'big')
   if not 1<=count<=256 or len(data)<12+16*count:raise ValueError('Invalid font directory.')
   for i in range(count):
    entry=data[12+i*16:28+i*16];offset=int.from_bytes(entry[8:12],'big');size=int.from_bytes(entry[12:16],'big')
    if offset+size>len(data):raise ValueError('Invalid font table bounds.')
  else:
   text=data.decode('utf-8-sig')
   if '\x00' in text:raise ValueError('Binary source rejected.')
  id=uuid.uuid4().hex;p=self.base/id;p.mkdir();atom(p/'payload',data);atom(p/'LICENSE.txt',license.encode())
  r={'id':id,'kind':kind,'url':b['url'],'licenseUrl':b['licenseUrl'],'sha256':expected,'size':len(data),'status':'STAGED','created':time.time(),'license':license,'note':'License recognition does not prove compatibility. Review attribution and product obligations. Source is never executed automatically.'};self.save(p,r);self.m.audit('acquire','Staged '+id+' '+expected);return r
 def install(self,b):
  import update_native
  with self.lock:
   p,r=self.record(b.get('id'));data=(p/'payload').read_bytes()
   if r['kind']!='font':raise ValueError('Source remains staged. Prepare a reviewed UI patch and use isolated testing and deployment; dependencies require a trusted release.')
   if r['status']!='STAGED' or b.get('approve') is not True or b.get('digest')!=r['sha256'] or hashlib.sha256(data).hexdigest()!=r['sha256']:raise ValueError('Approve the exact unmodified staged font.')
   record={'operation':'Install app-private font (available after restart; current typography unchanged)','digest':r['sha256'],'files':[{'path':'assets/fonts/acquired-'+r['sha256']+'.ttf','diff':r['url']+'\nLicense:\n'+r['license']}]}
   if not update_native.approve(record,threading.Event()):raise ValueError('Native approval declined.')
   target=self.m.root/record['files'][0]['path'];reject_link(target)
   if target.exists():raise ValueError('Font already exists; no overwrite allowed.')
   atom(target,data);atom(target.with_suffix('.license.txt'),r['license'].encode());r['status']='INSTALLED';r['target']=str(target);self.save(p,r);self.m.audit('acquire','Installed font '+r['id']);return r
 def rollback(self,b):
  import update_native
  with self.lock:
   p,r=self.record(b.get('id'));target=self.m.root/'assets/fonts'/('acquired-'+r['sha256']+'.ttf');reject_link(target)
   if b.get('approve') is not True or r['status']!='INSTALLED' or hashlib.sha256(target.read_bytes()).hexdigest()!=r['sha256']:raise ValueError('Only the unchanged acquired font can be removed.')
   if not update_native.approve({'operation':'Remove this acquired font; restart to unload','digest':r['sha256'],'files':[{'path':target.name,'diff':r['url']}]},threading.Event()):raise ValueError('Native approval declined.')
   target.unlink();target.with_suffix('.license.txt').unlink(missing_ok=True);r['status']='ROLLED_BACK';self.save(p,r);self.m.audit('acquire','Removed font '+r['id']);return r
