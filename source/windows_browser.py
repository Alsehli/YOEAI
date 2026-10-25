"""Browser adapter: separate local profile, exact allowed origins, no personal tabs."""
import contextlib,json,os,re,socket,subprocess,time,urllib.request,uuid
from pathlib import Path
from urllib.parse import urljoin,urlsplit
from windows_policy import origin,scoped_path,SENSITIVE_UI,redact

def profile_matches(arguments,profile):
 expected=os.path.normcase(os.path.abspath(profile))
 return any(a.startswith('--user-data-dir=') and os.path.normcase(os.path.abspath(a.split('=',1)[1]))==expected for a in arguments)

def session(context,scope,app=None):
 from windows_tools import app_paths
 import psutil
 home=Path(context['home'])/'WindowsBrowser';home.mkdir(parents=True,exist_ok=True);state=home/'session.json'
 if state.exists():
  s=json.loads(state.read_text())
  with contextlib.suppress(psutil.Error,OSError,ValueError):
   p=psutil.Process(s['pid'])
   if p.create_time()==s['created'] and profile_matches(p.cmdline(),s['profile']) and s['app'] in scope['apps'] and (not app or app==s['app']):return s
 if not app or app not in ['chrome','edge'] or app not in scope['apps']:raise ValueError('Open an approved Chrome or Edge agent session first.')
 entry=app_paths()[app]
 if not entry['installed']:raise ValueError('This browser is not installed.')
 with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
 profile=home/('session-'+uuid.uuid4().hex);profile.mkdir()
 args=[entry['path'],'--user-data-dir='+str(profile),'--remote-debugging-port='+str(port),'--remote-debugging-address=127.0.0.1','--no-first-run','--no-default-browser-check','about:blank']
 process=subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,shell=False)
 s={'pid':process.pid,'created':psutil.Process(process.pid).create_time(),'port':port,'profile':str(profile),'app':app}
 state.write_text(json.dumps(s))
 for _ in range(40):
  try:
   with urllib.request.urlopen('http://127.0.0.1:'+str(port)+'/json/version',timeout=.5) as r:json.load(r)
   return s
  except OSError:time.sleep(.15)
 raise ValueError('The isolated browser did not become ready. No personal profile was used.')

class ScopedRedirect(urllib.request.HTTPRedirectHandler):
 def __init__(self,allowed):self.allowed=allowed
 def redirect_request(self,req,fp,code,msg,headers,newurl):
  if origin(newurl) not in self.allowed:raise ValueError('Download redirect escaped the approved origins.')
  return super().redirect_request(req,fp,code,msg,headers,newurl)

def execute_browser(name,p,scope,context):
 if name=='browser_download':
  target=scoped_path(scope['folder'],p['destination'],False)
  if target.exists():raise ValueError('Download destination exists. Overwriting is blocked.')
  opener=urllib.request.build_opener(ScopedRedirect(scope['origins']));total=0
  with opener.open(urllib.request.Request(p['url'],headers={'User-Agent':'YOEAI-Windows-Agent/2.0'}),timeout=15) as response,target.open('xb') as out:
   if origin(response.url) not in scope['origins']:raise ValueError('Unapproved download origin.')
   while chunk:=response.read(65536):
    total+=len(chunk)
    if total>25_000_000:raise ValueError('Download exceeded 25 MB. Partial file retained for your review.')
    out.write(chunk)
  return {'saved':str(target),'bytes':total,'verified':target.stat().st_size==total,'cookies':'No browser cookies or private credentials sent'}
 from playwright.sync_api import sync_playwright
 s=session(context,scope,p.get('app') if name=='browser_open' else None)
 with sync_playwright() as pw:
  browser=pw.chromium.connect_over_cdp('http://127.0.0.1:'+str(s['port']),timeout=8000)
  ctx=browser.contexts[0];pages=ctx.pages;page=pages[-1] if pages else ctx.new_page();page.set_default_timeout(6000)
  def route(request):
   url=request.request.url
   if url.startswith(('data:','blob:')) or url=='about:blank':request.continue_();return
   try:approved=origin(url) in scope['origins']
   except ValueError:approved=False
   if approved:request.continue_()
   else:request.abort()
  ctx.route('**/*',route)
  try:
   if name=='browser_open':
    page.goto(p['url'],wait_until='domcontentloaded',timeout=15000)
    if origin(page.url) not in scope['origins']:raise ValueError('Navigation escaped the approved origins.')
    return {'url':page.url,'title':redact(page.title()),'verified':True,'profile':'Isolated agent profile; not your personal browser session'}
   if origin(page.url) not in scope['origins']:raise ValueError('The current browser origin is not approved for this task.')
   if name=='browser_read':
    text=page.locator('body').inner_text(timeout=6000)
    return {'url':page.url,'title':redact(page.title()),'text':redact(text[:10000]),'truncated':len(text)>10000,'untrusted':True,'verified':True}
   if name=='browser_fill':
    label=p.get('label','')
    if SENSITIVE_UI.search(label):raise ValueError('Sensitive form fields require manual user takeover.')
    field=page.get_by_label(label,exact=True)
    if field.count()!=1:raise ValueError('Field label is missing or ambiguous; nothing was filled.')
    kind=field.get_attribute('type') or '';autocomplete=field.get_attribute('autocomplete') or ''
    if kind.lower() in ['password','file','hidden','submit'] or re.search(r'password|credit|cc-|one-time|transaction',autocomplete,re.I):raise ValueError('Credential, payment, hidden and file fields require manual takeover.')
    field.fill(p.get('text',''))
    return {'url':page.url,'field':label,'verified':field.input_value()==p.get('text',''),'notice':'No form was submitted. Sensitive submissions require user takeover.'}
   if name=='browser_link':
    link=page.get_by_role('link',name=p.get('label',''),exact=True)
    if link.count()!=1 or SENSITIVE_UI.search(p.get('label','')):raise ValueError('This link is ambiguous or consequential. Perform it yourself.')
    url=urljoin(page.url,link.get_attribute('href') or '')
    if origin(url) not in scope['origins']:raise ValueError('Link origin is not approved.')
    # Navigate to an observed URL; do not execute arbitrary page onclick handlers.
    page.goto(url,wait_until='domcontentloaded',timeout=15000)
    return {'url':page.url,'verified':origin(page.url) in scope['origins']}
   raise ValueError('Unsupported browser operation. Forms, messages, purchases and CAPTCHAs require human takeover.')
  finally:
   with contextlib.suppress(Exception):ctx.unroute('**/*',route)
   # Disconnect from CDP without closing the user's visible agent browser.
