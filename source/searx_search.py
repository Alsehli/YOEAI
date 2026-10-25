"""Private loopback SearXNG bridge, launched only for an explicit web search."""
import atexit,json,re,subprocess,threading,time,urllib.request,urllib.parse
from pathlib import Path
from datetime import datetime,timezone
from configuration import APP_DIR
START=threading.Lock();PROCESS=None
BASE='http://127.0.0.1:8888'
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):raise ValueError('Unexpected redirect from local search service.')
HTTP=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
def get(path,timeout=2):
 with HTTP.open(BASE+path,timeout=timeout) as r:
  data=r.read(4_000_001)
  if len(data)>4_000_000:raise RuntimeError('Search response is too large.')
  return json.loads(data)
def ready():
 try:return get('/config').get('instance_name')=='YOEAI Search'
 except Exception:return False
def stop():
 global PROCESS
 if PROCESS and PROCESS.poll() is None:PROCESS.terminate()
atexit.register(stop)
def ensure():
 global PROCESS
 if ready():return
 with START:
  if ready():return
  root=APP_DIR/'SearchRuntime';exe=root/'Python/python.exe';script=root/'serve.py'
  if not exe.is_file() or not script.is_file():raise RuntimeError('The local SearXNG component is missing. Install the updated YOEAI search package.')
  import socket
  with socket.socket() as sock:
   if sock.connect_ex(('127.0.0.1',8888))==0:raise RuntimeError('Port 8888 is used by another service. Close that service before searching.')
  if not PROCESS or PROCESS.poll() is not None:
   PROCESS=subprocess.Popen([str(exe),str(script)],cwd=root,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
  for _ in range(80):
   if ready():return
   if PROCESS.poll() is not None:raise RuntimeError('Local SearXNG could not start. Check the SearchRuntime installation.')
   time.sleep(.15)
  raise RuntimeError('Local SearXNG is still starting. Try searching again shortly.')
def options(query):
 lower=query.lower();current=datetime.now(timezone.utc).year
 years=[int(x) for x in re.findall(r'\b(?:19|20)\d{2}\b',lower)]
 historical=bool(years and max(years)<current)
 fresh=not historical and bool(re.search(r'\b(latest|recent|current|today|now|news|newest|this week|this month)\b|أحدث|احدث|اليوم|الآن|الان|الأخبار|اخبار|الجديد|الحالية',lower))
 period=('day' if re.search(r'\btoday\b|اليوم',lower) else 'month') if fresh else ''
 language='ar' if re.search('[\u0600-\u06ff]',query) else 'en'
 return {'language':language,'time_range':period,'categories':'general','safesearch':2,'format':'json'}
STOPWORDS=set('the a an of in on for to and or is are what how which please search net web internet latest recent current today now news me tell about find look show photos images pictures new newest update updates can you could would give information results احدث أحدث اخبار أخبار الأخبار الاخبار اليوم الآن الان عن في من ما هي هو اعرض ابحث لي صور صورة'.split())
def terms(text):
 out=set()
 for w in re.findall(r'[\w]+',text.lower()):
  if len(w)<2 or w in STOPWORDS:continue
  if w.startswith('ال') and len(w)>4:w=w[2:]
  if w.isascii() and len(w)>4 and w.endswith('s'):w=w[:-1]
  out.add(w)
 return out
def rank(rows,query):
 wanted=terms(query);scored=[];seen=set();now=datetime.now(timezone.utc)
 for index,row in enumerate(rows):
  if not isinstance(row,dict):continue
  from web_search import safe_url,plain
  link=safe_url(row.get('url'));title=plain(row.get('title',''),180)
  if not link or not title:continue
  u=urllib.parse.urlsplit(link);key=urllib.parse.urlunsplit((u.scheme,u.netloc,u.path.rstrip('/'),u.query,''))
  if key in seen:continue
  seen.add(key);snippet=plain(row.get('content',''),1300);overlap=len(wanted & terms(title+' '+snippet))/max(1,len(wanted))
  if wanted and overlap==0:continue
  date=row.get('publishedDate');parsed=None
  if isinstance(date,str):
   try:parsed=datetime.fromisoformat(date.replace('Z','+00:00')).replace(tzinfo=timezone.utc) if not datetime.fromisoformat(date.replace('Z','+00:00')).tzinfo else datetime.fromisoformat(date.replace('Z','+00:00'))
   except ValueError:pass
  if parsed and parsed>now:date=None;parsed=None
  title_overlap=len(wanted & terms(title+' '+u.path))/max(1,len(wanted))
  score=overlap*5+title_overlap*3+1/(index+1)+min(3,len(row.get('engines',[])))*.15
  if 'release' in terms(query) and '/releases' in u.path:score+=1.5
  if 'download' in terms(query) and '/download' in u.path:score+=1
  if 'release' in terms(query) and u.hostname=='github.com':score+=.8
  if options(query)['time_range'] and parsed:score+=max(0,.3*(1-(now-parsed).days/31))
  item={'title':title,'url':link,'snippet':snippet,'date':date if parsed else None,'engines':[str(x)[:40] for x in row.get('engines',[])[:8]],'relevance':round(overlap,3)}
  scored.append((score,item))
 domains={};out=[]
 for _,item in sorted(scored,key=lambda x:-x[0]):
  host=urllib.parse.urlsplit(item['url']).hostname
  if domains.get(host,0)>=2:continue
  domains[host]=domains.get(host,0)+1;out.append(item)
  if len(out)==8:break
 return out
def search(query):
 ensure();params=options(query)|{'q':query,'pageno':1}
 try:data=get('/search?'+urllib.parse.urlencode(params),timeout=18)
 except Exception as ex:raise RuntimeError('SearXNG could not complete the search. Check your internet connection and try again.') from ex
 if not isinstance(data,dict) or not isinstance(data.get('results'),list):raise RuntimeError('SearXNG returned an invalid response.')
 results=rank(data['results'],query)
 broadened=False
 # Release/download landing pages are often undated and excluded by date filters.
 # One additional ordinary query can recover them; it never retries a blocked engine directly.
 resource_query=bool(terms(query)&{'release','download','documentation'})
 primary=any(urllib.parse.urlsplit(x['url']).hostname in {'github.com','gitlab.com','sourceforge.net'} for x in results)
 if params['time_range'] and resource_query and not primary:
  broad=params.copy();broad.pop('time_range',None)
  broad['q']=re.sub(r'\b(latest|current|recent|newest|today)\b','',query,flags=re.I).strip()+' official'
  try:
   extra=get('/search?'+urllib.parse.urlencode(broad),timeout=12)
   if isinstance(extra,dict) and isinstance(extra.get('results'),list):
    results=rank(data['results']+extra['results'],query);broadened=True
    data['unresponsive_engines']=(data.get('unresponsive_engines',[])+extra.get('unresponsive_engines',[]))[:12]
  except Exception:pass
 if not results:raise RuntimeError('No relevant results were returned. Try a more specific subject or date; YOEAI has not verified an answer.')
 engines=sorted({e for row in results for e in row['engines']})
 return {'results':results,'engines':engines,'timeRange':params['time_range'] or None,'language':params['language'],'unavailableEngines':data.get('unresponsive_engines',[])[:12],'broadenedSearch':broadened,'warning':'Additional undated official-resource search results are included; do not infer publication dates or a current version from retrieval time.' if broadened else ''}
