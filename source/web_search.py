# SPDX-License-Identifier: GPL-3.0-only
"""Explicit same-origin native search. No browser, credentials, or model changes."""
import json,threading,time,ipaddress
from urllib.parse import urlsplit
from html.parser import HTMLParser
from datetime import datetime,timezone
LOCK=threading.Lock();LAST=0.0;CACHE={}
class Plain(HTMLParser):
 def __init__(self):super().__init__();self.parts=[]
 def handle_data(self,data):self.parts.append(data)
def plain(value,limit):
 p=Plain();p.feed(str(value));return ' '.join(' '.join(p.parts).split())[:limit]
def safe_url(value):
 if not isinstance(value,str) or len(value)>2048:return None
 try:
  u=urlsplit(value)
  if u.scheme not in ('https','http') or not u.hostname or u.username or u.password:return None
  host=u.hostname.lower()
  if host=='localhost' or host.endswith(('.local','.localhost','.internal')) or '.' not in host:return None
  try:
   if not ipaddress.ip_address(host).is_global:return None
  except ValueError:pass
  return value
 except ValueError:return None
def normalize(rows):
 out=[];seen=set()
 for row in rows:
  if not isinstance(row,dict):continue
  url=safe_url(row.get('href'));title=plain(row.get('title',''),180)
  if not url or not title or url in seen:continue
  seen.add(url);out.append({'title':title,'url':url,'snippet':plain(row.get('body',''),850)})
  if len(out)==4:break
 return out
def clean_query(query):
 import re
 original=query.strip();value=original
 for _ in range(3):
  value=re.sub(r'^(?:(?:please|can you|could you)\s+)?(?:search(?:\s+(?:the\s+)?(?:internet|net|web))?(?:\s+for)?|look\s+(?:for|up)|find(?:\s+me)?|show(?:\s+me)?|get(?:\s+me)?)\s+','',value,flags=re.I)
  value=re.sub(r'^(?:some\s+)?(?:photos?|pictures?|images?)\s+(?:of|about)\s+','',value,flags=re.I)
  value=re.sub(r'^(?:من فضلك\s+)?(?:ابحث(?:\s+لي)?(?:\s+عن)?|اعرض(?:\s+لي)?|أرني|ارني|دور(?:\s+على)?)\s+','',value)
  value=re.sub(r'^صور(?:\s+عن)?\s+','',value)
 return value.strip() or original

def search(query,home=None):
 global LAST
 if not isinstance(query,str) or not 1<=len(query.strip())<=500:raise ValueError('Use a search question between 1 and 500 characters.')
 query=query.strip()
 if not LOCK.acquire(blocking=False):raise RuntimeError('A search is already running. Try again shortly.')
 try:
  from searx_search import search as searx_search,options
  ttl=60 if options(query)['time_range'] else 300
  if query in CACHE and time.monotonic()-CACHE[query][0]<ttl and CACHE[query][1].get('presentationVersion')==4:return dict(CACHE[query][1],fromCache=True)
  delay=1-(time.monotonic()-LAST)
  if delay>0:time.sleep(delay)
  LAST=time.monotonic();started=time.perf_counter();term=clean_query(query)
  from concurrent.futures import ThreadPoolExecutor
  import re,web_photos
  wants_photos=bool(re.search(r'\b(photos?|pictures?|images?)\b|صور|صورة',query,re.I))
  def pictures():
   try:return web_photos.search(term,home) if home and wants_photos else []
   except Exception:return []
  with ThreadPoolExecutor(max_workers=2) as pool:
   text_job=pool.submit(searx_search,term);image_job=pool.submit(pictures)
   evidence=text_job.result();photos=image_job.result()
  results=evidence['results']
  response={'provider':'SearXNG','query':query,'searchQuery':term,'results':results,'photos':photos,'presentationVersion':4,'searchedAt':datetime.now(timezone.utc).isoformat(),'seconds':round(time.perf_counter()-started,2),**{k:v for k,v in evidence.items() if k!='results'}}
  if len(CACHE)>=8:CACHE.pop(next(iter(CACHE)))
  CACHE[query]=(time.monotonic(),response)
  return response
 finally:LOCK.release()

def route(handler,post=False,home=None):
 if handler.path.startswith('/web-image/'):
  if post:return False
  from web_photos import route as photo_route
  return photo_route(handler,home)
 if handler.path!='/web-search':return False
 reply=getattr(handler,'reply',None) or handler.json
 if not post:reply(405,{'error':'Use the Search web switch in the local chat.'});return True
 if not handler.allowed() or handler.headers.get('Origin')!='http://'+handler.headers.get('Host',''):
  reply(403,{'error':'Only the local YOEAI chat can start a search.'});return True
 try:
  if handler.headers.get('Transfer-Encoding'):raise ValueError('Unsupported transfer encoding.')
  length=int(handler.headers.get('Content-Length','0'))
  if not 0<length<=4096:raise ValueError('Invalid search request size.')
  handler.connection.settimeout(15);body=json.loads(handler.rfile.read(length))
  if not isinstance(body,dict):raise ValueError('Invalid search request.')
  reply(200,search(body.get('query'),home))
 except (ValueError,TypeError):reply(400,{'error':'Use a search question between 1 and 500 characters.'})
 except Exception as error:reply(503,{'error':str(error) if isinstance(error,RuntimeError) else 'Web search is unavailable.'})
 return True

def diagnostic(path):
 from pathlib import Path
 from importlib.metadata import version
 import primp,lxml.etree,web_photos
 assert web_photos.allowed("https://upload.wikimedia.org/test.jpg")
 assert not web_photos.allowed("https://example.com/test.jpg")
 from ddgs.engines.duckduckgo import Duckduckgo
 engine=Duckduckgo(timeout=12,verify=True)
 assert normalize([{'href':'javascript:alert(1)','title':'bad'},{'href':'https://example.com','title':'Safe','body':'<b>Text</b>'}])==[{'title':'Safe','url':'https://example.com','snippet':'Text'}]
 result={'status':'PASS','ddgs':version('ddgs'),'primp':version('primp'),'lxml':version('lxml'),'scope':'Frozen dependency import and safe-result normalization; no internet request'}
 Path(path).write_text(json.dumps(result,indent=2));return result
