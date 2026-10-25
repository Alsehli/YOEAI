"""Local deterministic preparation of explicitly approved game images.
No claim of diffusion-generated transparency, frame consistency or inpainting.
"""
import base64,io,json,uuid
from pathlib import Path
from PIL import Image,ImageOps
from game_studio import atomic,sha

STATES=['idle','walk','run','jump','fall','attack','hurt','death','dash','interact','special']
def prepare(studio,body):
 if body.get('approve') is not True:raise ValueError('Review the source image and approve its import.')
 root,doc=studio.project(body['project']);studio.idle(doc['id']);studio.integrity(root,doc)
 state=body.get('state','idle');columns=body.get('columns',1);rows=body.get('rows',1);frames=body.get('frames',1);size=body.get('size',128);remove=body.get('removeBackground',False);ppu=body.get('ppu',32);fps=body.get('fps',10);pivot=body.get('pivot',[.5,.5]);filtering=body.get('filter','point')
 if state not in STATES or type(columns)!=int or type(rows)!=int or not 1<=columns<=8 or not 1<=rows<=8 or type(frames)!=int or not 1<=frames<=min(columns*rows,32) or size not in [64,128,256,512] or type(remove)!=bool:raise ValueError('Choose a supported action, grid up to 8×8, up to 32 frames and 64–512 px canvas.')
 if ppu not in [8,16,32,64,100] or type(fps)!=int or not 1<=fps<=24 or filtering not in ['point','bilinear'] or not isinstance(pivot,list) or len(pivot)!=2 or not all(type(x) in [int,float] and 0<=x<=1 for x in pivot):raise ValueError('Choose supported PPU, 1–24 FPS, a filter and normalized pivot coordinates.')
 raw=base64.b64decode(body.get('data',''),validate=True)
 if not 1<=len(raw)<=10_000_000:raise ValueError('Choose an image smaller than 10 MB.')
 with Image.open(io.BytesIO(raw)) as source:
  if source.width*source.height>16_000_000:raise ValueError('Choose an image under 16 megapixels.')
  image=ImageOps.exif_transpose(source).convert('RGBA')
 if image.width%columns or image.height%rows:raise ValueError('The image must divide evenly into the selected frame grid. Crop it first; labels and missing frames cannot be inferred reliably.')
 w,h=image.width//columns,image.height//rows
 if w<8 or h<8:raise ValueError('Frames are too small.')
 checkpoint=studio.checkpoint(root,doc);out=[];alpha=False
 for index in range(frames):
  x,y=index%columns,index//columns;frame=image.crop((x*w,y*h,(x+1)*w,(y+1)*h));frame.thumbnail((size,size),Image.Resampling.LANCZOS);fw,fh=frame.size
  if remove:
   # Border-connected flat color only. Never erase interior regions on color alone.
   color=frame.getpixel((0,0));pixels=frame.load();queue=[(0,0),(fw-1,0),(0,fh-1),(fw-1,fh-1)];seen=set()
   while queue:
    a,b=queue.pop()
    if (a,b) in seen or not 0<=a<fw or not 0<=b<fh:continue
    seen.add((a,b));p=pixels[a,b]
    if max(abs(p[k]-color[k]) for k in range(3))>22:continue
    pixels[a,b]=(p[0],p[1],p[2],0);queue.extend([(a-1,b),(a+1,b),(a,b-1),(a,b+1)])
  if frame.getchannel('A').getbbox() is None:raise ValueError('This frame is empty after background removal. Use a contrasting source or disable background removal.')
  frame.thumbnail((size,size),Image.Resampling.LANCZOS);canvas=Image.new('RGBA',(size,size));canvas.alpha_composite(frame,((size-frame.width)//2,size-frame.height));alpha=alpha or canvas.getextrema()[3][0]<255;path=root/'Assets/YOE/Art'/(state+'-'+str(index).zfill(3)+'.png');canvas.save(path);doc['trusted'][path.relative_to(root).as_posix()]=sha(path);out.append(path.relative_to(root).as_posix())
 warning='Frame consistency, labels and anatomy need visual review. Grid slicing cannot validate animation quality.'
 record={'id':uuid.uuid4().hex,'state':state,'files':out,'canvas':size,'alphaPresent':alpha,'pivot':pivot,'fps':fps,'filter':filtering,'ppu':ppu,'review':warning,'backgroundRemoval':'border-connected flat-color flood fill only' if remove else 'none; source alpha preserved'}
 settings=root/'Assets/YOE/Art'/(state+'.settings.json');atomic(settings,{'frames':frames,'ppu':ppu,'fps':fps,'pivotX':pivot[0],'pivotY':pivot[1],'filter':filtering});doc['trusted'][settings.relative_to(root).as_posix()]=sha(settings)
 doc['assets'].append(record);doc['history'].append({'action':'approved sprite import','checkpoint':checkpoint,'asset':record['id']});studio.save(root,doc);return record

def audio(studio,body):
 if body.get('approve') is not True or body.get('licensed') is not True:raise ValueError('Approve import and confirm you have permission to use this audio.')
 role=body.get('role','music')
 if role not in ['music','coin','hurt']:raise ValueError('Choose music, coin or hurt audio.')
 raw=base64.b64decode(body.get('data',''),validate=True)
 if not 44<=len(raw)<=10_000_000 or raw[:4]!=b'RIFF' or raw[8:12]!=b'WAVE':raise ValueError('Choose a WAV audio file under 10 MB.')
 import wave
 with wave.open(io.BytesIO(raw)) as w:
  if w.getnchannels() not in [1,2] or w.getframerate()>96000:raise ValueError('Use mono/stereo PCM WAV up to 96 kHz.')
 root,doc=studio.project(body['project']);studio.idle(doc['id']);studio.integrity(root,doc);cp=studio.checkpoint(root,doc);p=root/'Assets/Resources'/({'music':'YOEMusic','coin':'YOECoin','hurt':'YOEHurt'}[role]+'.wav');p.write_bytes(raw);doc['trusted'][p.relative_to(root).as_posix()]=sha(p);doc['history'].append({'action':'approved licensed audio import','role':role,'checkpoint':cp});studio.save(root,doc);return {'imported':p.relative_to(root).as_posix(),'generationAvailable':False}
