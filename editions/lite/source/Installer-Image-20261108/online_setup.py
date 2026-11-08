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
CANCEL=threading.Event()
class SetupCancelled(Exception):pass
def check_cancel():
 if CANCEL.is_set():raise SetupCancelled('Setup cancelled safely. Existing apps, models and history were preserved.')
def copy_checked(source,target):
 check_cancel()
 with open(source,'rb') as incoming,open(target,'wb') as outgoing:
  while chunk:=incoming.read(4*1024**2):check_cancel();outgoing.write(chunk)
 shutil.copystat(source,target)
 return target


REV='99b43f206bfe6e4e4c311d8fe5bf9b3a9d06d08e'

BASE=f'https://huggingface.co/Jackrong/DeepSeek-V4-Pro-Qwen3.5-9B-MTP-GGUF/resolve/{REV}/'

FILES=[

 ('Models','DeepSeek-V4-Pro-Qwen3.5-9B-MTP-Q4_K_M.gguf',5780092000,'afa0567da6353443c40b2560c20f52ed743a7a105dedf288fb26be00fb78e176',BASE+'DeepSeek-V4-Pro-Qwen3.5-9B-MTP-Q4_K_M.gguf'),

 ('Models','mmproj-F32.gguf',1824061952,'16c2f9c13c28c25e6024413951efe280d77b65cd2273b0f00cec20035e221731',BASE+'mmproj-F32.gguf'),

]

HTTP=urllib.request.build_opener()

def report(text):EVENTS.put(('status',text))

def sha(path):

 with path.open('rb') as f:
  h=hashlib.sha256()
  while chunk:=f.read(4*1024**2):check_cancel();h.update(chunk)
  return h.hexdigest()

def valid(path,size,digest):return path.is_file() and path.stat().st_size==size and sha(path)==digest

def download(url,path,size,digest):

 if valid(path,size,digest):report('Reusing verified '+path.name);return path

 if path.exists():path.rename(path.with_name(path.name+'.unverified-'+str(time.time_ns())))

 path.parent.mkdir(parents=True,exist_ok=True);part=path.with_name(path.name+'.part')

 for attempt in range(3):
  check_cancel()

  offset=part.stat().st_size if part.exists() else 0

  if offset>size:part.rename(part.with_name(part.name+'.unverified-'+str(time.time_ns())));offset=0

  if offset==size:break

  report(('Resuming ' if offset else 'Downloading ')+path.name)

  request=urllib.request.Request(url,headers={'User-Agent':'YOEAI-Lite-Setup/0.2.0','Range':f'bytes={offset}-'} if offset else {'User-Agent':'YOEAI-Lite-Setup/0.2.0'})

  try:

   with HTTP.open(request,timeout=15) as response:

    if not response.geturl().startswith('https://'):raise RuntimeError('Insecure download redirect rejected.')

    if offset and response.status!=206:offset=0

    if response.status==206 and not response.headers.get('Content-Range','').startswith(f'bytes {offset}-'):raise RuntimeError('Unexpected download range.')

    with part.open('ab' if offset else 'wb') as output:

     last=0

     while True:

      check_cancel();block=response.read(256*1024)

      if not block:break

      output.write(block);offset+=len(block)

      if offset>size:raise RuntimeError('Download exceeds pinned file size.')

      if time.monotonic()-last>1:EVENTS.put(('progress',(path.name,offset,size)));last=time.monotonic()

   if offset==size:break

  except SetupCancelled:raise

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



def install(selected=None,projector='',allow_download=False,defer_model=False):
 from model_selection import selected_model
 from setup_support import StagedInstall
 choice=selected_model(selected,projector) if selected else None
 check_cancel();DATA.mkdir(parents=True,exist_ok=True);report('Checking installer files…');verify_payload()
 final=DATA/'App/0.1.0'
 if final.exists():
  check_cancel();EVENTS.put(('updating','Finishing the existing Lite update safely. Please keep setup open.'))
  result=update(PAYLOAD,DATA,selection=choice)
  (DATA/'last-update-result.json').write_text(json.dumps(result,indent=2),encoding='utf8')
  return 'Updated. Your existing model and conversation history were preserved.'
 if (DATA/'profile.json').exists():raise RuntimeError('An existing Lite profile was preserved. Use its existing installation; no settings were overwritten.')
 if not choice and not allow_download and not defer_model:raise ValueError('Choose your local GGUF file, or explicitly allow the standard-model download.')
 desktop=desktop_folder()/'YOEAI Lite 2.0.lnk'
 if desktop.exists():raise RuntimeError('A Lite shortcut already exists. Open the existing app or resolve that installation first; it was preserved.')
 manifest=json.loads((PAYLOAD/'package-manifest.json').read_text(encoding='utf8'))
 required=sum(row['size'] for row in manifest['files'])+2*1024**3+(0 if choice or defer_model else sum(row[2] for row in FILES))
 if shutil.disk_usage(DATA).free<required:raise RuntimeError('Not enough storage. This setup needs about '+str(round(required/1024**3,1))+' GB free with your selected options.')
 edge=Path(os.environ.get('PROGRAMFILES(X86)','C:/Program Files (x86)'))/'Microsoft/Edge/Application/msedge.exe'
 if not edge.exists():raise RuntimeError('Microsoft Edge is required for the Lite interface.')
 memory=subprocess.check_output(['nvidia-smi','--query-gpu=memory.total','--format=csv,noheader,nounits'],stdin=subprocess.DEVNULL,stderr=subprocess.DEVNULL,text=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=10)
 if max(float(row) for row in memory.splitlines() if row.strip())<7500:raise RuntimeError('Lite requires a compatible NVIDIA GPU with at least 8 GB VRAM.')
 cache=DATA/'Downloads';downloads=[];offline=find_offline(OFFLINE_ROOT or Path(sys.executable).parent)
 if not choice and not defer_model:
  for category,name,size,digest,url in FILES:
   check_cancel();downloads.append((category,obtain_file(category,name,size,digest,url,cache,offline)))
 with StagedInstall(final,DATA/'profile.json',state_file=True) as transaction:
  stage=transaction.app_stage;report('Installing application files…');copy_checked(PAYLOAD/'YOEAILite.exe',stage/'YOEAILite.exe');(stage/'Models').mkdir()
  for category,path in downloads:
   check_cancel();target=stage/'Models'/path.name
   if category=='Models':
    try:os.link(path,target)
    except OSError:copy_checked(path,target)
   else:extract_verified(path,stage/'Backend')
  for name in ['Documents','Licenses','Source','Speech','SearchRuntime','RuntimeSupport','NativeEngine','NativeRuntime']:
   check_cancel();report('Installing '+name+'…');shutil.copytree(PAYLOAD/name,stage/name,copy_function=copy_checked)
  check_cancel();report('Checking the native CUDA runtime…')
  from native_payload import check
  check(stage);check_cancel()
  config=dict(model=str(final/'Models'/FILES[0][1]),projector=str(final/'Models'/FILES[1][1]),inferenceEngine='native',apiPort=8086,uiPort=8087,context=16384,gpuLayers=99)
  if defer_model and not choice:config.update(model=str(DATA/'Models/Choose-a-model.gguf'),projector='',loadOnDemand=True,setupModelPending=True)
  if choice:config.update(choice,loadOnDemand=True)
  (transaction.state_stage/'profile.json').write_text(json.dumps(config,indent=2),encoding='utf8')
  check_cancel();report('Finishing installation…');transaction.commit()
 try:shortcut(final/'YOEAILite.exe',desktop)
 except Exception:return 'Installed. The desktop shortcut could not be created. Use Open YOEAI below; your app and profile are intact.'
 return 'Installed. Your local model stays in its selected location. Open YOEAI when ready.'

def main():
 window=tk.Tk();window.title('YOEAI 2.0 — Lite Setup');window.geometry('760x650');window.minsize(700,600);window.configure(bg='#f3f7fd')
 style=ttk.Style(window);style.theme_use('clam');style.configure('TFrame',background='#f3f7fd');style.configure('TLabel',background='#f3f7fd',foreground='#172337',font=('Segoe UI',10));style.configure('TCheckbutton',background='#f3f7fd',font=('Segoe UI',10));style.configure('TButton',font=('Segoe UI',10),padding=8)
 content=ttk.Frame(window,padding=24);content.pack(fill='both',expand=True)
 head=ttk.Frame(content);head.pack(fill='x')
 try:
  fox=tk.PhotoImage(file=str(PAYLOAD/'Source/assets/yoeai-icon.png'));fox=fox.subsample(max(1,fox.width()//64));window.iconphoto(True,fox);brand=ttk.Label(head,image=fox);brand.image=fox;brand.pack(side='left',padx=(0,14))
 except tk.TclError:pass
 ttk.Label(head,text='YOEAI 2.0',font=('Segoe UI',26,'bold')).pack(anchor='w');ttk.Label(head,text='Lite · 8 GB GPU  /  Your space to think.').pack(anchor='w',pady=(0,16))
 ttk.Label(content,text='One setup. Your models and conversations stay on your PC.',font=('Segoe UI',14,'bold')).pack(anchor='w')
 ttk.Label(content,text='Windows x64 · NVIDIA 8 GB+ · 16 GB RAM · Microsoft Edge.\nUnsigned preview. Optional creative and speech components require separate setup.',wraplength=680).pack(anchor='w',pady=12)
 model=tk.StringVar();vision=tk.StringVar();download_allowed=tk.BooleanVar(value=False);accepted=tk.BooleanVar(value=False)
 controls=[]
 def field(label,variable,title):
  ttk.Label(content,text=label).pack(anchor='w');row=ttk.Frame(content);row.pack(fill='x',pady=(4,10));entry=ttk.Entry(row,textvariable=variable);entry.pack(side='left',fill='x',expand=True)
  def browse():
   selected=filedialog.askopenfilename(parent=window,title=title,filetypes=[('GGUF files','*.gguf')])
   if selected:variable.set(selected)
  button=ttk.Button(row,text='Browse…',command=browse);button.pack(side='left',padx=(8,0));controls.extend([entry,button])
 from model_downloads import show as show_model_downloads
 ttk.Button(content,text='Model downloads…',command=lambda:show_model_downloads(window)).pack(anchor='w',pady=(0,8))
 field('Local language model (.gguf)',model,'Choose your local language model')
 field('Optional matching vision projector — leave blank for text only',vision,'Choose a matching vision projector')
 download_box=ttk.Checkbutton(content,text='Allow the standard-model download (about 7.6 GB) if no local model is selected.',variable=download_allowed);download_box.pack(anchor='w');controls.append(download_box)
 agreement=ttk.Checkbutton(content,text='I reviewed the requirements and understand this is an unsigned preview.',variable=accepted);agreement.pack(anchor='w',pady=12);controls.append(agreement)
 status=tk.StringVar(value='Choose a GGUF now, or install and select one later in Settings.');ttk.Label(content,textvariable=status,wraplength=680).pack(anchor='w',pady=8)
 progress=ttk.Progressbar(content,maximum=100,mode='indeterminate');progress.pack(fill='x',pady=6)
 actions=ttk.Frame(content);actions.pack(side='bottom',fill='x',pady=(12,0));running=False;completed=False;selection=None
 button=ttk.Button(actions,text='Install / update Lite');button.pack(side='right');close_button=ttk.Button(actions,text='Close');close_button.pack(side='left')
 def ready(*unused):
  if not running and not completed:button.configure(state='normal' if accepted.get() else 'disabled')
 def worker():
  try:EVENTS.put(('done',install(selection[0] or None,selection[1],selection[2],defer_model=not selection[0] and not selection[2])))
  except Exception as error:
   try:DATA.mkdir(parents=True,exist_ok=True);(DATA/'online-setup-error.txt').write_text(str(error),encoding='utf8')
   except OSError:pass
   EVENTS.put(('cancelled' if isinstance(error,SetupCancelled) else 'error',str(error)))
 def begin():
  nonlocal running,selection
  if running:return
  if completed:os.startfile(DATA/'App/0.1.0/YOEAILite.exe');return
  if not accepted.get():return
  CANCEL.clear();selection=(model.get().strip(),vision.get().strip(),download_allowed.get());running=True
  for control in controls:control.configure(state='disabled')
  button.configure(state='disabled');close_button.configure(text='Cancel',state='normal');progress.configure(mode='indeterminate');progress.start(12)
  threading.Thread(target=worker,daemon=True).start()
 def close():
  if running:CANCEL.set();status.set('Stopping at a safe checkpoint. Please keep setup open.');close_button.configure(state='disabled')
  else:window.destroy()
 button.configure(command=begin);close_button.configure(command=close);window.protocol('WM_DELETE_WINDOW',close)
 def poll():
  nonlocal running,completed
  try:
   while True:
    kind,value=EVENTS.get_nowait()
    if kind=='status':status.set(value)
    elif kind=='updating':status.set(value);close_button.configure(state='disabled')
    elif kind=='progress':
     name,current,total=value;progress.stop();progress.configure(mode='determinate');progress['value']=100*current/max(1,total);status.set(f'{name}: {current/1e9:.2f} / {total/1e9:.2f} GB')
    else:
     running=False;progress.stop();close_button.configure(text='Close',state='normal');status.set(value)
     if kind=='done':completed=True;progress.configure(mode='determinate');progress['value']=100;button.configure(text='Open YOEAI',state='normal')
     else:
      CANCEL.clear()
      for control in controls:control.configure(state='normal')
      button.configure(text='Install / update Lite');ready()
      if kind=='error':messagebox.showerror('Setup stopped safely',value+'\nCorrect the choice and try again. Existing models and history were preserved.',parent=window)
  except queue.Empty:pass
  window.after(150,poll)
 for variable in (model,download_allowed,accepted):variable.trace_add('write',ready)
 ready();poll()
 if '--preview-report' in sys.argv:
  def preview():
   path=Path(sys.argv[sys.argv.index('--preview-report')+1]);window.update_idletasks();report={'agreementInitiallyUnchecked':not accepted.get(),'downloadInitiallyUnchecked':not download_allowed.get(),'initialInstallDisabled':str(button['state'])=='disabled','window':[window.winfo_width(),window.winfo_height()],'actionBarInWindow':actions.winfo_rooty()+actions.winfo_height()<=window.winfo_rooty()+window.winfo_height() and button.winfo_height()>=30}
   accepted.set(True);model.set('test.gguf');window.update_idletasks();report['enabledAfterExplicitChoices']=str(button['state'])=='normal'
   try:
    from PIL import ImageGrab
    ImageGrab.grab(window=window.winfo_id()).save(path.with_suffix('.png'))
   except Exception as error:report['screenshotError']=type(error).__name__
   path.write_text(json.dumps(report,indent=2),encoding='utf8');window.destroy()
  window.after(800,preview)
 window.mainloop()

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
