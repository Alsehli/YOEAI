"""Retryable pinned MOSS installation, isolated from Turbo and Qwen dependencies."""
import sys,os,json,time,hashlib,urllib.request,concurrent.futures,threading,subprocess,shutil,ctypes
from pathlib import Path

asset=Path(__file__).parent;base=Path(sys.argv[1]).resolve();base.mkdir(parents=True,exist_ok=True);manifest=json.loads((asset/'model-manifest.json').read_text(encoding='utf8'));config_path=base/'config.json'
config=json.loads(config_path.read_text(encoding='utf8')) if config_path.exists() else {'model':'OpenMOSS-Team/MOSS-Image-SFT','revision':manifest['sha'],'modelDirectory':str(base.parent/'Models/MOSS-Image-SFT'),'python':str(base.parent/'Runtime/MOSS-Image/.venv/Scripts/python.exe'),'gpuFraction':.88}
model=Path(config['modelDirectory']);model.mkdir(parents=True,exist_ok=True);runtime=Path(config['python']).parents[2];runtime.mkdir(parents=True,exist_ok=True);lock=threading.RLock();verified=set();done=threading.Event();total=sum(f['size'] for f in manifest['siblings']);statefile=base/'installation.json';started=time.time();lockfile=base/'install.lock'

def alive(pid):
 if os.name!='nt':return False
 handle=ctypes.windll.kernel32.OpenProcess(0x1000,False,pid)
 if handle:ctypes.windll.kernel32.CloseHandle(handle);return True
 return False

if lockfile.exists():
 try:pid=int(lockfile.read_text())
 except ValueError:pid=0
 if pid and alive(pid):raise RuntimeError('Another MOSS installer is still active.')
 lockfile.unlink()
fd=os.open(lockfile,os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.write(fd,str(os.getpid()).encode());os.close(fd)

def save(**values):
 with lock:
  try:state=json.loads(statefile.read_text(encoding='utf8'))
  except (OSError,ValueError):state={}
  state.update(values,updated=time.time(),pid=os.getpid(),directory=str(model),revision=manifest['sha'],totalBytes=total,requiredFiles=len(manifest['siblings']))
  tmp=statefile.with_suffix('.tmp');tmp.write_text(json.dumps(state,indent=2),encoding='utf8')
  for attempt in range(100):
   try:tmp.replace(statefile);break
   except PermissionError:
    if attempt==99:raise
    time.sleep(.02)

def valid(p,f):
 if not p.is_file() or p.stat().st_size!=f['size']:return False
 h=hashlib.sha256() if f.get('lfs') else hashlib.sha1(b'blob '+str(f['size']).encode()+b'\0')
 with p.open('rb') as stream:
  for data in iter(lambda:stream.read(8*1024**2),b''):h.update(data)
 return h.hexdigest()==((f.get('lfs') or {}).get('sha256') or f['blobId'])

def monitor():
 while not done.wait(1):
  count=0
  for f in manifest['siblings']:
   p=model/f['rfilename'];part=p.with_name(p.name+'.part')
   try:count+=min(f['size'],p.stat().st_size if p.is_file() else part.stat().st_size if part.exists() else 0)
   except FileNotFoundError:pass
  save(status='Downloading',downloadedBytes=count,verifiedFiles=len(verified),started=started)

def download(f):
 name=f['rfilename'];p=model/name
 if not p.resolve().is_relative_to(model.resolve()):raise ValueError('Unsafe model manifest path.')
 p.parent.mkdir(parents=True,exist_ok=True);part=p.with_name(p.name+'.part')
 if valid(p,f):verified.add(name);return
 for attempt in range(6):
  try:
   offset=part.stat().st_size if part.exists() else 0
   if offset>f['size']:part.unlink();offset=0
   if offset<f['size']:
    print(f'Downloading {name}; resume offset {offset} bytes',flush=True)
    url='https://huggingface.co/OpenMOSS-Team/MOSS-Image-SFT/resolve/'+manifest['sha']+'/'+name+'?download=true'
    request=urllib.request.Request(url,headers={'Range':f'bytes={offset}-'} if offset else {})
    with urllib.request.urlopen(request,timeout=90) as response:
     if offset and (response.status!=206 or not response.headers.get('Content-Range','').startswith(f'bytes {offset}-')):offset=0
     with part.open('ab' if offset else 'wb') as stream:
      while data:=response.read(4*1024**2):stream.write(data)
   if not valid(part,f):
    if part.exists() and part.stat().st_size>=f['size']:part.unlink()
    raise ValueError('Downloaded size/hash mismatch: '+name)
   part.replace(p);verified.add(name);return
  except Exception:
   if attempt==5:raise
   time.sleep(min(30,2**attempt))

def run(args):subprocess.run(args,check=True,stdin=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))

try:
 missing=sum(f['size'] for f in manifest['siblings'] if not (model/f['rfilename']).exists())
 if shutil.disk_usage(model).free<missing+7*1024**3:raise RuntimeError('Insufficient space for model and isolated CUDA backend.')
 save(status='Downloading',error=None);thread=threading.Thread(target=monitor,daemon=True);thread.start()
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(download,manifest['siblings']))
 done.set();thread.join();save(status='Installing',downloadedBytes=total,verifiedFiles=len(verified),message='All model hashes verified. Installing isolated CUDA dependencies…')
 (base/'model-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
 approval=json.loads((asset/'code-approval.json').read_text(encoding='utf8'))
 for item in approval['files']:
  if hashlib.sha256((model/item['file']).read_bytes()).hexdigest()!=item['sha256']:raise RuntimeError('Pipeline code is not the reviewed version.')
 (base/'code-approval.json').write_text(json.dumps(approval,indent=2),encoding='utf8');(base/'files-verified.json').write_text(json.dumps({'revision':manifest['sha'],'files':len(verified),'bytes':total,'verifiedAt':time.time()}),encoding='utf8')
 python=Path(config['python'])
 if not python.exists():run([sys.executable,'-m','venv',str(python.parents[1])])
 wheel=runtime/'Downloads/torch-2.9.1+cu130-cp313-cp313-win_amd64.whl'
 wheel_sha='47cae56331fdec7f7082aad967b25868cc5f94b203fc273e40346a852aa009dd'
 if wheel.exists():
  h=hashlib.sha256()
  with wheel.open('rb') as f:
   for data in iter(lambda:f.read(8*1024**2),b''):h.update(data)
  if h.hexdigest()!=wheel_sha:raise RuntimeError('Cached CUDA wheel failed the official PyTorch checksum.')
  run([str(python),'-m','pip','install','--no-cache-dir',str(wheel)])
 else:run([str(python),'-m','pip','install','--no-cache-dir','torch==2.9.1','--index-url','https://download.pytorch.org/whl/cu130'])
 run([str(python),'-m','pip','install','--no-cache-dir','diffusers==0.38.0','transformers==5.3.0','accelerate>=1.10','safetensors==0.8.0','Pillow>=10','psutil','wheel'])
 shutil.copytree(asset/'official',runtime/'official',dirs_exist_ok=True)
 run([str(python),'-m','pip','install','--no-deps','--no-build-isolation',str(runtime/'official')])
 run([str(python),'-m','pip','check'])
 check="""import torch,diffusers,transformers,accelerate,safetensors,json,sys,importlib.metadata
from pathlib import Path
assert torch.cuda.is_available(),'CUDA is unavailable'
a=torch.ones((16,16),device='cuda',dtype=torch.bfloat16);assert (a@a)[0,0].item()==16
data={'cudaAvailable':True,'device':torch.cuda.get_device_name(0),'torch':torch.__version__,'cuda':torch.version.cuda,'archList':torch.cuda.get_arch_list(),'diffusers':diffusers.__version__,'transformers':transformers.__version__,'accelerate':accelerate.__version__,'safetensors':safetensors.__version__,'moss-image':importlib.metadata.version('moss-image'),'python':sys.version}
Path(sys.argv[1]).write_text(json.dumps(data,indent=2),encoding='utf8')
from safetensors import safe_open
for p in Path(sys.argv[2]).rglob('*.safetensors'):
 with safe_open(str(p),framework='pt',device='cpu') as f:assert len(f.keys())>0
"""
 run([str(python),'-I','-c',check,str(base/'backend.json'),str(model)])
 config['revision']=manifest['sha'];config_path.write_text(json.dumps(config,indent=2),encoding='utf8');save(status='Installed — awaiting first image verification',message='All model files and CUDA dependencies verified. Ready for the first real generation test.')
except Exception as e:
 done.set();save(status='Error',error=str(e),message=str(e));raise
finally:
 try:lockfile.unlink()
 except OSError:pass
