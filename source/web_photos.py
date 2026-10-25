# SPDX-License-Identifier: GPL-3.0-only
"""Bounded Wikimedia photo retrieval and same-origin cached thumbnails."""
import hashlib,json,re,threading,urllib.request,urllib.parse,uuid
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
HOSTS={'commons.wikimedia.org','upload.wikimedia.org','thumb.wikimedia.org'}
AGENT='YOEAI/2.0 (https://yoeai.online; hello@yoeai.online)'
WRITE_LOCK=threading.Lock()
class Text(HTMLParser):
 def __init__(self):super().__init__();self.parts=[]
 def handle_data(self,value):self.parts.append(value)
def plain(value,limit=1000):
 p=Text();p.feed(str(value));return ' '.join(' '.join(p.parts).split())[:limit]
def allowed(url,hosts=HOSTS):
 try:
  u=urllib.parse.urlsplit(url)
  return u.scheme=='https' and u.hostname in hosts and not u.username and not u.password and u.port in (None,443)
 except (ValueError,TypeError):return False
class Redirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl):
  if not allowed(newurl):raise ValueError('Unexpected photo redirect.')
  return super().redirect_request(req,fp,code,msg,headers,newurl)
HTTP=urllib.request.build_opener(urllib.request.ProxyHandler({}),Redirect())
def fetch(url,limit):
 if not allowed(url):raise ValueError('Unsupported photo host.')
 with HTTP.open(urllib.request.Request(url,headers={'User-Agent':AGENT,'Accept':'application/json,image/jpeg,image/png'}),timeout=8) as r:
  if not allowed(r.url):raise ValueError('Unexpected photo destination.')
  raw=r.read(limit+1)
  if len(raw)>limit:raise ValueError('Photo response is too large.')
  return raw,r.headers.get_content_type()
def mime(raw):
 if raw.startswith(b'\xff\xd8\xff'):return 'image/jpeg'
 if raw.startswith(b'\x89PNG\r\n\x1a\n'):return 'image/png'
 return None
def metadata(data):
 out=[]
 for page in sorted(data.get('query',{}).get('pages',{}).values(),key=lambda p:p.get('index',999)):
  info=(page.get('imageinfo') or [{}])[0];m=info.get('extmetadata',{});get=lambda k:plain(m.get(k,{}).get('value',''),1100)
  license=get('LicenseShortName');license_url=get('LicenseUrl').replace('http://','https://',1);artist=get('Artist');title=plain(page.get('title','').removeprefix('File:'),250)
  u=urllib.parse.urlsplit(license_url)
  permitted=u.hostname=='creativecommons.org' and (u.path.startswith(('/licenses/by/','/licenses/by-sa/','/publicdomain/zero/','/publicdomain/mark/')))
  public=license.lower() in ['public domain','cc0']
  if not (permitted or public) or get('Restrictions') or len(artist)>500 or (not artist and not public):continue
  image=info.get('thumburl');url=info.get('descriptionurl','')
  if info.get('mime') not in ['image/jpeg','image/png'] or not allowed(image,{'upload.wikimedia.org','thumb.wikimedia.org'}) or not allowed(url,{'commons.wikimedia.org'}):continue
  image=urllib.parse.urlunsplit(urllib.parse.urlsplit(image)._replace(query='',fragment=''))
  out.append({'title':title,'author':artist or 'Wikimedia Commons contributor','license':license,'licenseUrl':license_url if permitted else '', 'pageUrl':url,'remoteImage':image,'snippet':plain(get('ImageDescription'),650)})
  if len(out)==2:break
 return out
def store(photo,home):
 root=Path(home)/'WebPhotoCache';root.mkdir(parents=True,exist_ok=True);key=hashlib.sha256(photo['remoteImage'].encode()).hexdigest();dest=root/(key+'.img')
 if not dest.exists():
  raw,_=fetch(photo['remoteImage'],2_000_000)
  if not mime(raw):raise ValueError('Only JPEG and PNG photos are supported.')
  with WRITE_LOCK:
   if sum(p.stat().st_size for p in root.glob('*.img'))+len(raw)>128_000_000:raise ValueError('Photo cache limit reached.')
   temp=root/(key+'.'+uuid.uuid4().hex+'.tmp');temp.write_bytes(raw);temp.replace(dest)
 if not mime(dest.read_bytes()[:16]):raise ValueError('Cached photo is invalid.')
 return {k:v for k,v in photo.items() if k!='remoteImage'}|{'image':'/web-image/'+key}
def search(query,home):
 params={'action':'query','generator':'search','gsrsearch':query,'gsrnamespace':'6','gsrlimit':'5','prop':'imageinfo','iiprop':'url|mime|extmetadata','iiurlwidth':'480','format':'json'}
 raw,_=fetch('https://commons.wikimedia.org/w/api.php?'+urllib.parse.urlencode(params),1_500_000);data=json.loads(raw);photos=metadata(data)
 def one(photo):
  try:return store(photo,home)
  except Exception:return None
 with ThreadPoolExecutor(max_workers=2) as pool:return [p for p in pool.map(one,photos) if p]
def route(handler,home):
 if not handler.path.startswith('/web-image/'):return False
 reply=getattr(handler,'reply',None) or handler.json
 if not handler.allowed() or handler.headers.get('Sec-Fetch-Site')=='cross-site':reply(403,{'error':'Only the local chat can display these photos.'});return True
 key=handler.path.removeprefix('/web-image/')
 if not re.fullmatch('[0-9a-f]{64}',key):reply(404,{'error':'Photo not found.'});return True
 p=Path(home)/'WebPhotoCache'/(key+'.img')
 if not p.is_file() or p.stat().st_size>2_000_000:reply(404,{'error':'Photo is unavailable. Open its original link.'});return True
 raw=p.read_bytes();content_type=mime(raw)
 if not content_type:reply(404,{'error':'Invalid photo.'});return True
 handler.send_response(200);handler.send_header('Content-Type',content_type);handler.send_header('Content-Length',str(len(raw)));handler.send_header('X-Content-Type-Options','nosniff');handler.send_header('Cache-Control','private, max-age=3600');handler.end_headers();handler.wfile.write(raw);return True
