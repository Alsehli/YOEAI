"""Scoped document/productivity tools. Fixed Python operations, never generated commands."""
import io,json,base64,hashlib,os,time,wave
from pathlib import Path
from windows_policy import scoped_path
from windows_capabilities import paths,validate

def read_limit(path,limit=100_000_000):
 if not path.is_file() or path.stat().st_size>limit:raise ValueError('Choose a supported file under 100 MB.')
 return path.read_bytes()
def save_new(path,data):
 with path.open('xb') as f:f.write(data)
 return {'saved':str(path),'bytes':len(data),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'verified':path.read_bytes()==data}
def pdfs(items):
 from pypdf import PdfReader
 readers=[]
 for p in items:
  if p.suffix.lower()!='.pdf':raise ValueError('Choose PDF source files.')
  reader=PdfReader(io.BytesIO(read_limit(p)))
  if reader.is_encrypted:raise ValueError('Unlock the PDF yourself before selecting it; passwords are never collected.')
  if len(reader.pages)>200:raise ValueError('Use PDFs with at most 200 pages.')
  readers.append(reader)
 if sum(len(r.pages) for r in readers)>200:raise ValueError('Use at most 200 pages per task.')
 return readers

def execute(name,p,scope,context):
 validate(name,p,scope)
 if name in {'images_pdf','pdf_transform','image_transform'}:sources=paths(p['paths'],scope)
 if p.get('destination'):dest=scoped_path(scope['folder'],p['destination'],False)
 if name=='images_pdf':
  from image_pdf import convert
  items=[{'data':base64.b64encode(read_limit(f,30*1024*1024)).decode()} for f in sources]
  data,pages=convert(items,p.get('size','a4'));result=save_new(dest,data);result.update(pages=len(pages),pageSize=p.get('size','a4'));return result
 if name=='pdf_transform':
  from pypdf import PdfWriter,PageObject,Transformation
  readers=pdfs(sources);op=p['operation'];writer=PdfWriter()
  if op=='extract_images':
   # A new directory is required. No original PDF or existing output is modified.
   dest.mkdir(exist_ok=False);count=0
   for reader in readers:
    for page in reader.pages:
     for image in page.images:
      count+=1
      if count>100:raise ValueError('Stopped at 100 extracted images. Partial output is retained for review.')
      ext=Path(image.name).suffix.lower()
      if ext not in ['.png','.jpg','.jpeg','.tif','.tiff','.jp2']:ext='.bin'
      save_new(dest/(str(count).zfill(3)+ext),image.data)
   return {'saved':str(dest),'images':count,'verified':len(list(dest.iterdir()))==count}
  for reader in readers:
   for original in reader.pages:
    staging=PdfWriter();page=staging.add_page(original)
    if op=='rotate':page.rotate(p.get('degrees',90))
    if op=='a4':
     page.transfer_rotation_to_content();width=float(page.mediabox.width);height=float(page.mediabox.height);scale=min(595.2756/width,841.8898/height)
     target=PageObject.create_blank_page(width=595.2756,height=841.8898)
     transform=Transformation().translate(-float(page.mediabox.left),-float(page.mediabox.bottom)).scale(scale).translate((595.2756-width*scale)/2,(841.8898-height*scale)/2)
     target.merge_transformed_page(page,transform);page=target
    added=writer.add_page(page)
    if op=='compress':added.compress_content_streams()
  out=io.BytesIO();writer.write(out);data=out.getvalue();checked=pdfs_bytes(data);result=save_new(dest,data);result.update(pages=checked,operation=op,compression='Lossless content-stream compression; smaller output is not guaranteed' if op=='compress' else None);return result
 if name=='image_transform':
  from PIL import Image,ImageOps
  pictures=[]
  for f in sources:
   with Image.open(io.BytesIO(read_limit(f,30*1024*1024))) as im:
    if im.width*im.height>40_000_000:raise ValueError('Use pictures under 40 megapixels.')
    pictures.append(ImageOps.exif_transpose(im).convert('RGB'))
  if p['operation']=='rotate':
   if len(pictures)!=1:raise ValueError('Select one picture to rotate into a new file.')
   image=pictures[0].rotate(-p.get('degrees',90),expand=True)
  else:
   from math import ceil
   image=Image.new('RGB',(960,ceil(len(pictures)/4)*220),'white')
   for i,pic in enumerate(pictures):
    pic.thumbnail((220,200));image.paste(pic,((i%4)*240+(240-pic.width)//2,(i//4)*220+(220-pic.height)//2))
  out=io.BytesIO();image.save(out,format='PNG' if dest.suffix.lower()=='.png' else 'JPEG',quality=95)
  result=save_new(dest,out.getvalue());result.update(width=image.width,height=image.height);return result
 if name=='document_preview':
  import re
  from PIL import Image,ImageOps
  source=scoped_path(scope['folder'],p['path']);raw=read_limit(source)
  pages=None
  if source.suffix.lower()=='.pdf':
   pages=len(pdfs([source])[0].pages)
   os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
   from PySide6.QtGui import QGuiApplication
   from PySide6.QtCore import QBuffer,QByteArray,QIODevice,QSize
   from PySide6.QtPdf import QPdfDocument
   application=QGuiApplication.instance() or QGuiApplication([]);buffer=QBuffer();buffer.setData(QByteArray(raw));buffer.open(QIODevice.ReadOnly);pdf=QPdfDocument();pdf.load(buffer);page=p.get('page',1)-1
   if not 0<=page<pdf.pageCount():raise ValueError('That page does not exist.')
   extent=pdf.pagePointSize(page);scale=min(1000/extent.width(),1200/extent.height());img=pdf.render(page,QSize(max(1,round(extent.width()*scale)),max(1,round(extent.height()*scale))))
   output=QBuffer();output.open(QIODevice.WriteOnly)
   if img.isNull() or not img.save(output,'PNG'):raise ValueError('Could not render this PDF page.')
   image=Image.open(io.BytesIO(bytes(output.data()))).convert('RGBA');pdf.close();buffer.close()
  else:
   with Image.open(io.BytesIO(raw)) as original:
    if original.width*original.height>40_000_000:raise ValueError('Use an image under 40 megapixels.')
    image=ImageOps.exif_transpose(original).convert('RGBA')
  image.thumbnail((1000,1200));white=Image.new('RGB',image.size,'white');white.paste(image,mask=image.getchannel('A'));out=io.BytesIO();white.save(out,format='JPEG',quality=88);data=out.getvalue()
  if not re.fullmatch('[a-f0-9]{32}',context.get('task','')):raise ValueError('Invalid preview task.')
  folder=Path(context['home'])/'WindowsShots'/context['task'];folder.mkdir(parents=True,exist_ok=True);digest=hashlib.sha256(data).hexdigest();name=digest+'.jpg';target=folder/name
  if not target.exists():save_new(target,data)
  if hashlib.sha256(target.read_bytes()).hexdigest()!=digest:raise ValueError('Preview cache integrity check failed.')
  return {'screenshot':name,'sha256':digest,'width':white.width,'height':white.height,'pages':pages,'previewPage':p.get('page',1),'verified':True,'notice':'Preview only; no user output file was saved. PDF preview shows only the selected page.'}
 if name=='document_info' or name=='media_info':
  path=scoped_path(scope['folder'],p['path']);data=read_limit(path)
  if path.suffix.lower() in ['.docx','.xlsx','.pptx']:
   import zipfile
   with zipfile.ZipFile(io.BytesIO(data)) as z:
    if len(z.infolist())>5000 or sum(x.file_size for x in z.infolist())>100_000_000:raise ValueError('Expanded Office document is too large.')
  if path.suffix.lower()=='.pdf':return {'pages':len(pdfs([path])[0].pages),'bytes':len(data),'verified':True}
  if path.suffix.lower() in ['.png','.jpg','.jpeg','.webp','.bmp','.tif','.tiff']:
   from PIL import Image
   with Image.open(io.BytesIO(data)) as im:return {'width':im.width,'height':im.height,'frames':getattr(im,'n_frames',1),'format':im.format,'bytes':len(data),'verified':True}
  if path.suffix.lower()=='.wav':
   with wave.open(io.BytesIO(data)) as f:return {'seconds':f.getnframes()/f.getframerate(),'channels':f.getnchannels(),'sampleRate':f.getframerate(),'verified':True}
  if path.suffix.lower()=='.docx':
   from docx import Document
   d=Document(io.BytesIO(data));return {'paragraphs':len(d.paragraphs),'tables':len(d.tables),'pages':None,'notice':'Word pagination was not measured.','verified':True}
  if path.suffix.lower()=='.xlsx':
   from openpyxl import load_workbook
   w=load_workbook(io.BytesIO(data),read_only=True,data_only=True);r={'sheets':w.sheetnames,'verified':True};w.close();return r
  if path.suffix.lower()=='.pptx':
   from pptx import Presentation
   return {'slides':len(Presentation(io.BytesIO(data)).slides),'verified':True}
  raise ValueError('This format is not supported by the local metadata reader. No duration or page count was guessed.')
 if name=='office_create':
  out=io.BytesIO();text=p.get('text','');title=p.get('title','YOEAI document')[:200]
  if p['format']=='docx':
   from docx import Document
   d=Document();d.add_heading(title,0)
   for line in text.splitlines():d.add_paragraph(line)
   d.save(out);assert len(Document(io.BytesIO(out.getvalue())).paragraphs)>0
  elif p['format']=='xlsx':
   from openpyxl import Workbook,load_workbook
   import csv
   w=Workbook();ws=w.active;ws.title='Tracker'
   for row in csv.reader(io.StringIO(text),delimiter='\t'):
    # Never allow generated cells to become Excel formulas or external links.
    ws.append(["'"+v if v.startswith(('=','+','-','@')) else v for v in row[:40]])
   w.save(out);check=load_workbook(io.BytesIO(out.getvalue()),read_only=True);check.close()
  else:
   from pptx import Presentation
   d=Presentation()
   for section in text.split('\n\n')[:20] or [title]:
    lines=section.splitlines();slide=d.slides.add_slide(d.slide_layouts[1]);slide.shapes.title.text=(lines[0] if lines else title)[:200];slide.placeholders[1].text='\n'.join(lines[1:])
   d.save(out);assert len(Presentation(io.BytesIO(out.getvalue())).slides)>0
  return save_new(dest,out.getvalue())|{'format':p['format']}
 if name=='office_pdf':
  source=scoped_path(scope['folder'],p['path']);read_limit(source)
  from windows_office import export_pdf
  data=export_pdf(source,dest.parent);return save_new(dest,data)|{'pages':pdfs_bytes(data)}
 if name=='calendar_draft':
  from datetime import datetime,timedelta,timezone
  import uuid
  start=datetime.fromisoformat(p['start']).astimezone(timezone.utc);end=start+timedelta(minutes=p['minutes'])
  title=p.get('title','Appointment').replace('\\','\\\\').replace('\n','\\n').replace('\r','').replace(',','\\,').replace(';','\\;')
  text='BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//YOEAI//Local draft//EN\r\nBEGIN:VEVENT\r\nUID:'+uuid.uuid4().hex+'@yoeai.local\r\nDTSTAMP:'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'\r\nDTSTART:'+start.strftime('%Y%m%dT%H%M%SZ')+'\r\nDTEND:'+end.strftime('%Y%m%dT%H%M%SZ')+'\r\nSUMMARY:'+title+'\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n'
  return save_new(dest,fold_ics(text).encode('utf-8'))|{'activeReminder':False,'invitationsSent':False,'notice':'Calendar draft saved. Import it yourself; no reminder service was scheduled.'}
 raise ValueError('Unsupported productivity operation.')

def pdfs_bytes(data):
 from pypdf import PdfReader
 count=len(PdfReader(io.BytesIO(data)).pages)
 if not count:raise ValueError('The generated PDF has no pages.')
 return count


def fold_ics(text):
 lines=[]
 for line in text.splitlines():
  part=''
  for char in line:
   if len((part+char).encode('utf-8'))>74:lines.append(part);part=' '+char
   else:part+=char
  lines.append(part)
 return '\r\n'.join(lines)+'\r\n'
