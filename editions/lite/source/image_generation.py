"""Optional local image generation. Fixed executable/models; no model-written commands."""
import atexit,hashlib,json,os,re,struct,subprocess,threading,time,uuid,zlib
from pathlib import Path

def has_visual_content(path):
 data=Path(path).read_bytes()
 if data[:8]!=b'\x89PNG\r\n\x1a\n':return False
 offset=8;compressed=[];width=height=channels=0
 while offset+12<=len(data):
  length=struct.unpack('>I',data[offset:offset+4])[0];kind=data[offset+4:offset+8];chunk=data[offset+8:offset+8+length];offset+=length+12
  if kind==b'IHDR':
   width,height,depth,color,_,_,interlace=struct.unpack('>IIBBBBB',chunk)
   if depth!=8 or interlace or color not in (0,2,6) or width>2048 or height>2048:return False
   channels={0:1,2:3,6:4}[color]
  elif kind==b'IDAT':compressed.append(chunk)
 if not width or not height:return False
 stride=width*channels;raw=zlib.decompress(b''.join(compressed))
 if len(raw)!=(stride+1)*height:return False
 previous=bytearray(stride);mins=[255]*min(channels,3);maxs=[0]*len(mins)
 for y in range(height):
  row=bytearray(raw[y*(stride+1)+1:(y+1)*(stride+1)]);filter_type=raw[y*(stride+1)]
  for x in range(stride):
   a=row[x-channels] if x>=channels else 0;b=previous[x];c=previous[x-channels] if x>=channels else 0
   if filter_type==1:row[x]=(row[x]+a)&255
   elif filter_type==2:row[x]=(row[x]+b)&255
   elif filter_type==3:row[x]=(row[x]+((a+b)//2))&255
   elif filter_type==4:
    v=a+b-c;pa,pb,pc=abs(v-a),abs(v-b),abs(v-c);row[x]=(row[x]+(a if pa<=pb and pa<=pc else b if pb<=pc else c))&255
   elif filter_type!=0:return False
  for channel in range(len(mins)):
   values=row[channel::channels];mins[channel]=min(mins[channel],min(values));maxs[channel]=max(maxs[channel],max(values))
  previous=row
 return any(high-low>2 for low,high in zip(mins,maxs))

class ImageGenerator:
 def __init__(self,config_path,home,pause=None,resume=None,max_size=1024):
  self.config_path=Path(config_path);self.home=Path(home);self.pause=pause;self.resume=resume;self.max_size=max_size
  self.lock=threading.RLock();self.worker=None;atexit.register(self.shutdown);self.process=None;self.cancelled=threading.Event();self.state={'status':'idle','message':'Ready to create an image.'}
 def config(self):
  if not self.config_path.is_file():raise ValueError('Image generation is not installed. Connect the image-generation drive and finish local setup.')
  c=json.loads(self.config_path.read_text(encoding='utf-8-sig'))
  for key in ['executable','diffusion','encoder','vae']:
   if not Path(c.get(key,'')).is_file():raise ValueError('Image component missing: '+key+'. Reconnect the model drive or repair the image add-on.')
  return c
 def status(self):
  with self.lock:return dict(self.state)
 def start(self,body):
  if not isinstance(body,dict):raise ValueError('Image request must be a JSON object.')
  prompt=body.get('prompt');size=body.get('size',512)
  if not isinstance(prompt,str) or not prompt.strip() or len(prompt)>2000:raise ValueError('Enter an image description of 1 to 2,000 characters.')
  if type(size) is not int or size not in (512,768,1024) or size>self.max_size:raise ValueError('Choose a supported image size.')
  c=self.config()
  with self.lock:
   if self.state['status'] in ('running','restoring'):raise ValueError('An image is already being created.')
   self.cancelled.clear();job=uuid.uuid4().hex;self.state={'status':'running','message':'Preparing image generation…','id':job,'started':time.time()}
   self.worker=threading.Thread(target=self.run,args=(c,prompt,size,job),daemon=True);self.worker.start()
  return self.status()
 def cancel(self):
  self.cancelled.set()
  with self.lock:
   if self.process is not None and self.process.poll() is None:self.process.terminate()
  return self.status()
 def shutdown(self):
  self.cancel()
  if self.worker and self.worker.is_alive() and self.worker is not threading.current_thread():self.worker.join(timeout=270)
 def run(self,c,prompt,size,job):
  paused=False;handle=None;result={};self.home.mkdir(parents=True,exist_ok=True)
  root=self.config_path.parent;lockfile=root/'generation.lock';output=self.home/(job+'.png');log=self.home/(job+'.log')
  try:
   try:handle=os.open(lockfile,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
   except FileExistsError:raise ValueError('Another image-generation job is active. If a previous app crashed, reopen the image add-on to recover its lock.')
   os.write(handle,str(os.getpid()).encode())
   if self.pause:
    self.state['message']='Pausing chat to free GPU memory…';paused=bool(self.pause())
   if self.cancelled.is_set():raise InterruptedError('Image creation stopped.')
   seed=int.from_bytes(os.urandom(4),'little')
   args=[c['executable'],'--diffusion-model',c['diffusion'],'--llm',c['encoder'],'--vae',c['vae'],'--cfg-scale','1.0','--steps','8','-W',str(size),'-H',str(size),'--seed',str(seed),'--output',str(output),'-p',prompt]+c.get('arguments',[])
   self.state['message']='Creating your image locally…'
   with log.open('w',encoding='utf-8') as trace:
    with self.lock:
     if self.cancelled.is_set():raise InterruptedError('Image creation stopped.')
     self.process=subprocess.Popen(args,cwd=str(Path(c['executable']).parent),stdin=subprocess.DEVNULL,stdout=trace,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    try:code=self.process.wait(timeout=900)
    except subprocess.TimeoutExpired:self.process.terminate();self.process.wait(timeout=20);raise ValueError('Image generation timed out. Try 512 pixels.')
   if self.cancelled.is_set():raise InterruptedError('Image creation stopped.')
   if code or not output.is_file() or not has_visual_content(output):raise ValueError('The image engine produced no usable image. Check the model files and local generation log.')
   result={'status':'complete','message':'Image ready.','id':job,'url':'/imagegen/output/'+job,'seconds':round(time.time()-self.state['started'],1),'seed':seed}
  except InterruptedError as e:result={'status':'cancelled','message':str(e)}
  except Exception as e:result={'status':'error','message':str(e)}
  finally:
   with self.lock:self.process=None
   if paused and self.resume:
    self.state['status']='restoring';self.state['message']='Restoring your chat model…'
    try:self.resume()
    except Exception:result['message']=result.get('message','')+' Chat could not restart automatically; reopen YOEAI.';result['chatRestartFailed']=True
   if handle is not None:
    os.close(handle)
    try:lockfile.unlink()
    except OSError:pass
   with self.lock:self.state=result
 def output(self,name):
  if not re.fullmatch('[0-9a-f]{32}',name):raise ValueError('Invalid image reference.')
  p=self.home/(name+'.png')
  if not p.is_file():raise ValueError('Image not found.')
  return p.read_bytes()

def handle_request(handler,generator,post=False):
 path=handler.path.split('?',1)[0]
 if not path.startswith('/imagegen/'):return False
 reply=getattr(handler,'json',None) or handler.reply
 if not handler.allowed():reply(403,{'error':'Only the local YOEAI interface may use image generation.'});return True
 try:
  if post:
   host=handler.headers.get('Host','');origin=handler.headers.get('Origin')
   if origin!='http://'+host:raise ValueError('Use the local YOEAI image screen to create images.')
   if handler.headers.get('Transfer-Encoding'):raise ValueError('Unsupported transfer encoding.')
   length=int(handler.headers.get('Content-Length','0'))
   if not 0<length<=10000:raise ValueError('Invalid image request size.')
   body=json.loads(handler.rfile.read(length))
   if path=='/imagegen/create':reply(202,generator.start(body))
   elif path=='/imagegen/stop':reply(200,generator.cancel())
   else:reply(404,{'error':'Image route not found.'})
  elif path=='/imagegen/status':reply(200,generator.status())
  elif path.startswith('/imagegen/output/'):
   data=generator.output(path.rsplit('/',1)[-1]);handler.send_response(200);handler.send_header('Content-Type','image/png');handler.send_header('X-Content-Type-Options','nosniff');handler.send_header('Content-Disposition','attachment; filename="YOEAI-image.png"');handler.send_header('Cache-Control','no-store');handler.send_header('Content-Length',str(len(data)));handler.end_headers();handler.wfile.write(data)
  else:reply(404,{'error':'Image route not found.'})
 except (ValueError,TypeError,json.JSONDecodeError) as e:reply(400,{'error':str(e)})
 return True
