"""Optional Normal-edition local video jobs. Fixed model paths and argument arrays."""
import atexit,hashlib,json,os,re,subprocess,threading,time,uuid,urllib.request,shutil
from pathlib import Path

ACTIVE={'running','restoring','installing'}
PROFILES={'fast':(640,384,16),'quality':(832,480,20)}
class VideoGenerator:
 def __init__(self,config_path,home,pause=None,resume=None):
  self.config_path=Path(config_path);self.home=Path(home);self.pause=pause;self.resume=resume;self.lock=threading.RLock();self.preview_lock=threading.Lock();self.cancelled=threading.Event();self.process=None;self.worker=None;self.state={'status':'idle','message':'Ready to create a short video.'};atexit.register(self.shutdown)
 def config(self,require=True):
  if not self.config_path.is_file():raise ValueError('Video add-on is missing. Install the Normal video add-on first.')
  c=json.loads(self.config_path.read_text(encoding='utf-8-sig'))
  if c.get('engine')=='ltx':
   for key in ['python','worker','ffmpeg','gpuLock','checkpoint','encoderIndex']:
    p=Path(c[key]);c[key]=str(p if p.is_absolute() else self.config_path.parent/p)
    if require and key!='gpuLock' and not Path(c[key]).is_file():raise ValueError('LTX video component missing: '+key+'. Finish the C: video add-on installation.')
   return c
  for key in ['executable','ffmpeg','diffusion','encoder','vae','gpuLock']:
   p=Path(c[key]);c[key]=str(p if p.is_absolute() else self.config_path.parent/p)
   if require and key!='gpuLock' and not Path(c[key]).is_file():raise ValueError('Video component missing: '+key+'. Open Settings → Video creation to download the optional models.')
  return c
 def status(self):
  with self.lock:s=dict(self.state)
  try:c=self.config();s['installed']=True
  except (ValueError,KeyError,OSError):s['installed']=False
  if s['status']=='running' and s.get('id'):
   progress=self.home/(s['id']+'.progress.json')
   if progress.is_file():
    try:
     detail=json.loads(progress.read_text(encoding='utf8'))
     for key in ('message','step','steps'):
      if key in detail:s[key]=detail[key]
    except (OSError,ValueError):pass
   path=self.home/(s['id']+'.log')
   if path.is_file():
    with path.open('rb') as f:f.seek(max(0,path.stat().st_size-10000));tail=f.read().decode('utf8',errors='replace')
    steps=list(re.finditer(r'(\d+)\s*/\s*(\d+)\s*-\s*[\d.]+s/it',tail))
    if steps and s.get('message')=='Creating your video locally…':
     last=steps[-1];a,b=map(int,last.groups());decoder=tail.rfind('wan_vae build cached graph')
     if decoder>=0 and last.start()<decoder:s['message']='Decoding video frames…'
     else:
      s['step']=a;s['steps']=b;s['message']=f'Finishing video frames · {a} of {b}' if decoder>=0 else f'Creating video locally · step {a} of {b}'
  if s.get('started'):s['elapsed']=round(time.time()-s['started'],1)
  return s
 def start(self,body):
  if not isinstance(body,dict):raise ValueError('Video request must be an object.')
  prompt=body.get('prompt');seconds=body.get('seconds',3);quality=body.get('quality','fast')
  if not isinstance(prompt,str) or not prompt.strip() or len(prompt)>2000:raise ValueError('Describe your video in 1–2,000 characters.')
  if type(seconds) is not int or seconds not in (3,5):raise ValueError('Choose a 3- or 5-second clip.')
  if not isinstance(quality,str) or quality not in PROFILES:raise ValueError('Choose Fast or Quality video mode.')
  c=self.config()
  image=None;source=body.get('sourceJob')
  if body.get('image') is not None or source is not None:
   if c.get('engine')!='ltx':raise ValueError('Photo animation requires the LTX video add-on.')
   from video_inputs import normalise_image
   if source is not None:
    if body.get('image') is not None or not isinstance(source,str) or not re.fullmatch('[0-9a-f]{32}',source):raise ValueError('Invalid source photo reference.')
    previous=self.home/(source+'.input.png')
    if not previous.is_file():raise ValueError('The original photo is unavailable. Attach it again.')
    import base64
    image=normalise_image('data:image/png;base64,'+base64.b64encode(previous.read_bytes()).decode('ascii'))
   else:image=normalise_image(body['image'])
  with self.lock:
   if self.state['status'] in ACTIVE:raise ValueError('Wait for the current video job, or stop it first.')
   self.cancelled.clear();job=uuid.uuid4().hex;self.state={'status':'running','message':'Preparing video generation…','id':job,'started':time.time(),'secondsRequested':seconds,'quality':quality,'samplingSteps':8 if c.get('engine')=='ltx' else PROFILES[quality][2]}
   self.state['imageToVideo']=image is not None
   self.worker=threading.Thread(target=self.run,args=(c,prompt,seconds,job,quality,image),daemon=True);self.worker.start()
  return self.status()
 def install(self):
  c=self.config(False)
  if c.get('engine')=='ltx':
   self.config();return self.status()
  manifest=self.config_path.parent/'models-manifest.json'
  if not manifest.is_file():raise ValueError('Video model manifest is missing.')
  records=json.loads(manifest.read_text());needed=sum(r['size'] for r in records if not (self.config_path.parent/'Models'/r['name']).is_file())
  if shutil.disk_usage(self.config_path.parent).free<needed+2*1024**3:raise ValueError('Not enough disk space. Allow 10 GB for the video models and working files.')
  with self.lock:
   if self.state['status'] in ACTIVE:raise ValueError('A video operation is already active.')
   self.cancelled.clear();self.state={'status':'installing','message':'Downloading optional video models…','started':time.time()};self.worker=threading.Thread(target=self.download,args=(records,),daemon=True);self.worker.start()
  return self.status()
 def download(self,records):
  try:
   root=self.config_path.parent/'Models';root.mkdir(exist_ok=True)
   for r in records:
    if not re.fullmatch(r'[A-Za-z0-9_.-]+',r['name']) or not re.fullmatch(r'[a-f0-9]{64}',r['sha256']):raise ValueError('Invalid model manifest.')
    if not r['url'].startswith(('https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/','https://huggingface.co/city96/umt5-xxl-encoder-gguf/resolve/')):raise ValueError('Unapproved model download source.')
    dest=root/r['name'];part=dest.with_suffix(dest.suffix+'.part')
    if dest.is_file():
     if dest.stat().st_size==r['size'] and self.digest(dest)==r['sha256']:continue
     raise ValueError('An existing video model failed verification. Repair it before downloading; it was not overwritten.')
    offset=part.stat().st_size if part.exists() else 0
    req=urllib.request.Request(r['url'],headers={'Range':f'bytes={offset}-'} if offset else {})
    with urllib.request.urlopen(req,timeout=60) as response,part.open('ab' if offset and response.status==206 else 'wb') as f:
     while data:=response.read(4*1024*1024):
      if self.cancelled.is_set():raise InterruptedError('Video download paused. Select Download to resume.')
      f.write(data);self.state['message']=f"Downloading {r['name']} · {f.tell()/r['size']:.0%}"
    self.state['message']='Verifying downloaded model…'
    if part.stat().st_size!=r['size'] or self.digest(part)!=r['sha256']:raise ValueError('Model verification failed. No model was installed.')
    part.replace(dest)
   self.state={'status':'idle','message':'Video models installed and verified.'}
  except InterruptedError as e:self.state={'status':'cancelled','message':str(e)}
  except Exception as e:self.state={'status':'error','message':str(e)}
 @staticmethod
 def digest(path):
  with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
 def output_path(self,job):
  # Preserve historical clips when the optional model runtime moves drives.
  roots=[self.home,Path('F:/YOEAI-Video-Generation/Outputs'),self.config_path.parent/'Outputs']
  return next((root/(job+'.mp4') for root in roots if (root/(job+'.mp4')).is_file()),self.home/(job+'.mp4'))
 def preview_path(self,job):
  if not re.fullmatch('[0-9a-f]{32}',job):raise ValueError('Invalid video reference.')
  source=self.output_path(job)
  if not source.is_file():raise ValueError('Video not found. Reconnect its original drive.')
  self.home.mkdir(parents=True,exist_ok=True);target=self.home/(job+'.preview.webm')
  with self.preview_lock:
   if target.is_file() and target.stat().st_size>1000 and target.stat().st_mtime_ns>=source.stat().st_mtime_ns:return target
   temporary=self.home/(job+'.preview.tmp.webm')
   try:
    c=self.config();result=subprocess.run([c['ffmpeg'],'-v','error','-y','-i',str(source),'-an','-c:v','libvpx-vp9','-deadline','realtime','-cpu-used','8','-crf','30','-b:v','0','-pix_fmt','yuv420p',str(temporary)],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=90,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode or not temporary.is_file() or temporary.stat().st_size<1000:raise ValueError('Could not prepare playback preview. You can still save the MP4.')
    temporary.replace(target);return target
   except subprocess.TimeoutExpired:raise ValueError('Playback preview took too long. Use Save MP4 to open the original.')
   finally:
    if temporary.exists():temporary.unlink()
 def cancel(self):
  self.cancelled.set()
  with self.lock:
   if self.process is not None and self.process.poll() is None:self.terminate_worker()
  return self.status()
 def terminate_worker(self):
  # Windows venv python.exe may launch a child interpreter; stop that owned
  # process tree before releasing the GPU lock and restoring chat.
  import psutil
  try:
   parent=psutil.Process(self.process.pid);targets=parent.children(recursive=True)+[parent]
   for target in reversed(targets):
    try:target.terminate()
    except psutil.NoSuchProcess:pass
   _,alive=psutil.wait_procs(targets,timeout=5)
   for target in alive:
    try:target.kill()
    except psutil.NoSuchProcess:pass
   psutil.wait_procs(alive,timeout=5)
  except psutil.NoSuchProcess:pass
 def shutdown(self):
  self.cancel()
  if self.worker and self.worker.is_alive() and self.worker is not threading.current_thread():self.worker.join(timeout=270)
 def execute(self,args,log,timeout):
  with log.open('a',encoding='utf8') as trace:
   with self.lock:
    if self.cancelled.is_set():raise InterruptedError('Video creation stopped.')
    self.process=subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=trace,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
   try:code=self.process.wait(timeout=timeout)
   except subprocess.TimeoutExpired:self.terminate_worker();self.process.wait(timeout=20);raise ValueError('Video creation timed out. Try a 3-second clip.')
  if self.cancelled.is_set():raise InterruptedError('Video creation stopped.')
  if code:
   progress=log.with_suffix('.progress.json')
   if progress.is_file():
    try:
     detail=json.loads(progress.read_text(encoding='utf8'))
     if detail.get('error'):raise ValueError(str(detail.get('message','Video engine failed.'))[:500])
    except (OSError,json.JSONDecodeError):pass
   raise ValueError('Video engine failed. See the local job log for details.')
 def run(self,c,prompt,seconds,job,quality,image=None):
  handle=None;paused=False;result={};self.home.mkdir(parents=True,exist_ok=True);started=time.time();output=self.home/(job+'.mp4');raw=self.home/(job+'.avi');log=self.home/(job+'.log');frames=seconds*16+1;width,height,steps=PROFILES[quality]
  try:
   lock=Path(c['gpuLock']);lock.parent.mkdir(parents=True,exist_ok=True)
   try:handle=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
   except FileExistsError:raise ValueError('Another image or video job is using the GPU. Wait for it to finish.')
   os.write(handle,str(os.getpid()).encode())
   self.state['message']='Pausing chat to free GPU memory…'
   if self.pause:paused=bool(self.pause())
   seed=int.from_bytes(os.urandom(4),'little')
   fps=24 if c.get('engine')=='ltx' else 16
   if c.get('engine')=='ltx':
    steps=8;request=self.home/(job+'.request.json')
    payload={'prompt':prompt,'seconds':seconds,'width':width,'height':height,'seed':seed,'output':str(output)}
    if image is not None:
     photo=self.home/(job+'.input.png');photo.write_bytes(image);payload['image']=str(photo)
    request.write_text(json.dumps(payload,ensure_ascii=False),encoding='utf8')
    self.state['message']='Loading LTX-Video…';self.execute([c['python'],'-I',c['worker'],'--request',str(request)],log,1800)
   else:
    args=[c['executable'],'-M','vid_gen','--diffusion-model',c['diffusion'],'--t5xxl',c['encoder'],'--vae',c['vae'],'-p',prompt,'-n','blurry, distorted, low quality, subtitles, watermark, static image','-W',str(width),'-H',str(height),'--video-frames',str(frames),'--fps','16','--steps',str(steps),'--cfg-scale','6.0','--flow-shift','3.0','--sampling-method','euler','--seed',str(seed),'--backend','cuda0','--max-vram','cuda0=12','--offload-to-cpu','--flash-attn','off,diffusion=on','--vae-tiling','--temporal-tiling','-t','6','-o',str(raw)]
    self.state['message']='Creating your video locally…';self.execute(args,log,1800)
    if not raw.is_file() or raw.stat().st_size<10000:raise ValueError('The engine produced no usable video.')
    self.state['message']='Saving MP4…';self.execute([c['ffmpeg'],'-hide_banner','-y','-i',str(raw),'-an','-t',str(seconds),'-vf','setsar=1','-c:v','libx264','-preset','fast','-crf','19','-pix_fmt','yuv420p','-movflags','+faststart',str(output)],log,180)
   self.execute([c['ffmpeg'],'-v','error','-i',str(output),'-f','null','-'],log,120)
   if not output.is_file() or output.stat().st_size<10000:raise ValueError('No playable MP4 was created.')
   result={'status':'complete','message':'Video ready.','id':job,'url':'/videogen/output/'+job,'seconds':seconds,'generationSeconds':round(time.time()-started,1),'width':width,'height':height,'fps':fps,'engine':c.get('engine','wan'),'seed':seed,'quality':quality,'samplingSteps':steps,'imageToVideo':image is not None}
  except InterruptedError as e:result={'status':'cancelled','message':str(e),'id':job}
  except Exception as e:result={'status':'error','message':str(e),'id':job}
  finally:
   with self.lock:self.process=None
   if paused and self.resume:
    self.state.update(status='restoring',message='Restoring your chat model…')
    try:self.resume()
    except Exception:result['message']=result.get('message','')+' Chat could not restart; reopen YOEAI.';result['chatRestartFailed']=True
   if handle is not None:
    os.close(handle)
    try:Path(c['gpuLock']).unlink()
    except OSError:pass
   result['totalSeconds']=round(time.time()-started,1)
   (self.home/(job+'.json')).write_text(json.dumps({**result,'prompt':prompt},indent=2),encoding='utf8')
   with self.lock:self.state=result

def handle_request(handler,generator,post=False):
 path=handler.path.split('?',1)[0]
 if not path.startswith('/videogen/'):return False
 if not handler.allowed():handler.json(403,{'error':'Only the local YOEAI interface may use video creation.'});return True
 try:
  if post:
   if handler.headers.get('Origin')!='http://'+handler.headers.get('Host',''):raise ValueError('Use the local YOEAI screen to create videos.')
   if handler.headers.get('Transfer-Encoding'):raise ValueError('Unsupported transfer encoding.')
   length=int(handler.headers.get('Content-Length','0'))
   if not 0<length<=(22*1024**2 if path=='/videogen/create' else 10000):raise ValueError('Invalid video request size.')
   body=json.loads(handler.rfile.read(length))
   if path=='/videogen/create':handler.json(202,generator.start(body))
   elif path=='/videogen/stop':handler.json(200,generator.cancel())
   elif path=='/videogen/install':handler.json(202,generator.install())
   else:handler.json(404,{'error':'Video route not found.'})
  elif path=='/videogen/status':handler.json(200,generator.status())
  elif path.startswith(('/videogen/output/','/videogen/preview/')):
   job=path.rsplit('/',1)[-1]
   if not re.fullmatch('[0-9a-f]{32}',job):raise ValueError('Invalid video reference.')
   preview=path.startswith('/videogen/preview/');p=generator.preview_path(job) if preview else generator.output_path(job)
   if not p.is_file():return handler.json(404,{'error':'Video not found.'}) or True
   size=p.stat().st_size;start=0;end=size-1;partial=False;requested=handler.headers.get('Range')
   if requested:
    match=re.fullmatch(r'bytes=(\d+)-(\d*)',requested)
    if not match:raise ValueError('Unsupported video range.')
    start=int(match[1]);end=min(int(match[2]),size-1) if match[2] else size-1;partial=True
    if start>end:handler.send_response(416);handler.send_header('Content-Range',f'bytes */{size}');handler.end_headers();return True
   handler.send_response(206 if partial else 200);handler.send_header('Content-Type','video/webm' if preview else 'video/mp4');handler.send_header('X-Content-Type-Options','nosniff');handler.send_header('Accept-Ranges','bytes');handler.send_header('Cache-Control','no-store');handler.send_header('Content-Length',str(end-start+1))
   if partial:handler.send_header('Content-Range',f'bytes {start}-{end}/{size}')
   handler.end_headers()
   with p.open('rb') as f:
    f.seek(start);left=end-start+1
    while left:
     data=f.read(min(left,1024*1024));handler.wfile.write(data);left-=len(data)
  else:handler.json(404,{'error':'Video route not found.'})
 except (ValueError,TypeError,KeyError,OSError) as e:handler.json(400,{'error':str(e)})
 return True
