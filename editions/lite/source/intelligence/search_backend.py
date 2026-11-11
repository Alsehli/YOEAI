"""Bundled SearXNG lifecycle and HTTPS-only managed search configuration."""
import atexit,json,os,secrets,socket,subprocess,threading,time,urllib.request
from pathlib import Path
from urllib.parse import urlencode,urlsplit
from .automatic_web import Cancelled,public_query

class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):raise ValueError('Private search redirects are blocked.')

DEFAULTS={'enabled':True,'backend':'bundled-searxng','managedHttpsEndpoint':None,'engines':['brave','duckduckgo','wikipedia'],'safeSearch':2,'requestTimeoutSeconds':15,'startupTimeoutSeconds':30,'idleShutdownSeconds':300,'maxResults':8}
class Backend:
 def __init__(self,root,home):
  self.root=Path(root);self.home=Path(home)/'Search';self.lock=threading.RLock();self.process=None;self.port=None;self.token=None;self.log=None;self.timer=None;self.active=0
  path=self.root/'Settings/web-research.json';self.settings=dict(DEFAULTS)
  if path.is_file():self.settings.update(json.loads(path.read_text(encoding='utf-8-sig')))
  atexit.register(self.close,True)
 def describe(self):
  missing=[str(p.relative_to(self.root)) for p in (self.root/'SearchRuntime/Python/python.exe',self.root/'SearchRuntime/Runtime/searx/webapp.py',self.root/'SearchRuntime/settings.yml') if not p.is_file()]
  return {'configured':bool(self.settings.get('enabled')),'backend':self.settings.get('backend'),'bundledLocalService':self.settings.get('backend')=='bundled-searxng','internetRequired':True,'localInferenceOnly':True,'startupSearches':False,'missingComponents':missing,'verified':False}
 def _get(self,url,headers,cancel,timeout):
  outcome={};response_holder={}
  def receive():
   try:
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect());request=urllib.request.Request(url,headers=headers)
    with opener.open(request,timeout=timeout) as response:
     response_holder['response']=response;raw=response.read(300001)
     if len(raw)>300000:raise ValueError('Search response exceeded its size limit.')
     outcome['value']=json.loads(raw)
   except Exception as error:outcome['error']=error
  worker=threading.Thread(target=receive,daemon=True);worker.start();deadline=time.monotonic()+timeout+1
  while worker.is_alive():
   if cancel.wait(.05) or time.monotonic()>deadline:
    if response_holder.get('response'):response_holder['response'].close()
    if cancel.is_set():raise Cancelled('Research stopped')
    raise TimeoutError('Search response timed out.')
  if 'error' in outcome:raise RuntimeError('Live search could not be completed. Local chat remains available.') from outcome['error']
  return outcome['value']
 def _ensure(self,cancel):
  if self.process and self.process.poll() is None:return
  for p in (self.root/'SearchRuntime/Python/python.exe',self.root/'SearchRuntime/Runtime/searx/webapp.py',self.root/'SearchRuntime/settings.yml'):
   if not p.is_file():raise ValueError('Bundled research component is missing: '+str(p.relative_to(self.root)))
  self.home.mkdir(parents=True,exist_ok=True)
  with socket.socket() as probe:probe.bind(('127.0.0.1',0));self.port=probe.getsockname()[1]
  self.token=secrets.token_urlsafe(32);self.log=(self.home/'backend.log').open('w',encoding='utf8')
  server=self.root/'Source/intelligence/search_server.py'
  if not server.is_file():server=Path(__file__).with_name('search_server.py')
  self.process=subprocess.Popen([str(self.root/'SearchRuntime/Python/python.exe'),str(server),'--root',str(self.root),'--home',str(self.home),'--port',str(self.port)],env=dict(os.environ,YOEAI_SEARCH_TOKEN=self.token,PYTHONNOUSERSITE='1'),stdin=subprocess.DEVNULL,stdout=self.log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
  deadline=time.monotonic()+max(5,min(60,int(self.settings['startupTimeoutSeconds'])))
  while time.monotonic()<deadline:
   if cancel.is_set():self.close();raise Cancelled('Research stopped')
   if self.process.poll() is not None:break
   try:
    value=self._get('http://127.0.0.1:'+str(self.port)+'/health',{'X-YOEAI-Search-Token':self.token},cancel,1)
    if value.get('service')=='YOEAI-private-searxng':return
   except Cancelled:raise
   except Exception:cancel.wait(.15)
  self.close();raise RuntimeError('The bundled search service could not start. Local chat remains available.')
 def search(self,query,language,cancel):
  query=public_query(query)
  if not self.settings.get('enabled'):raise ValueError('Live research is unavailable in this installation.')
  with self.lock:
   if self.timer:self.timer.cancel();self.timer=None
   backend=self.settings.get('backend')
   if backend=='bundled-searxng':
    self._ensure(cancel);base='http://127.0.0.1:'+str(self.port)+'/search';headers={'X-YOEAI-Search-Token':self.token}
   elif backend=='managed-https':
    base=self.settings.get('managedHttpsEndpoint') or '';p=urlsplit(base)
    if p.scheme!='https' or not p.hostname or p.username or p.password or p.query or p.fragment:raise ValueError('The managed HTTPS search endpoint has not been configured.')
    headers={}
   else:raise ValueError('Unsupported research backend; no unconfigured service is used.')
   self.active+=1
  try:
   params=urlencode({'q':query,'format':'json','language':language,'safesearch':2,'engines':','.join(self.settings['engines'])})
   if backend=='managed-https':
    from .public_reader import read_json
    value=read_json(base+'?'+params,cancel)
   else:value=self._get(base+'?'+params,headers,cancel,max(3,min(20,int(self.settings['requestTimeoutSeconds']))))
   if not isinstance(value,dict) or not isinstance(value.get('results'),list):raise ValueError('Search backend returned an unsupported response.')
   return value['results'][:min(12,int(self.settings['maxResults']))]
  finally:
   with self.lock:
    self.active-=1
    if not self.active:
     self.timer=threading.Timer(max(30,int(self.settings['idleShutdownSeconds'])),self.close);self.timer.daemon=True;self.timer.start()
 def close(self,force=False):
  with self.lock:
   if self.active and not force:return
   if self.timer:self.timer.cancel();self.timer=None
   if self.process:
    if self.process.poll() is None:
     self.process.terminate()
     try:self.process.wait(timeout=5)
     except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=5)
    self.process=None
   if self.log:self.log.close();self.log=None
