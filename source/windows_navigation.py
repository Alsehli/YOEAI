"""Fast path for explicit navigation/search only; scope still authorizes tools.

Never interprets page content or grants an origin, file root or credentials.
Complex/chained tasks remain with the selected model and one-use approvals.
"""
import re,time
from urllib.parse import urlsplit,urlencode
from windows_policy import origin,validate_action

def direct_navigation(text,scope):
 if not isinstance(text,str):return None
 value=text.strip()
 if re.search(r'\bthen\b|&&|;|\band\s+(?:delete|click|send|install|open|fill)\b',value,re.I):return None
 browser=next((a for a in scope['apps'] if a in ['edge','chrome']),None)
 if not browser:return None
 query=None;url=None
 m=re.fullmatch(r'(?:please\s+)?(?:search(?:\s+(Google|Bing|DuckDuckGo))?(?:\s+for)?|look\s+up|ابحث\s+عن|بحث\s+عن)\s+(.+)',value,re.I)
 if m:
  query=m[2].strip();query=re.sub(r'\s+in\s+(?:google\s+)?(?:chrome|chrom|chorme|edge|the browser)\.?$','',query,flags=re.I)
  query=re.sub(r'^the\s+word\s+','',query,flags=re.I)
  requested={'google':'https://www.google.com','bing':'https://www.bing.com','duckduckgo':'https://duckduckgo.com'}.get((m[1] or '').lower())
  site=requested or next((o for o in scope['origins'] if o in ['https://www.google.com','https://www.bing.com','https://duckduckgo.com']),None)
  if not site or site not in scope['origins'] or not query:return None
  url=site+('/?' if site=='https://duckduckgo.com' else '/search?')+urlencode({'q':query})
 else:
  m=re.fullmatch(r'(?:please\s+)?(?:open|opne|visit|go to|افتح)\s+(https?://[^\s<>"\']+)',value,re.I)
  if m:url=m[1].rstrip('.,;!)')
 if not url:return None
 try:
  if origin(url) not in scope['origins']:return None
  return validate_action({'tool':'browser_open','params':{'app':browser,'url':url},'why':'Open the website or search explicitly requested by you.','expected':'Verify the final URL and page title in the visible agent browser.'},scope)
 except ValueError:return None

def prepare(e,t):
 w=t['windows'];action=direct_navigation(t['objective'],w['scope'])
 if action is None:return False
 w.update(plan=[action],summary='Open the requested website/search',planned=True,started=time.time())
 t['plan']='1. Open '+action['params']['url'];t['stream']=''
 from windows_agent import pending
 pending(e,t,'plan',message='Review the explicit navigation and its existing website scope.');return True
