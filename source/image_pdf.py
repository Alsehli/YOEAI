"""Local image conversion for the main chat; no inference or network access."""
import base64, io, json, threading, time, uuid
from urllib.parse import urlsplit
from PIL import Image, ImageOps, UnidentifiedImageError
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

LOCK=threading.Lock()
JOBS={}
FORMATS={'JPEG','PNG','WEBP','BMP','TIFF'}

def convert(items, size='a4', progress=lambda *a:None):
 if size not in {'a4','letter','original'}:raise ValueError('Choose A4, Letter or original size.')
 if not isinstance(items,list) or not 1<=len(items)<=40:raise ValueError('Select between 1 and 40 pictures.')
 out=io.BytesIO();pdf=canvas.Canvas(out,pageCompression=1);pdf.setTitle('YOEAI - Images to PDF')
 pages=[];pixels=0
 for index,item in enumerate(items):
  try:
   raw=base64.b64decode(item['data'].split(',',1)[-1],validate=True)
   if len(raw)>30*1024*1024:raise ValueError('Each picture must be under 30 MB.')
   with Image.open(io.BytesIO(raw)) as source:
    if source.format not in FORMATS:raise ValueError('Use JPG, PNG, WEBP, BMP or TIFF pictures.')
    for frame in range(getattr(source,'n_frames',1) if source.format=='TIFF' else 1):
     if len(pages)>=100:raise ValueError('Use at most 100 pages per PDF.')
     source.seek(frame);pixels+=source.width*source.height
     if source.width*source.height>60_000_000 or pixels>300_000_000:raise ValueError('These pictures are too large. Convert fewer pictures at a time.')
     image=ImageOps.exif_transpose(source).copy()
     dpi=source.info.get('dpi',(96,96))
     try:dx,dy=[max(36,min(1200,float(v))) for v in dpi]
     except (ValueError,TypeError):dx=dy=96
     if image.mode in ('RGBA','LA') or 'transparency' in image.info:
      rgba=image.convert('RGBA');image=Image.new('RGB',rgba.size,'white');image.paste(rgba,mask=rgba.getchannel('A'))
     else:image=image.convert('RGB')
     w,h=image.size
     pw,ph=(595.2756,841.8898) if size=='a4' else (612,792) if size=='letter' else (w*72/dx,h*72/dy)
     if size=='original' and max(pw,ph)>14400:raise ValueError('Original page is too large. Choose A4 or Letter.')
     margin=18 if size!='original' else 0
     scale=min((pw-2*margin)/w,(ph-2*margin)/h)
     dw,dh=w*scale,h*scale
     pdf.setPageSize((pw,ph));pdf.drawImage(ImageReader(image),(pw-dw)/2,(ph-dh)/2,dw,dh);pdf.showPage()
     pages.append({'width':pw,'height':ph,'imageWidth':w,'imageHeight':h,'drawWidth':dw,'drawHeight':dh})
     progress(index+1,len(items),len(pages))
  except (UnidentifiedImageError,Image.DecompressionBombError,Image.DecompressionBombWarning):raise ValueError('One picture is damaged or too large. Remove it and try again.')
 pdf.save();return out.getvalue(),pages

def run(key,body):
 job=JOBS[key]
 try:
  def progress(done,total,pages):job.update(message=f'Converting picture {done} of {total} - {pages} pages',completed=done)
  data,pages=convert(body.get('images'),body.get('size','a4'),progress)
  # Render the actual generated PDF, rather than showing source-image mockups.
  from PySide6.QtCore import QByteArray,QBuffer,QIODevice,QSize
  from PySide6.QtPdf import QPdfDocument
  buffer=QBuffer();buffer.setData(QByteArray(data));buffer.open(QIODevice.ReadOnly)
  document=QPdfDocument();document.load(buffer)
  if document.pageCount()!=len(pages):raise ValueError('PDF verification failed. Please retry.')
  previews=[]
  for n in range(document.pageCount()):
   extent=document.pagePointSize(n);scale=min(700/extent.width(),1000/extent.height())
   rendered=document.render(n,QSize(max(1,round(extent.width()*scale)),max(1,round(extent.height()*scale))))
   dest=QBuffer();dest.open(QIODevice.WriteOnly)
   if rendered.isNull() or not rendered.save(dest,'PNG'):raise ValueError('PDF preview could not be created.')
   previews.append('data:image/png;base64,'+base64.b64encode(bytes(dest.data())).decode())
  document.close();buffer.close()
  job.update(status='ready',message=f'PDF ready - {len(pages)} pages',pdf=data,previews=previews,pages=pages)
 except Exception as ex:job.update(status='failed',message=str(ex) if isinstance(ex,ValueError) else 'Could not convert these pictures. Check the files and try again.')

def route(handler,post=False):
 path=urlsplit(handler.path).path
 if not path.startswith('/image-pdf/'):return False
 if not handler.allowed():handler.json(403,{'error':'Only the local app may use this tool.'});return True
 if post and handler.headers.get('Origin')!='http://'+handler.headers.get('Host',''):handler.json(403,{'error':'Open this tool inside YOEAI.'});return True
 try:
  if post and path=='/image-pdf/create':
   if handler.headers.get('Transfer-Encoding'):raise ValueError('Unsupported upload.')
   length=int(handler.headers.get('Content-Length','0'))
   if not 0<length<=180*1024*1024:raise ValueError('Select fewer pictures (maximum upload 180 MB).')
   with LOCK:
    for key in list(JOBS):
     if time.time()-JOBS[key]['created']>900 and JOBS[key]['status']!='running':del JOBS[key]
    if any(j['status']=='running' for j in JOBS.values()):raise ValueError('Another PDF is converting. Wait for it to finish.')
    if len(JOBS)>=3:raise ValueError('Close older PDFs and try again in a few minutes.')
    body=json.loads(handler.rfile.read(length));key=uuid.uuid4().hex
    JOBS[key]={'created':time.time(),'status':'running','message':'Preparing pictures...'}
   threading.Thread(target=run,args=(key,body),daemon=True).start();handler.json(202,{'id':key})
  else:
   bits=path.split('/');key=bits[-1];job=JOBS.get(key)
   if not job:handler.json(404,{'error':'PDF expired. Convert the pictures again.'});return True
   if post and bits[-2]=='release':
    if job['status']!='running':JOBS.pop(key,None)
    handler.json(200,{'ok':True})
   elif not post and bits[-2]=='status':handler.json(200,{k:v for k,v in job.items() if k not in {'pdf','created'}})
   elif not post and bits[-2]=='file' and job['status']=='ready':
    data=job['pdf'];handler.send_response(200);handler.send_header('Content-Type','application/pdf');handler.send_header('Cache-Control','no-store');handler.send_header('Content-Length',str(len(data)));handler.end_headers();handler.wfile.write(data)
   else:handler.json(404,{'error':'PDF is not ready.'})
 except (ValueError,TypeError,KeyError) as ex:handler.json(400,{'error':str(ex)})
 return True
