"""One shared process-local manager, one native worker, private inherited pipes."""
import atexit,json,os,queue,subprocess,sys,threading,time,uuid
from pathlib import Path
class Manager:
 def __init__(self):
  self.worker=None;self.lock=threading.RLock();self.write_lock=threading.Lock();self.messages=None;self.shutting_down=False;self.last_load=None;self.state={'phase':'idle','busy':False,'loaded':False,'progress':0,'error':None,'transport':'private-stdio'}
 def start(self):
  if self.shutting_down:raise RuntimeError('The native engine is shutting down.')
  if self.worker and self.worker.poll()is None:return
  if self.worker:self.close()
  from configuration import APP_DIR,HOME
  if getattr(sys,"frozen",False):APP_DIR=Path(sys.executable).parent
  runtime=Path(os.environ.get('YOEAI_NATIVE_RUNTIME',str(APP_DIR/'NativeRuntime/b11784'))).resolve()
  if not(runtime/'llama.dll').is_file():raise ValueError('The bundled native runtime is missing. Repair the YOEAI installation; no model download is needed.')
  if getattr(sys,'frozen',False):command=[str(APP_DIR/'NativeEngine/YOEAI-Inference.exe')]
  else:command=[sys.executable,'-u','-m','native_ai.worker']
  env=dict(os.environ);env['PYTHONPATH']=str(Path(__file__).parent.parent)
  logs=HOME/'Logs';logs.mkdir(exist_ok=True);self.log_path=logs/('native-'+str(time.time_ns())+'.log');self.log=self.log_path.open('w',encoding='utf8')
  self.messages=queue.Queue(maxsize=4096);self.worker=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.log,text=True,encoding='utf8',bufsize=1,env=env,cwd=str(APP_DIR),creationflags=subprocess.CREATE_NO_WINDOW)
  process=self.worker;messages=self.messages
  from .process_job import WorkerJob
  try:self.job=WorkerJob(process)
  except Exception:
   process.terminate();process.wait(timeout=5);self.log.close();self.worker=None;raise
  def read():
   try:
    for line in process.stdout:messages.put(json.loads(line))
   except Exception as ex:messages.put({'event':'error','error':str(ex)})
   finally:messages.put({'event':'exit','error':'Native worker closed. See '+str(self.log_path)})
  threading.Thread(target=read,daemon=True).start();self.wait_ready(messages)
  self.job.refresh();self.runtime=runtime;self.state.update(phase='ready',loaded=False,error=None,pid=process.pid)
 def wait_ready(self,messages):
  try:
   ready=messages.get(timeout=30)
   if ready.get('event')!='ready':raise RuntimeError(ready.get('error','Native worker did not initialize.'))
  except Exception as ex:
   message='Native worker did not initialize within 30 seconds.' if isinstance(ex,queue.Empty) else str(ex)
   try:self.close()
   finally:self.state.update(loaded=False,busy=False,phase='error',error=message)
   raise RuntimeError(message) from ex
 def send(self,value):
  with self.write_lock:self.worker.stdin.write(json.dumps(value,ensure_ascii=False)+'\n');self.worker.stdin.flush()
 def request(self,op,cancel_event=None,timeout=600,**values):
  with self.lock:
   if cancel_event and cancel_event.is_set():raise InterruptedError('Native request cancelled before starting.')
   self.start()
   if op in ('generate','tokenize') and not self.state['loaded'] and self.last_load:
    list(self.request('load',**self.last_load))
   if op=='load':self.state.update(loaded=False,phase='loading',progress=0,error=None)
   ident=uuid.uuid4().hex;self.state['busy']=True;deadline=time.monotonic()+timeout;cancel_sent=False
   try:
    self.send({'id':ident,'op':op,**values})
    while True:
     if cancel_event and cancel_event.is_set() and not cancel_sent:self.cancel();cancel_sent=True
     if time.monotonic()>deadline:
      self.cancel();self.close();raise TimeoutError('Native operation timed out. The private worker was released; reload the selected model to recover.')
     try:event=self.messages.get(timeout=.2)
     except queue.Empty:continue
     if event.get('event')=='exit':self.state.update(loaded=False,phase='error');raise RuntimeError(event['error'])
     if event.get('id')not in (ident,None):continue
     kind=event.get('event')
     if kind=='progress':self.state.update(progress=event['value'],phase='loading')
     elif kind=='chunk':yield event['value']
     elif kind=='error':raise InterruptedError(event['error'])if event.get('cancelled')else RuntimeError(event['error'])
     elif kind=='done':
      if op=='load':self.last_load=dict(values);self.state.update(event['value']);self.state.update(loaded=True,phase='ready',error=None,progress=1)
      if op=='unload':self.last_load=None;self.state.update(loaded=False,phase='idle')
      yield {'native_result':event.get('value')};break
   except Exception as ex:self.state.update(error=str(ex));raise
   finally:self.state['busy']=False
 def cancel(self):
  if self.worker and self.worker.poll()is None:self.send({'op':'cancel'})
 def close(self):
  if not self.worker:return
  try:self.cancel()
  except (OSError,ValueError):pass  # A dead pipe must not prevent process cleanup.
  with self.lock:
   try:
    if self.worker.poll()is None:self.send({'op':'shutdown'});self.worker.wait(timeout=8)
   except Exception:
    if self.worker.poll()is None:self.worker.terminate();self.worker.wait(timeout=5)
   finally:
    for f in (self.worker.stdin,self.worker.stdout):
     if f:f.close()
    self.log.close();self.worker=None;self.state.update(loaded=False,busy=False,phase='idle')
    if getattr(self,'job',None):self.job.close();self.job=None
 def shutdown(self):
  self.shutting_down=True;self.close()
INSTANCE=Manager();atexit.register(INSTANCE.shutdown)
