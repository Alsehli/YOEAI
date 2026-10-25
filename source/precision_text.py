"""Local editable typography over immutable Image Turbo artwork. No model loader."""
import json,re,os,time,uuid,threading,hashlib,io,zipfile
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from configuration import APP_DIR,HOME

ID=re.compile(r'^[0-9a-f]{32}$')
CUE=re.compile(r'\b(?:saying\b|says\b|write\b(?: the text)?|add (?:the )?(?:words|text)\b|with (?:the )?words?\b|with (?:the )?text\b|text\s*:|title\s*:|subtitle\s*:|caption\s*:|headline\s*:|reads\s*:?)\s*|(?:بعبارة|بالعبارة|بالكلمات|يقول|مكتوب(?:ة)?\s*[:：]?|النص\s*[:：])\s*',re.I)
INTENT=re.compile(r'\b(?:saying|words|text|write|written|caption|headline|title|lettering|poster|banner|advertisement|certificate|logo|flyer|typography)\b|(?:بعبارة|كلمات|مكتوب|النص|إعلان|اعلان|ملصق|شعار)',re.I)
QUOTES=re.compile(r'"([^"\n]+)"|“([^”]+)”|«([^»]+)»|(?<!\w)\x27([^\x27\n]+)\x27(?!\w)')
FAMILIES={'Inter':'inter.ttf','Manrope':'manrope.ttf','JetBrains Mono':'jetbrainsmono.ttf','Noto Sans Arabic':'noto-sans-arabic.ttf','Segoe UI':None,'Arial':None}
FONT_LOCK=threading.Lock();FONT_READY=False

def exact_recipe(prompt,mode='auto'):
 if mode not in ['auto','on','off']:raise ValueError('Choose Automatic, Precision Text or Artwork only.')
 if mode=='off':return None
 spans=[]
 if INTENT.search(prompt):
  for m in QUOTES.finditer(prompt):
   group=next(i for i in range(1,5) if m.group(i) is not None)
   if re.search(r'(?:font|typeface|family|color|colour)\s*[:=]?\s*$',prompt[max(0,m.start()-24):m.start()],re.I):continue
   spans.append((m.start(group),m.end(group)))
 if not spans:
  cue=CUE.search(prompt)
  if cue:
   start=cue.end();end=len(prompt)
   while start<end and prompt[start].isspace():start+=1
   while end>start and prompt[end-1].isspace():end-=1
   if start<end:spans=[(start,end)]
 if not spans and mode!='on':return None
 if len(spans)>8:raise ValueError('Precision Text supports up to eight text blocks. Use the editor to simplify the layout.')
 requested=[prompt[a:b] for a,b in spans]
 if sum(map(len,requested))>12000:raise ValueError('Keep image text under 12,000 characters.')
 visual=prompt
 for a,b in reversed(spans):visual=visual[:a]+' uncluttered negative space '+visual[b:]
 visual=CUE.sub('',visual)
 visual=re.sub('[\"\u201c\u201d\u00ab\u00bb]','',visual)
 visual=re.sub(r'\b(?:saying|with the words|with words|with the text|caption|headline|lettering|text)\b','',visual,flags=re.I)
 visual=(visual[:1450]+'\nArtwork/background only. No writing, letters, numbers, signatures, typography, logos or watermarks. Reserve uncluttered negative space for typography added later. Clean empty '+('lower' if re.search(r'\b(?:bottom|lower)\b|أسفل',visual,re.I) else 'upper')+' area, balanced composition.')
 return {'originalPrompt':prompt,'visualPrompt':visual,'spans':spans,'requested':requested,'instruction':'Exact quoted text was copied without normalization.' if spans and QUOTES.search(prompt) else 'The ending after the text cue was copied literally. If it includes layout instructions, correct it in the editor.','stylePrompt':visual}

def ensure_fonts():
 global FONT_READY
 from PySide6.QtGui import QGuiApplication,QFontDatabase
 if QGuiApplication.instance() is None:raise ValueError('Precision Text requires the YOEAI desktop window to be running.')
 with FONT_LOCK:
  if not FONT_READY:
   for name,file in FAMILIES.items():
    if file and name not in QFontDatabase.families():
     if QFontDatabase.addApplicationFont(str(APP_DIR/'assets/fonts'/file))<0:raise ValueError('Bundled typography font is missing: '+name)
   FONT_READY=True
 return [name for name in FAMILIES if name in QFontDatabase.families()]

def initial_layers(recipe,width):
 result=[];count=max(1,len(recipe['requested']));style=recipe['stylePrompt'];align='right' if re.search(r'\bright\b|يمين',style,re.I) else 'left' if re.search(r'\bleft\b|يسار',style,re.I) else 'center'
 for i,text in enumerate(recipe['requested']):
  result.append({'id':uuid.uuid4().hex,'kind':'text','text':text,'font':'Noto Sans Arabic' if re.search('[\u0600-\u06ff]',text) else 'Manrope','size':round(width*.075),'bold':True,'x':.07,'y':(.58 if count==1 and re.search(r'\bbottom\b|أسفل',style,re.I) else .08)+i*.8/count,'width':.86,'height':min(.32,.75/count),'align':align,'direction':'auto','color':'#ffffff','outlineColor':'#102040','outline':1.5,'shadow':True,'panelColor':'#102040','panelOpacity':0,'autoFit':True})
 for layer in result:
  named=next((f for f in FAMILIES if re.search(r'\b'+re.escape(f)+r'\b',style,re.I)),None)
  if named:layer['font']=named
  color=next((v for word,v in [('red','#d92c48'),('blue','#2277ee'),('black','#101725'),('white','#ffffff'),('gold','#e9bd65')] if re.search(r'\b'+word+r'\b',style,re.I)),None)
  if color:layer['color']=color
  explicit=re.search(r'\b(\d{1,3})\s*(?:px|pixels)\b',style,re.I)
  if explicit and 8<=int(explicit[1])<=240:layer['size']=int(explicit[1])
 return result

def validate_layers(layers):
 if not isinstance(layers,list) or len(layers)>8:raise ValueError('Use at most eight text or cover layers.')
 allowed={'id','kind','text','font','size','bold','x','y','width','height','align','direction','color','outlineColor','outline','shadow','panelColor','panelOpacity','autoFit'};out=[];seen=set()
 for item in layers:
  if not isinstance(item,dict) or set(item)-allowed:raise ValueError('Unsupported text layer field.')
  layer=dict(item)
  if not ID.fullmatch(str(layer.get('id',''))) or layer['id'] in seen:raise ValueError('Layer identifiers must be unique.')
  seen.add(layer['id'])
  if layer.get('kind') not in ['text','cover'] or layer.get('font') not in FAMILIES:raise ValueError('Choose a supported layer/font.')
  text=layer.get('text')
  if not isinstance(text,str) or len(text)>6000 or '\x00' in text:raise ValueError('Use ordinary Unicode text, at most 6,000 characters per block.')
  if layer.get('kind')=='text' and not text.strip():raise ValueError('Enter text, delete this block, or choose a cover layer.')
  for key,low,high in [('x',0,1),('y',0,1),('width',.02,1),('height',.02,1),('size',8,240),('outline',0,12),('panelOpacity',0,100)]:
   v=layer.get(key)
   if type(v) not in (int,float) or not low<=v<=high:raise ValueError('Invalid '+key+' value.')
  for key in ['color','outlineColor','panelColor']:
   if not re.fullmatch('#[0-9a-fA-F]{6}',str(layer.get(key,''))):raise ValueError('Choose a six-digit RGB color.')
  for key in ['bold','shadow','autoFit']:
   if type(layer.get(key))!=bool:raise ValueError('Invalid '+key+' option.')
  if layer.get('align') not in ['left','center','right'] or layer.get('direction') not in ['auto','ltr','rtl']:raise ValueError('Choose a supported alignment/direction.')
  out.append(layer)
 if sum(len(x['text']) for x in out)>12000:raise ValueError('Use at most 12,000 text characters.')
 return out

def layout_text(layer,width,height,scale):
 from PySide6.QtCore import Qt,QPointF,QRectF
 from PySide6.QtGui import QFont,QTextLayout,QTextOption
 padding=(layer['outline']+4+(3 if layer['shadow'] else 0))*scale
 available=max(1,width-2*padding);vertical=max(1,height-2*padding)
 def build(size):
  font=QFont(layer['font']);font.setPixelSize(max(1,round(size*scale)));font.setWeight(QFont.Weight.Bold if layer['bold'] else QFont.Weight.Normal)
  layout=QTextLayout(layer['text'].replace('\n','\u2028'),font);option=QTextOption();option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere);option.setAlignment({'left':Qt.AlignmentFlag.AlignLeft,'right':Qt.AlignmentFlag.AlignRight,'center':Qt.AlignmentFlag.AlignHCenter}[layer['align']]);option.setTextDirection({'auto':Qt.LayoutDirection.LayoutDirectionAuto,'ltr':Qt.LayoutDirection.LeftToRight,'rtl':Qt.LayoutDirection.RightToLeft}[layer['direction']]);layout.setTextOption(option);layout.beginLayout();y=0;wide=False
  while True:
   line=layout.createLine()
   if not line.isValid():break
   line.setLineWidth(available);line.setPosition(QPointF(0,y));y+=line.height()*1.12;wide=wide or line.naturalTextWidth()>available+.5
  layout.endLayout();ink=QRectF();missing=False;families=set();glyphs=0
  for run in layout.glyphRuns():
   raw=run.rawFont();families.add(raw.familyName())
   for glyph,pos in zip(run.glyphIndexes(),run.positions()):
    glyphs+=1;missing=missing or glyph==0;box=raw.boundingRect(glyph).translated(pos);ink=box if ink.isNull() else ink.united(box)
  edge=(layer['outline']+(3 if layer['shadow'] else 0))*scale
  fits=not wide and y<=vertical+.5 and ink.left()-edge>=-padding and ink.top()-edge>=-padding and ink.right()+edge<=available+padding and ink.bottom()+edge<=vertical+padding
  return layout,{'fits':fits,'height':y,'actualSize':size,'missingGlyphs':missing,'fontsUsed':sorted(families),'glyphCount':glyphs,'lineCount':layout.lineCount()},padding
 size=layer['size'];layout,meta,pad=build(size)
 if layer['autoFit'] and not meta['fits']:
  low=8;high=int(size);best=build(low)
  while low<=high:
   mid=(low+high)//2;candidate=build(mid)
   if candidate[1]['fits']:best=candidate;low=mid+1
   else:high=mid-1
  layout,meta,pad=best
 return layout,meta,pad

def render(document,background,width):
 from PySide6.QtCore import QRectF,QPointF,QBuffer,QIODevice
 from PySide6.QtGui import QImage,QPainter,QColor,QPen,QPainterPath,QTransform
 from PySide6.QtCore import Qt
 ensure_fonts();source=QImage(str(background))
 if source.isNull():raise ValueError('The background image cannot be opened.')
 height=round(width*source.height()/source.width())
 if width>4096 or width<256 or width*height>16_777_216:raise ValueError('Export is limited to 4096 pixels and 16 megapixels.')
 scale=width/source.width();image=QImage(width,height,QImage.Format.Format_ARGB32_Premultiplied);painter=QPainter(image);painter.setRenderHint(QPainter.RenderHint.Antialiasing);painter.setRenderHint(QPainter.RenderHint.TextAntialiasing);painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform);painter.drawImage(QRectF(0,0,width,height),source);checks=[];issues=[];warnings=[];start=time.perf_counter();margin=document.get('margin',.04)
 try:
  for layer in document['layers']:
   rect=QRectF(layer['x']*width,layer['y']*height,layer['width']*width,layer['height']*height)
   if rect.right()>width+.5 or rect.bottom()>height+.5:issues.append(layer['id']+': layer extends outside the image')
   painter.save();painter.setClipRect(rect)
   if layer['panelOpacity']:
    color=QColor(layer['panelColor']);color.setAlphaF(layer['panelOpacity']/100);painter.fillRect(rect,color)
   if layer['kind']=='cover':checks.append({'id':layer['id'],'kind':'cover'});painter.restore();continue
   layout,check,padding=layout_text(layer,rect.width(),rect.height(),scale);check['id']=layer['id'];checks.append(check)
   if not check['fits']:issues.append(layer['id']+': text does not fit; enlarge the box or reduce font size')
   if check['missingGlyphs']:issues.append(layer['id']+': missing glyphs; choose a font supporting this language')
   if layer['x']<margin or layer['y']<margin or layer['x']+layer['width']>1-margin+.0001 or layer['y']+layer['height']>1-margin+.0001:issues.append(layer['id']+': text box is outside the safe margin')
   if re.search('[\u202a-\u202e\u2066-\u2069]',layer['text']):warnings.append('Explicit bidirectional control characters present; review the visual order.')
   # Paint paths from Qt's already-shaped glyph runs, retaining Arabic joins,
   # bidi placement and fallback fonts. A winding fill avoids overlap holes in
   # variable-font composite outlines; the stroke is painted behind the fill.
   path=QPainterPath();path.setFillRule(Qt.FillRule.WindingFill)
   for run in layout.glyphRuns():
    raw=run.rawFont()
    for glyph,pos in zip(run.glyphIndexes(),run.positions()):
     transform=QTransform();transform.translate(rect.x()+padding+pos.x(),rect.y()+padding+pos.y());path.addPath(transform.map(raw.pathForGlyph(glyph)))
   if layer['shadow']:
    shift=QTransform();shift.translate(3*scale,3*scale);painter.fillPath(shift.map(path),QColor('#99000000'))
   if layer['outline']:
    pen=QPen(QColor(layer['outlineColor']));pen.setWidthF(2*layer['outline']*scale);pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin);painter.strokePath(path,pen)
   painter.fillPath(path,QColor(layer['color']));painter.restore()
 finally:painter.end()
 for index,layer in enumerate(document['layers']):
  if layer['kind']!='text':continue
  box=QRectF(layer['x'],layer['y'],layer['width'],layer['height'])
  for later in document['layers'][index+1:]:
   if not box.intersects(QRectF(later['x'],later['y'],later['width'],later['height'])):continue
   if later['panelOpacity']==100:issues.append(layer['id']+': a later opaque panel/cover overlaps this text; move the cover behind it')
   elif later['kind']=='text':warnings.append('Text boxes overlap; review readability.')
 original=[x['text'] for x in document['requested']];current=[x['text'] for x in document['layers'] if x['kind']=='text'];changed=original!=current
 buffer=QBuffer();buffer.open(QIODevice.OpenModeFlag.WriteOnly)
 if not image.save(buffer,'PNG'):raise ValueError('Could not encode the rendered image.')
 return bytes(buffer.data()),{'layoutPassed':not issues,'issues':issues,'warnings':warnings,'originalText':original,'currentText':current,'textChanged':changed,'textExact':not changed,'layers':checks,'sceneText':'Not automatically verified. Review the background and the final image for unintended AI lettering. Overlay accuracy does not verify embedded scene text.','width':width,'height':height,'renderMs':round((time.perf_counter()-start)*1000,2),'shaper':'Qt Unicode shaping and bidi layout; glyph coverage checked, language correctness not inferred.'}

class TextProjects:
 def __init__(self,home):self.home=Path(home);self.home.mkdir(parents=True,exist_ok=True);self.lock=threading.RLock()
 def folder(self,ident):
  if not isinstance(ident,str) or not ID.fullmatch(ident):raise ValueError('Invalid text project.')
  p=self.home/ident
  if p.is_symlink():raise ValueError('Linked project blocked.')
  return p
 def load(self,ident):
  p=self.folder(ident)/'project.json'
  if not p.is_file():raise ValueError('Editable text project is unavailable on this PC.')
  value=json.loads(p.read_text(encoding='utf8'));return value
 def save(self,value):
  folder=self.folder(value['id']);folder.mkdir(exist_ok=True);stage=folder/'project.stage';stage.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8');os.replace(stage,folder/'project.json')
 def create(self,ident,recipe,background):
  with self.lock:
   folder=self.folder(ident)
   if (folder/'project.json').is_file():
    existing=self.load(ident)
    if 'verification' not in existing:self.refresh(existing)
    return existing
   from PIL import Image
   with Image.open(io.BytesIO(background)) as im:width,height=im.size
   if width*height>4_194_304:raise ValueError('The generated background exceeds the text project limit.')
   folder.mkdir(exist_ok=True);(folder/'background.png').write_bytes(background)
   layers=initial_layers(recipe,width);doc={'schemaVersion':1,'id':ident,'revision':1,'width':width,'height':height,'margin':.04,'originalPrompt':recipe['originalPrompt'],'visualPrompt':recipe['visualPrompt'],'extractionNote':recipe['instruction'],'requested':[{'text':t,'span':s} for t,s in zip(recipe['requested'],recipe['spans'])],'layers':validate_layers(layers),'backgroundSha256':hashlib.sha256(background).hexdigest(),'created':time.time()};self.save(doc);self.refresh(doc);return doc
 def refresh(self,doc):
  folder=self.folder(doc['id']);data,verification=render(doc,folder/'background.png',doc['width']);doc['verification']=verification;preview=folder/'preview.stage';preview.write_bytes(data);os.replace(preview,folder/'preview.png');self.save(doc)
 def edit(self,ident,body):
  with self.lock:
   doc=self.load(ident)
   if body.get('revision')!=doc['revision']:raise ValueError('This project changed in another editor. Reopen it before saving.')
   layers=validate_layers(body.get('layers'));margin=body.get('margin',.04)
   if type(margin) not in (int,float) or not 0<=margin<=.15:raise ValueError('Choose a safe margin from 0 to 15%.')
   doc.update(layers=layers,margin=margin,revision=doc['revision']+1);self.refresh(doc);return doc
 def export(self,ident,body):
  with self.lock:
   doc=self.load(ident)
   if body.get('revision')!=doc['revision']:raise ValueError('The project changed. Review its current version before exporting.')
   if body.get('backgroundReviewed') is not True:raise ValueError('Review the final image for unwanted AI lettering before exporting.')
   width=body.get('width',doc['width'])
   if type(width)!=int or not doc['width']<=width<=4096:raise ValueError('Choose an export width between the original size and 4096.')
   folder=self.folder(ident)
   if hashlib.sha256((folder/'background.png').read_bytes()).hexdigest()!=doc['backgroundSha256']:raise ValueError('The original artwork changed outside this editor. Restore it before export.')
   data,check=render(doc,folder/'background.png',width)
   if not check['layoutPassed']:raise ValueError('Export blocked: '+'; '.join(check['issues']))
   if check['textChanged'] and body.get('textEditsApproved') is not True:raise ValueError('The text differs from the original request. Explicitly approve your edited wording.')
   export=uuid.uuid4().hex;kind=body.get('format','png')
   if kind=='png':(folder/(export+'.png')).write_bytes(data)
   elif kind=='zip':
    with zipfile.ZipFile(folder/(export+'.zip'),'w',zipfile.ZIP_DEFLATED) as z:z.write(folder/'background.png','background.png');z.writestr('text-layers.json',json.dumps(doc,ensure_ascii=False,indent=2));z.writestr('preview.png',data)
   else:raise ValueError('Choose PNG or an editable project ZIP.')
   (folder/(export+'.verification.json')).write_text(json.dumps(check,ensure_ascii=False,indent=2),encoding='utf8')
   return {'url':f'/imagegen/precision/export/{ident}/{export}.{kind}','verification':check,'filename':'YOEAI-precision.'+kind}

class PrecisionEngines:
 def __init__(self,base,home):self.base=base;self.projects=TextProjects(home);self.pending={};self.lock=threading.RLock()
 def __getattr__(self,name):return getattr(self.base,name)
 def start(self,body):
  if not isinstance(body,dict):return self.base.start(body)
  recipe=exact_recipe(body.get('prompt',''),body.get('precisionMode','auto')) if body.get('engine','turbo')=='turbo' and isinstance(body.get('prompt'),str) else None
  request=dict(body)
  if recipe:request['prompt']=recipe['visualPrompt']
  result=self.base.start(request)
  if recipe:
   with self.lock:
    self.pending[result['id']]=recipe
    if len(self.pending)>128:self.pending.pop(next(iter(self.pending)))
   result['precisionPending']=True
  return result
 def status(self):
  state=self.base.status();ident=state.get('id')
  if state.get('status')=='complete' and ident and (ident in self.pending or (self.projects.folder(ident)/'project.json').is_file()):
   with self.lock:
    try:
     doc=self.projects.create(ident,self.pending[ident],self.base.output(ident)) if ident in self.pending else self.projects.load(ident);state['precisionProject']=ident;state['precisionRevision']=doc['revision']
    except Exception as error:state['precisionError']='Artwork is ready, but typography needs attention: '+str(error)
  return state


def precision_route(handler,engines,post):
 path=urlsplit(handler.path);prefix='/imagegen/precision/'
 if not path.path.startswith(prefix):return False
 if not handler.allowed() or post and handler.headers.get('Origin')!='http://'+handler.headers.get('Host',''):handler.json(403,{'error':'Use the local Image Turbo interface.'});return True
 try:
  parts=path.path[len(prefix):].split('/');body={}
  if post:
   n=int(handler.headers.get('Content-Length','0'))
   if handler.headers.get('Transfer-Encoding') or not 0<n<=120000:raise ValueError('Invalid text-editor request size.')
   body=json.loads(handler.rfile.read(n))
   if not isinstance(body,dict):raise ValueError('Text-editor request must be an object.')
  if parts==['fonts'] and not post:handler.json(200,{'fonts':ensure_fonts()});return True
  if parts==['analyze'] and post:
   prompt=body.get('prompt')
   if not isinstance(prompt,str) or len(prompt)>2000:raise ValueError('Use an image prompt under 2,000 characters.')
   handler.json(200,{'recipe':exact_recipe(prompt,body.get('mode','auto'))});return True
  if len(parts)==2 and parts[0]=='project':
   if post:value=engines.projects.edit(parts[1],body)
   else:value=engines.projects.load(parts[1])
   handler.json(200,value);return True
  if len(parts)==2 and parts[0]=='export' and post:handler.json(200,engines.projects.export(parts[1],body));return True
  file=None;mime=None
  if len(parts)==3 and parts[0]=='project' and parts[2] in ['preview','background'] and not post:file=engines.projects.folder(parts[1])/(parts[2]+'.png');mime='image/png'
  if len(parts)==3 and parts[0]=='export' and not post and re.fullmatch('[0-9a-f]{32}\\.(png|zip)',parts[2]):file=engines.projects.folder(parts[1])/parts[2];mime='image/png' if parts[2].endswith('.png') else 'application/zip'
  if file is None or not file.is_file() or file.is_symlink():raise ValueError('Text-project asset not found.')
  handler.send_response(200);handler.send_header('Content-Type',mime);handler.send_header('Content-Length',str(file.stat().st_size));handler.send_header('Cache-Control','no-store');handler.send_header('X-Content-Type-Options','nosniff');handler.end_headers()
  with file.open('rb') as stream:
   while data:=stream.read(1024*1024):handler.wfile.write(data)
 except (BrokenPipeError,ConnectionResetError):pass
 except (ValueError,OSError,TypeError,KeyError) as error:handler.json(400,{'error':str(error)})
 return True
