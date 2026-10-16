"""Opt-in local GGUF workspace. Never rewrites the bundled model configuration."""
import json,os,sys,struct,subprocess,threading,time,socket,http.client,urllib.request,mimetypes,webbrowser,base64
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import unquote,urlsplit
HTTP=urllib.request.build_opener(urllib.request.ProxyHandler({}))
def inspect_gguf(path):
 p=Path(path).expanduser().resolve()
 if p.suffix.lower()!='.gguf' or not p.is_file():raise ValueError('Choose an existing local .gguf file.')
 with p.open('rb') as f:header=f.read(24)
 if len(header)<24 or header[:4]!=b'GGUF':raise ValueError('This file is not a GGUF model.')
 version,tensors,metadata=struct.unpack('<IQQ',header[4:24])
 if version not in (2,3) or not tensors or metadata>100000:raise ValueError('Unsupported or invalid GGUF header.')
 return str(p)
def validated(value):
 model=inspect_gguf(value['model']);projector=inspect_gguf(value['projector']) if value.get('projector','').strip() else ''
 context=int(value['context']);layers=int(value['gpuLayers'])
 if context not in (2048,4096,8192,16384,32768) or not 0<=layers<=999:raise ValueError('Invalid context or GPU layer setting.')
 name=value.get('name','').strip()
 if not 1<=len(name)<=80:raise ValueError('Enter a profile name (1–80 characters).')
 return dict(name=name,model=model,projector=projector,context=context,gpuLayers=layers)
def launch(entry):
 args=[sys.executable]+([] if getattr(sys,'frozen',False) else [str(entry)])+['--developer-mode']
 subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
class Workspace:
 def __init__(self,backend,ui,home,port):
  self.backend=Path(backend);self.ui=Path(ui);self.home=Path(home)/'DeveloperMode';self.home.mkdir(parents=True,exist_ok=True);self.port=port;self.api=port+1;self.process=None;self.server=None;self.profile=None;self.lock=threading.RLock()
 def request(self,path,body=None):
  req=urllib.request.Request(f'http://127.0.0.1:{self.api}'+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json'})
  with HTTP.open(req,timeout=180) as r:return json.load(r)
 def stop(self):
  if self.server:self.server.shutdown();self.server.server_close();self.server=None
  if self.process and self.process.poll() is None:
   self.process.terminate()
   try:self.process.wait(timeout=15)
   except subprocess.TimeoutExpired:raise RuntimeError('Custom model is still closing. Default services were not touched.')
  self.process=None;self.profile=None
 def test(self,value):
  value=validated(value)
  if not self.backend.is_file():raise ValueError('Installed llama-server.exe could not be found.')
  self.stop()
  with socket.socket() as s:s.bind(('127.0.0.1',self.api))
  args=[str(self.backend),'-m',value['model'],'--host','127.0.0.1','--port',str(self.api),'-c',str(value['context']),'-ngl',str(value['gpuLayers']),'-np','1','-b','128','-ub','64','--alias','deepseek-local']
  if value['projector']:args+=['--mmproj',value['projector'],'--no-mmproj-offload']
  self.log=self.home/('model-'+time.strftime('%Y%m%d-%H%M%S')+'.log')
  with self.log.open('w',encoding='utf-8') as log:self.process=subprocess.Popen(args,cwd=str(self.backend.parent),stdin=subprocess.DEVNULL,stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
  start=time.monotonic()
  try:
   while time.monotonic()-start<240:
    if self.process.poll() is not None:raise RuntimeError('Model load failed. See '+str(self.log))
    try:
     if self.request('/health').get('status')=='ok':break
    except Exception:pass
    time.sleep(.3)
   else:raise RuntimeError('Model loading timed out. Try fewer GPU layers or a smaller model/context.')
   answer=self.request('/v1/chat/completions',{'model':'deepseek-local','messages':[{'role':'user','content':'Say hello.'}],'max_tokens':128,'stream':False,'chat_template_kwargs':{'enable_thinking':False}})
   if not answer.get('choices') or not answer['choices'][0].get('message',{}).get('content','').strip():raise RuntimeError('The model did not return a chat completion. Its architecture/template may be unsupported.')
   self.profile=value
   return {'status':'PASS','loadAndTextSeconds':round(time.monotonic()-start,2),'profile':value,'vision':'NOT TESTED','response':answer['choices'][0]['message'].get('content',''),'log':str(self.log)}
  except Exception:self.stop();raise
 def vision_test(self,image):
  if not self.profile or not self.profile['projector']:raise ValueError('Test a profile with its compatible projector first.')
  p=Path(image)
  if p.suffix.lower() not in ('.png','.jpg','.jpeg','.webp') or p.stat().st_size>10*1024*1024:raise ValueError('Choose a PNG, JPEG or WebP under 10 MB.')
  data='data:'+mimetypes.guess_type(str(p))[0]+';base64,'+base64.b64encode(p.read_bytes()).decode()
  answer=self.request('/v1/chat/completions',{'messages':[{'role':'user','content':[{'type':'text','text':'Briefly describe this image.'},{'type':'image_url','image_url':{'url':data}}]}],'max_tokens':100,'stream':False,'chat_template_kwargs':{'enable_thinking':False}})
  return answer['choices'][0]['message']['content']
 def activate(self):
  if not self.profile or self.process.poll() is not None:raise RuntimeError('Test this profile successfully before opening chat.')
  workspace=self
  class Handler(BaseHTTPRequestHandler):
   def log_message(self,*a):pass
   def allowed(self):return self.headers.get('Host')==f'127.0.0.1:{workspace.port}' and self.headers.get('Origin',f'http://127.0.0.1:{workspace.port}')==f'http://127.0.0.1:{workspace.port}'
   def reply(self,status,value,kind='application/json'):
    body=value if isinstance(value,bytes) else json.dumps(value).encode();self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(body)));self.send_header('X-Content-Type-Options','nosniff');self.send_header('Cache-Control','no-store');self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'");self.end_headers();self.wfile.write(body)
   def do_GET(self):
    if not self.allowed():return self.reply(403,{'error':'Local workspace only.'})
    route=unquote(urlsplit(self.path).path)
    if route=='/status':
     gpu={'used':None,'total':None,'util':None,'temp':None}
     try:
      raw=subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,memory.total,utilization.gpu,temperature.gpu','--format=csv,noheader,nounits'],text=True,timeout=5,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));gpu=dict(zip(gpu,[float(x) for x in raw.splitlines()[0].split(',')]))
     except Exception:pass
     return self.reply(200,dict(gpu,status='ok' if workspace.process.poll() is None else 'offline',model=workspace.profile['model'],context=workspace.profile['context'],changing=False))
    if route=='/':
     html=(workspace.ui/'ui.html').read_text(encoding='utf-8').replace('</body>',"<script>document.title='Developer Mode · YOEAI';document.getElementById('apply').disabled=true;document.getElementById('apply').title='Change context in Developer Mode settings';document.getElementById('context').disabled=true;</script></body>")
     return self.reply(200,html.encode(),'text/html; charset=utf-8')
    if route.startswith('/assets/'):
     file=(workspace.ui/route.lstrip('/')).resolve();base=(workspace.ui/'assets').resolve()
     if file.is_relative_to(base) and file.is_file() and file.suffix.lower() in ('.css','.js','.png','.svg','.ico','.ttf'):return self.reply(200,file.read_bytes(),mimetypes.guess_type(str(file))[0] or 'application/octet-stream')
    return self.reply(404,{'error':'Not found'})
   def do_POST(self):
    if not self.allowed() or self.headers.get('Origin')!=f'http://127.0.0.1:{workspace.port}':return self.reply(403,{'error':'Local workspace only.'})
    if self.path!='/v1/chat/completions':return self.reply(403,{'error':'Use the Developer Mode settings window. PC control is unavailable.'})
    try:
     size=int(self.headers.get('Content-Length','0'))
     if self.headers.get('Transfer-Encoding') or not 0<size<=25000000:raise ValueError('Invalid request size.')
     body=json.loads(self.rfile.read(size));payload={k:body[k] for k in ('messages','stream','stream_options','temperature','max_tokens') if k in body};payload['model']='deepseek-local';payload['chat_template_kwargs']={'enable_thinking':False};payload['max_tokens']=min(int(payload.get('max_tokens',512)),2048)
     if not isinstance(payload.get('messages'),list):raise ValueError('Messages are required.')
     for message in payload['messages']:
      if isinstance(message.get('content'),list):
       for item in message['content']:
        if item.get('type')=='image_url' and (not workspace.profile['projector'] or not item.get('image_url',{}).get('url','').startswith('data:image/')):raise ValueError('Vision requires a compatible tested projector and an uploaded image.')
     conn=http.client.HTTPConnection('127.0.0.1',workspace.api,timeout=180);conn.request('POST','/v1/chat/completions',json.dumps(payload),{'Content-Type':'application/json'});r=conn.getresponse();self.send_response(r.status);self.send_header('Content-Type',r.getheader('Content-Type','application/json'));self.send_header('Connection','close');self.end_headers();self.close_connection=True
     try:
      while True:
       chunk=r.read1(8192)
       if not chunk:break
       self.wfile.write(chunk);self.wfile.flush()
     finally:conn.close()
    except (BrokenPipeError,ConnectionResetError):pass
    except Exception as e:self.reply(400,{'error':str(e)})
  if not self.server:self.server=ThreadingHTTPServer(('127.0.0.1',self.port),Handler);threading.Thread(target=self.server.serve_forever,daemon=True).start()
  return f'http://127.0.0.1:{self.port}/'
def main(app_dir,default,home,lite=False,ui_dir=None):
 import tkinter as tk
 from tkinter import ttk,filedialog,messagebox
 app_dir=Path(app_dir);home=Path(home);ui_dir=Path(ui_dir or app_dir)
 backend=Path(default.get('backend',app_dir/'backend/llama-server.exe'))
 if not backend.is_file() and not lite:backend=Path('C:/AI/llama.cpp/llama-server.exe')
 work=Workspace(backend,ui_dir,home,18090 if lite else 18092);profiles=work.home/'profiles.json'
 saved=json.loads(profiles.read_text()) if profiles.exists() else []
 window=tk.Tk();window.title(('Lite' if lite else 'YOEAI')+' · Developer Mode');window.geometry('850x730');window.configure(bg='#0B0F19')
 style=ttk.Style();style.theme_use('clam');style.configure('.',background='#151D2B',foreground='#F8FAFC',fieldbackground='#202B3C',font=('Segoe UI',10));style.configure('TButton',padding=9);style.configure('TEntry',padding=6)
 panel=ttk.Frame(window,padding=24);panel.pack(fill='both',expand=True)
 ttk.Label(panel,text='Developer Mode',font=('Segoe UI',20,'bold')).pack(anchor='w')
 ttk.Label(panel,text='Optional local GGUF workspace · bundled model and chat history remain unchanged.',wraplength=780).pack(anchor='w',pady=(6,12))
 enabled=tk.BooleanVar(value=False);fields={};controls=[]
 ttk.Checkbutton(panel,text='Enable Developer Mode for this session',variable=enabled,command=lambda:state()).pack(anchor='w',pady=8)
 selector=ttk.Combobox(panel,values=[p['name'] for p in saved],state='readonly');selector.pack(fill='x',pady=6)
 def load_profile(_=None):
  found=next((p for p in saved if p['name']==selector.get()),None)
  if found:
   for key,var in fields.items():var.set(found.get(key,''))
 selector.bind('<<ComboboxSelected>>',load_profile)
 for key,label,value in [('name','Profile name','My custom model'),('model','GGUF model',default.get('model','')),('projector','Optional vision projector GGUF (leave empty for text only)',default.get('projector','')),('context','Context tokens',2048),('gpuLayers','GPU layers (0 = CPU; 99 = attempt full offload)',0)]:
  ttk.Label(panel,text=label).pack(anchor='w',pady=(8,2));row=ttk.Frame(panel);row.pack(fill='x');var=tk.StringVar(value=str(value));fields[key]=var
  entry=ttk.Entry(row,textvariable=var);entry.pack(side='left',fill='x',expand=True);controls.append(entry)
  if key in ('model','projector'):
   def browse(v=var):
    file=filedialog.askopenfilename(parent=window,filetypes=[('GGUF files','*.gguf')])
    if file:v.set(file)
   button=ttk.Button(row,text='Browse…',command=browse);button.pack(side='right',padx=(8,0));controls.append(button)
 ttk.Label(panel,text='Only architectures supported by your installed llama.cpp can load. CPU testing avoids competing with the default GPU model. Large models may need substantial RAM. Vision compatibility must be tested separately.',wraplength=780).pack(anchor='w',pady=12)
 output=tk.Text(panel,height=5,bg='#101725',fg='#94A3B8',wrap='word',font=('Consolas',10));output.pack(fill='both',expand=True)
 def log(text):output.insert('end',text+'\n');output.see('end')
 busy=False;tested=None
 def state():
  for c in controls:c.configure(state='normal' if enabled.get() and not busy else 'disabled')
 def task(action):
  nonlocal busy,tested
  if busy or not enabled.get():return
  busy=True;state();values={k:v.get() for k,v in fields.items()}
  def runner():
   nonlocal busy,tested
   try:
    if action=='test':
     result=work.test(values);tested=validated(values);(work.home/'last-test.json').write_text(json.dumps(result,indent=2));message='PASS: model loaded and text inference succeeded. Vision NOT TESTED. '+str(result['loadAndTextSeconds'])+' seconds.'
    elif action=='save':
     value=validated(values);saved[:]=[p for p in saved if p['name']!=value['name']]+[value];profiles.write_text(json.dumps(saved,indent=2));window.after(0,lambda:selector.configure(values=[p['name'] for p in saved]));message='Profile saved. Model files were not copied.'
    elif action=='open':
     if validated(values)!=tested:raise ValueError('Test the current settings before opening chat.')
     webbrowser.open(work.activate());message='Developer chat opened. Keep this window open. Close it to stop only the custom workspace.'
    else:raise ValueError('Unknown action')
    window.after(0,lambda m=message:log(m))
   except Exception as error:window.after(0,lambda m=str(error):log('FAILED: '+m))
   finally:busy=False;window.after(0,state)
  threading.Thread(target=runner,daemon=True).start()
 row=ttk.Frame(panel);row.pack(fill='x',pady=(12,0))
 for label,action in [('Save profile','save'),('Test model','test'),('Open tested chat','open')]:
  button=ttk.Button(row,text=label,command=lambda a=action:task(a));button.pack(side='left',padx=(0,8));controls.append(button)
 def vision():
  if busy or not enabled.get():return
  file=filedialog.askopenfilename(filetypes=[('Images','*.png *.jpg *.jpeg *.webp')])
  if not file:return
  def run():
   try:message='Vision response (check against your image): '+work.vision_test(file)
   except Exception as e:message='Vision FAILED: '+str(e)
   window.after(0,lambda:log(message))
  threading.Thread(target=run,daemon=True).start()
 button=ttk.Button(row,text='Test vision…',command=vision);button.pack(side='left');controls.append(button)
 def close():
  if busy:messagebox.showinfo('Working','Wait for the model test to finish before closing.');return
  work.stop();window.destroy()
 ttk.Button(panel,text='Return to bundled model / close Developer Mode',command=close).pack(fill='x',pady=(10,0));window.protocol('WM_DELETE_WINDOW',close);state();window.mainloop()
