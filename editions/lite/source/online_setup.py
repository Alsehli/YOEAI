"""Single-file Lite setup: pinned downloads, then local-only inference."""

import ctypes,hashlib,json,os,queue,shutil,subprocess,sys,threading,time,urllib.request,zipfile

from pathlib import Path

import tkinter as tk

from tkinter import messagebox,ttk,filedialog

PAYLOAD=Path(getattr(sys,'_MEIPASS',Path(__file__).parent))/'online-payload'

from native_update import data_home,shortcut,update,desktop_folder

DATA=data_home()

OFFLINE_ROOT=None

EVENTS=queue.Queue()

REV='99b43f206bfe6e4e4c311d8fe5bf9b3a9d06d08e'

BASE=f'https://huggingface.co/Jackrong/DeepSeek-V4-Pro-Qwen3.5-9B-MTP-GGUF/resolve/{REV}/'

FILES=[

 ('Models','DeepSeek-V4-Pro-Qwen3.5-9B-MTP-Q4_K_M.gguf',5780092000,'afa0567da6353443c40b2560c20f52ed743a7a105dedf288fb26be00fb78e176',BASE+'DeepSeek-V4-Pro-Qwen3.5-9B-MTP-Q4_K_M.gguf'),

 ('Models','mmproj-F32.gguf',1824061952,'16c2f9c13c28c25e6024413951efe280d77b65cd2273b0f00cec20035e221731',BASE+'mmproj-F32.gguf'),

]

HTTP=urllib.request.build_opener()

def report(text):EVENTS.put(('status',text))

def sha(path):

 with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def valid(path,size,digest):return path.is_file() and path.stat().st_size==size and sha(path)==digest

def download(url,path,size,digest):

 if valid(path,size,digest):report('Reusing verified '+path.name);return path

 if path.exists():path.rename(path.with_name(path.name+'.unverified-'+str(time.time_ns())))

 path.parent.mkdir(parents=True,exist_ok=True);part=path.with_name(path.name+'.part')

 for attempt in range(3):

  offset=part.stat().st_size if part.exists() else 0

  if offset>size:part.rename(part.with_name(part.name+'.unverified-'+str(time.time_ns())));offset=0

  if offset==size:break

  report(('Resuming ' if offset else 'Downloading ')+path.name)

  request=urllib.request.Request(url,headers={'User-Agent':'YOEAI-Lite-Setup/0.2.0','Range':f'bytes={offset}-'} if offset else {'User-Agent':'YOEAI-Lite-Setup/0.2.0'})

  try:

   with HTTP.open(request,timeout=90) as response:

    if not response.geturl().startswith('https://'):raise RuntimeError('Insecure download redirect rejected.')

    if offset and response.status!=206:offset=0

    if response.status==206 and not response.headers.get('Content-Range','').startswith(f'bytes {offset}-'):raise RuntimeError('Unexpected download range.')

    with part.open('ab' if offset else 'wb') as output:

     last=0

     while True:

      block=response.read(2*1024*1024)

      if not block:break

      output.write(block);offset+=len(block)

      if offset>size:raise RuntimeError('Download exceeds pinned file size.')

      if time.monotonic()-last>1:EVENTS.put(('progress',(path.name,offset,size)));last=time.monotonic()

   if offset==size:break

  except Exception:

   if attempt==2:raise

 if not valid(part,size,digest):

  if part.exists():part.rename(part.with_name(part.name+'.unverified-'+str(time.time_ns())))

  raise RuntimeError('Checksum failed for '+path.name+'. Unverified file preserved for diagnosis; no installation was promoted.')

 part.rename(path);return path

def extract_verified(archive,target):

 with zipfile.ZipFile(archive) as z:

  for entry in z.infolist():

   if not (target/entry.filename).resolve().is_relative_to(target.resolve()):raise RuntimeError('Unsafe runtime archive path.')

  z.extractall(target)

def obtain_file(category,name,size,digest,url,cache,offline):

 target=cache/name

 if valid(target,size,digest):report('Reusing verified '+name);return target

 if offline.is_dir():

  source=offline/category/name;report('Verifying offline '+name)

  if not valid(source,size,digest):raise RuntimeError('Offline package file is missing or invalid: '+str(source)+'. No network download was attempted.')

  cache.mkdir(parents=True,exist_ok=True)

  if target.exists():target.rename(target.with_name(target.name+'.unverified-'+str(time.time_ns())))

  staged=cache/(name+'.offline-'+str(time.time_ns()))

  try:os.link(source,staged)

  except OSError:shutil.copy2(source,staged)

  if not valid(staged,size,digest):raise RuntimeError('Offline file copy verification failed: '+name)

  staged.rename(target);return target

 return download(url,target,size,digest)

def verify_payload():

 manifest=json.loads((PAYLOAD/'package-manifest.json').read_text(encoding='utf-8-sig'))

 for item in manifest['files']:

  path=PAYLOAD/item['path']

  if not valid(path,item['size'],item['sha256']):raise RuntimeError('Embedded payload failed verification: '+item['path'])

 return len(manifest['files'])

def find_offline(base):

 base=Path(base)

 candidates=[base,base/'8GB-Lite',base/'YOEAI-Lite',base.parent/'8GB-Lite',base.parent/'YOEAI-Lite']

 for candidate in candidates:

  if (candidate/'Models').is_dir() and (candidate/'Runtime').is_dir():return candidate

 return base/'YOEAI-Lite'



def run_setup(payload=None,offline=None):

 global PAYLOAD,OFFLINE_ROOT

 if payload is not None:PAYLOAD=Path(payload)

 OFFLINE_ROOT=Path(offline) if offline is not None else None

 main()



def install(selected=None,projector=''):

 from model_selection import selected_model

 choice=selected_model(selected,projector) if selected else None

 DATA.mkdir(parents=True,exist_ok=True);verify_payload()

 final=DATA/'App/0.1.0'

 if final.exists():

  report('Updating your existing Lite app; model downloads are skipped.')

  result=update(PAYLOAD,DATA,selection=choice)

  (DATA/'last-update-result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')

  return 'Existing Lite app updated. Your model and history were preserved. The updated app will try the new 16K context once, with recovery if loading fails.'

 if (DATA/'profile.json').exists():raise RuntimeError('A custom Lite profile already exists. It was preserved; this installer will not overwrite it.')

 desktop=desktop_folder()/'YOEAI Lite 2.0.lnk'

 if desktop.exists():raise RuntimeError('An existing Lite shortcut was preserved. Resolve the existing installation before continuing.')

 if shutil.disk_usage(DATA).free<25_000_000_000:raise RuntimeError('At least 25 GB free space is required for a new installation.')

 edge=Path(os.environ.get('PROGRAMFILES(X86)','C:/Program Files (x86)'))/'Microsoft/Edge/Application/msedge.exe'

 if not edge.exists():raise RuntimeError('Microsoft Edge is required.')

 memory=subprocess.check_output(['nvidia-smi','--query-gpu=memory.total','--format=csv,noheader,nounits'],stdin=subprocess.DEVNULL,stderr=subprocess.DEVNULL,text=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=10)

 if float(memory.splitlines()[0])<7500:raise RuntimeError('An NVIDIA GPU with at least 8 GB VRAM is required.')

 cache=DATA/'Downloads';downloads=[];offline=find_offline(OFFLINE_ROOT or Path(sys.executable).parent)

 if not choice:

  for category,name,size,digest,url in FILES:downloads.append((category,obtain_file(category,name,size,digest,url,cache,offline)))

 stage=final.parent/('.setup-'+str(time.time_ns()));stage.mkdir(parents=True)

 shutil.copy2(PAYLOAD/'YOEAILite.exe',stage/'YOEAILite.exe');(stage/'Models').mkdir()

 for category,path in downloads:

  if category=='Models':

   target=stage/'Models'/path.name

   try:os.link(path,target)

   except OSError:shutil.copy2(path,target)

  else:extract_verified(path,stage/'Backend')

 for name in ['Documents','Licenses','Source','Speech','RuntimeSupport','NativeEngine','NativeRuntime']:shutil.copytree(PAYLOAD/name,stage/name)

 from native_payload import check

 check(stage)

 stage.rename(final)

 config=dict(model=str(final/'Models'/FILES[0][1]),projector=str(final/'Models'/FILES[1][1]),inferenceEngine='native',apiPort=8086,uiPort=8087,context=16384,gpuLayers=99)

 if choice:config.update(choice,loadOnDemand=True)

 (DATA/'profile.json').write_text(json.dumps(config,indent=2),encoding='utf-8')

 shortcut(final/'YOEAILite.exe',desktop)

 return 'Installed. Open the YOEAI Lite 2.0 desktop shortcut. Future inference works offline.'

def main():

 window=tk.Tk();window.title('YOEAI Lite 2.0 - Native Setup 2.0.3');window.geometry('760x620')

 tk.Label(window,text='YOEAI Lite 2.0\nText, image understanding, PDF and English voice',font=('Segoe UI',18),pady=15).pack()

 tk.Label(window,text='Setup reuses a complete YOEAI-Lite folder beside this EXE when available.\nOtherwise first setup downloads about 7.60 GB; conversations run locally afterward.\nNVIDIA 8 GB+ VRAM, 16 GB system RAM, Microsoft Edge and 25 GB free SSD space required.\nUnsigned development build: target-PC validation and signing remain pending.',wraplength=640,justify='left').pack()

 model=tk.StringVar();vision=tk.StringVar()

 tk.Label(window,text='Choose a local GGUF model (optional; blank uses the standard package)').pack()

 tk.Entry(window,textvariable=model,width=85).pack()

 def choose_model():

  selected=filedialog.askopenfilename(title='Choose a local language model',filetypes=[('GGUF model','*.gguf')])

  if selected:model.set(selected)

 tk.Button(window,text='Choose model…',command=choose_model).pack()

 tk.Entry(window,textvariable=vision,width=85).pack()

 def choose_vision():

  selected=filedialog.askopenfilename(title='Optional matching vision projector',filetypes=[('GGUF projector','*.gguf')])

  if selected:vision.set(selected)

 tk.Button(window,text='Optional projector…',command=choose_vision).pack()

 tk.Label(window,text='Leave the projector blank for text-only. Models stay in their selected location.').pack()

 selection=['','']

 status=tk.StringVar(value='Ready to install or update.');tk.Label(window,textvariable=status,wraplength=640,pady=14).pack()

 progress=ttk.Progressbar(window,length=610,maximum=100);progress.pack()

 def worker():

  try:EVENTS.put(('done',install(selection[0] or None,selection[1])))

  except Exception as error:

   DATA.mkdir(parents=True,exist_ok=True);(DATA/'online-setup-error.txt').write_text(str(error),encoding='utf-8');EVENTS.put(('error',str(error)))

 accepted=tk.BooleanVar(value=False)

 tk.Checkbutton(window,text='I understand the technical requirements and that this is an unsigned test build.',variable=accepted,wraplength=650).pack(pady=8)

 def begin():

  if not accepted.get():messagebox.showwarning('Please confirm','Review the requirements and tick the confirmation box first.');return

  selection[:]=[model.get().strip(),vision.get().strip()];button.config(state='disabled');threading.Thread(target=worker,daemon=True).start()

 button=tk.Button(window,text='Install / update Lite',command=begin,padx=24,pady=8);button.pack(pady=15)

 def poll():

  while not EVENTS.empty():

   kind,value=EVENTS.get()

   if kind=='status':status.set(value)

   elif kind=='progress':name,current,total=value;status.set(f'{name}: {current/1e9:.2f} / {total/1e9:.2f} GB');progress['value']=100*current/total

   elif kind=='done':progress['value']=100;status.set(value);messagebox.showinfo('Lite setup complete',value);button.config(text='Complete')

   elif kind=='error':status.set('Setup failed.');messagebox.showerror('Lite setup failed',value);button.config(state='normal')

  window.after(150,poll)

 window.after(150,poll);window.mainloop()



def test_native_install(root,models):

 """Exact payload qualification; fresh profile, no shortcuts or model copies."""

 root=Path(root).absolute();models=Path(models).absolute()

 if root.exists():raise ValueError('The test folder already exists and was preserved. Choose a new folder.')

 verify_payload()

 for category,name,size,digest,url in FILES:

  if category!='Models' or not valid(models/name,size,digest):raise ValueError('Existing Lite model files failed verification.')

 from native_payload import check

 hardware=check(PAYLOAD)

 root.mkdir(parents=True);app=root/'App';shutil.copytree(PAYLOAD,app)

 home=root/'Profile/YOEAILite';home.mkdir(parents=True)

 config={'model':str(models/FILES[0][1]),'projector':str(models/FILES[1][1]),'inferenceEngine':'native','apiPort':19086,'uiPort':19087,'context':16384,'gpuLayers':99}

 (home/'profile.json').write_text(json.dumps(config,indent=2),encoding='utf8')

 return {'passed':True,'app':str(app),'profileRoot':str(root/'Profile'),'hardware':hardware,'modelWeightsCopied':False,'shortcutsCreated':False,'cleanWindowsQualified':False}



if __name__=='__main__':

 if '--test-native-install' in sys.argv:

  import argparse

  parser=argparse.ArgumentParser();parser.add_argument('--test-native-install',required=True);parser.add_argument('--models-existing',required=True);parser.add_argument('--report',required=True);args=parser.parse_args()

  try:result=test_native_install(args.test_native_install,args.models_existing)

  except Exception as e:result={'passed':False,'error':str(e)}

  Path(args.report).write_text(json.dumps(result,indent=2),encoding='utf8');sys.exit(0 if result['passed']else 1)

 elif '--self-test-native' in sys.argv:

  # Isolated compiled-binary regression test; never touches the user's installation.

  from native_update import update,shortcut

  import uuid

  root=Path(sys.argv[sys.argv.index('--self-test-native')+1]);root.mkdir(parents=True,exist_ok=True)

  test=root/('fixture-'+uuid.uuid4().hex);data=test/'data';installed=data/'App/0.1.0';installed.mkdir(parents=True);(installed/'Backend').mkdir()

  (installed/'YOEAILite.exe').write_bytes(b'previous fixture executable')

  (installed/'model.gguf').write_bytes(b'fixture model');(installed/'projector.gguf').write_bytes(b'fixture projector')

  config=dict(backend=str(installed/'Backend/llama-server.exe'),model=str(installed/'model.gguf'),projector=str(installed/'projector.gguf'),apiPort=29281,uiPort=29282,context=8192)

  profile=data/'profile.json';profile.write_text(json.dumps(config),encoding='utf-8');before=profile.read_bytes()

  count=verify_payload()

  result=update(PAYLOAD,data,make_shortcut=lambda target:shortcut(target,test/'YOEAI Lite 2.0.lnk'),stopper=lambda exe:None)

  assert profile.read_bytes()==before and sha(installed/'YOEAILite.exe')==sha(PAYLOAD/'YOEAILite.exe')

  assert (installed/'Speech/Runtime/YOEAI-Speech.exe').is_file() and (installed/'Source/assets/read-aloud.js').is_file() and (installed/'Source/assets/chat-pdf.js').is_file()

  (root/'native-selftest.json').write_text(json.dumps(dict(status='PASS',payloadFiles=count,profilePreserved=True,exeChecksumVerified=True,nativeShortcutVerified=Path(result['shortcut']).is_file(),powershellUsed=False,scope='Isolated compiled updater and shortcut; real target-PC installation and GPU inference not tested'),indent=2),encoding='utf-8')

 elif '--verify-payload' in sys.argv:

  count=verify_payload();DATA.mkdir(parents=True,exist_ok=True);(DATA/'online-setup-payload-test.json').write_text(json.dumps(dict(status='PASS',verifiedFiles=count,scope='Embedded setup payload only; no download or installation performed.'),indent=2))

 else:main()
