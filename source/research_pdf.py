"""Local, sanitized report printing through the desktop's existing Chromium engine."""
import html,json,threading,time
from html.parser import HTMLParser
from urllib.parse import urlsplit
from PySide6.QtCore import QObject,Signal,Slot,QUrl,QMarginsF,QTimer
from PySide6.QtGui import QPageLayout,QPageSize
from PySide6.QtWebEngineCore import QWebEnginePage,QWebEngineProfile,QWebEngineUrlRequestInterceptor

TAGS={'h1','h2','h3','h4','h5','h6','p','div','span','strong','b','em','i','ul','ol','li','pre','code','blockquote','table','thead','tbody','tfoot','tr','th','td','a','br','hr','img'}
BLOCK={'h1','h2','h3','h4','h5','h6','p','li','blockquote','table'}
SKIP={'script','style','iframe','object','embed','form','button','input','textarea','select','svg','math'}
FONTS={'inter.ttf','inter-italic.ttf','manrope.ttf','jetbrainsmono.ttf','noto-sans-arabic.ttf'}
BROKER=None;GATE=threading.Lock()

class CleanReport(HTMLParser):
 def __init__(self):super().__init__(convert_charrefs=True);self.parts=[];self.skip=0;self.table=0;self.columns=0;self.maximum=0;self.rows=0;self.text_size=0
 def handle_starttag(self,tag,attrs):
  if tag in SKIP:self.skip+=1;return
  if self.skip or tag not in TAGS:return
  attr={};raw=dict(attrs)
  if tag in BLOCK:attr['dir']='auto'
  if tag in ['pre','code']:attr['dir']='ltr'
  if tag=='a' and raw.get('href','').startswith(('https://','http://')):attr['href']=raw['href'][:2000]
  if tag=='img':
   import re
   if not re.fullmatch(r'data:image/png;base64,[A-Za-z0-9+/=]+',raw.get('src','')):return
   attr['src']=raw['src']
  if tag in ['td','th']:
   self.columns+=1
   for key in ['colspan','rowspan']:
    try:
     n=int(raw.get(key,'1'))
     if 1<n<=12:attr[key]=str(n)
    except ValueError:pass
  if tag=='table':self.table+=1
  if tag=='tr':self.columns=0;self.rows+=1
  if self.rows>1000:raise ValueError('Use up to 1,000 table rows per report.')
  self.parts.append('<'+tag+''.join(' '+k+'="'+html.escape(v,quote=True)+'"' for k,v in attr.items())+'>')
 def handle_endtag(self,tag):
  if tag in SKIP:
   if self.skip:self.skip-=1
   return
  if self.skip or tag not in TAGS:return
  if tag=='tr':self.maximum=max(self.maximum,self.columns)
  if tag not in ['br','hr','img']:self.parts.append('</'+tag+'>')
 def handle_data(self,data):
  if self.skip:return
  self.text_size+=len(data)
  if self.text_size>150000:raise ValueError('Use a report under 150,000 characters.')
  self.parts.append(html.escape(data))

def document(fragment,title,port):
 if not isinstance(fragment,str) or not fragment.strip() or len(fragment.encode('utf8'))>900000:raise ValueError('The printable report is empty or too large.')
 parser=CleanReport();parser.feed(fragment);parser.close()
 if not parser.text_size:raise ValueError('The report has no printable text.')
 base=f'http://127.0.0.1:{port}'
 css='''@font-face{font-family:Inter;src:url("BASE/assets/fonts/inter.ttf");font-weight:100 900}@font-face{font-family:Inter;src:url("BASE/assets/fonts/inter-italic.ttf");font-style:italic;font-weight:100 900}@font-face{font-family:Manrope;src:url("BASE/assets/fonts/manrope.ttf");font-weight:200 800}@font-face{font-family:Mono;src:url("BASE/assets/fonts/jetbrainsmono.ttf")}@font-face{font-family:Arabic;src:url("BASE/assets/fonts/noto-sans-arabic.ttf");font-weight:100 900}
*{box-sizing:border-box}body{font:11pt/1.65 Inter,Arabic,sans-serif;color:#172033;margin:0}h1,h2,h3,h4,h5,h6{font-family:Manrope,Arabic,Inter,sans-serif;line-height:1.4;break-after:avoid;color:#143362}h1{font-size:25pt}h2{font-size:19pt}h3{font-size:15pt}p{margin:0 0 10pt;orphans:3;widows:3}a{color:#215fc2;text-decoration:underline;overflow-wrap:anywhere}pre,code{font-family:Mono,Arabic,monospace;font-size:9pt}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f1f5fa;padding:10pt;border:1px solid #dce4f0}blockquote{border-inline-start:3pt solid #77a4ed;padding-inline-start:12pt;color:#475569}table{border-collapse:collapse;width:100%;table-layout:fixed;font-size:9pt;line-height:1.5;margin:12pt 0 18pt}thead{display:table-header-group}tfoot{display:table-footer-group}tr{break-inside:avoid}th,td{border:0.6pt solid #b8c7db;padding:6pt;vertical-align:top;white-space:normal;overflow-wrap:anywhere}th{background:#e9f0fb;font-weight:700;color:#143362}tbody tr:nth-child(even){background:#f7f9fc}ul,ol{padding-inline-start:22pt}li{margin:0 0 5pt}hr{border:0;border-top:1px solid #cbd5e1;margin:16pt 0}'''.replace('BASE',base)
 css+='img{max-width:100%;height:auto;break-inside:avoid}'
 page='<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; font-src '+base+'; img-src data:; script-src \'none\'; base-uri \'none\'"><title>'+html.escape(str(title)[:160])+'</title><style>'+css+'</style></head><body>'+''.join(parser.parts)+'</body></html>'
 return page,parser.maximum>5

class FontsOnly(QWebEngineUrlRequestInterceptor):
 def __init__(self,port,parent):super().__init__(parent);self.port=port
 def interceptRequest(self,info):
  u=info.requestUrl();allowed=u.scheme() in ['data','about'] or (u.scheme()=='http' and u.host()=='127.0.0.1' and u.port()==self.port and u.path().startswith('/assets/fonts/') and u.path().rsplit('/',1)[-1] in FONTS)
  if not allowed:info.block(True)

class ReportPrinter(QObject):
 requested=Signal(object)
 def __init__(self,port,parent):
  super().__init__(parent);self.port=port;self.jobs={};self.profile=QWebEngineProfile(self);self.interceptor=FontsOnly(port,self.profile);self.profile.setUrlRequestInterceptor(self.interceptor);self.requested.connect(self.render)
 @Slot(object)
 def render(self,job):
  if job['done'].is_set():return
  try:
   content,wide=document(job['html'],job['title'],self.port);page=QWebEnginePage(self.profile,self);key=id(job);self.jobs[key]=page;job['started']=time.monotonic()
   def finish(data=None,error=None):
    if job['done'].is_set():
     if key in self.jobs:self.jobs.pop(key,None);page.deleteLater()
     return
    job['data']=bytes(data) if data else None;job['error']=error;job['done'].set();self.jobs.pop(key,None);page.deleteLater()
   def ready(ok):
    if not ok:return finish(error='Could not load the printable report.')
    def fonts(state):
     if job['done'].is_set():return
     if state!='loaded' and time.monotonic()-job['started']<12:QTimer.singleShot(100,check);return
     if state!='loaded':return finish(error='Report fonts could not load. Retry the export.')
     layout=QPageLayout(QPageSize(QPageSize.A4),QPageLayout.Landscape if wide else QPageLayout.Portrait,QMarginsF(14,14,14,16),QPageLayout.Millimeter)
     page.printToPdf(lambda data:finish(data if bytes(data).startswith(b'%PDF-') else None,None if bytes(data).startswith(b'%PDF-') else 'PDF printing failed.'),layout)
    def check():page.runJavaScript('document.fonts.status',fonts)
    QTimer.singleShot(100,check)
   page.loadFinished.connect(ready);page.setHtml(content,QUrl(f'http://127.0.0.1:{self.port}/'))
   QTimer.singleShot(45000,lambda:finish(error='PDF creation timed out.') if not job['done'].is_set() else None)
  except Exception as ex:job['error']=str(ex);job['done'].set()

def configure(port,parent):
 global BROKER
 BROKER=ReportPrinter(port,parent)
 return BROKER

def route(handler):
 if urlsplit(handler.path).path!='/reports/pdf':return False
 if not handler.allowed() or handler.headers.get('Origin')!='http://'+handler.headers.get('Host',''):handler.json(403,{'error':'Only the local report export may print.'});return True
 if BROKER is None:handler.json(503,{'error':'Open the YOEAI desktop app to export a formatted report.'});return True
 if not GATE.acquire(False):handler.json(409,{'error':'A report is already printing. Wait and retry.'});return True
 try:
  if handler.headers.get('Transfer-Encoding'):raise ValueError('Unsupported transfer encoding.')
  if not handler.headers.get('Content-Type','').startswith('application/json'):raise ValueError('Use a JSON report request.')
  n=int(handler.headers.get('Content-Length','0'))
  if not 0<n<=950000:raise ValueError('Report request is empty or too large.')
  value=json.loads(handler.rfile.read(n))
  if not isinstance(value,dict):raise ValueError('The report request must be an object.')
  fragment=value.get('html');title=value.get('title','YOEAI report');document(fragment,title,BROKER.port)
  job={'html':fragment,'title':title,'done':threading.Event()};BROKER.requested.emit(job)
  if not job['done'].wait(48):job['done'].set();raise ValueError('PDF printing timed out. Try a shorter report.')
  if job.get('error'):raise ValueError(job['error'])
  data=job.get('data')
  if not data:raise ValueError('An empty PDF was returned.')
  handler.send_response(200);handler.send_header('Content-Type','application/pdf');handler.send_header('Cache-Control','no-store');handler.send_header('Content-Length',str(len(data)));handler.end_headers();handler.wfile.write(data)
 except (ValueError,TypeError,KeyError) as ex:handler.json(400,{'error':str(ex)})
 except (BrokenPipeError,ConnectionResetError):pass
 finally:GATE.release()
 return True
