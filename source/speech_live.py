"""Fast-mode-only Pro dictation, sharing GPU without unloading the 9B engine."""
import json,threading,uuid,time
from speech_input import Dictation,ACTIVE

class LiveDictation(Dictation):
 def fast_only(self):
  from configuration import read_config
  from model_modes import reconcile_running
  if read_config().get('modelMode')!='fast' or reconcile_running()!='fast':raise ValueError('Live Pro dictation is available in Fast · 9B mode only. Select Fast mode first.')
 def start(self,approved=False):
  if approved is not True:raise ValueError('Activate the microphone explicitly before recording.')
  c=self.settings();self.fast_only()
  from mini_agents import GATE
  with self.lock:
   if self.state['status'] in ACTIVE:raise ValueError('Stop or cancel the current recording first.')
   if not GATE.acquire(blocking=False):raise ValueError('Finish the active AI task before dictating.')
   self.cancelled.clear();self.finished.clear();self.stop_requested=False
   self.state={'status':'starting','id':uuid.uuid4().hex,'message':'Preparing Pro voice input · Fast 9B stays loaded…'}
   threading.Thread(target=self.run_live,args=(c,),daemon=True,name='YOE-Live-Dictation').start();return self.status()
 def stop(self):
  with self.lock:
   if self.state['status'] not in ('starting','recording'):raise ValueError('No active recording.')
   self.stop_requested=True
   if self.worker and self.worker.poll() is None and self.state['status']=='recording':
    self.worker.stdin.write('{"op":"stop"}\n');self.worker.stdin.flush();self.update(status='transcribing',message='Finishing your last words…')
   return self.status()
 def run_live(self,c):
  from mini_agents import GATE
  import queue
  result=None
  try:
   self.fast_only()
   from model_modes import media_busy
   if media_busy():raise ValueError('Wait for image or video generation to finish.')
   if self.worker is None or self.worker.poll() is not None:
    self.messages=queue.Queue();self.worker=self.launch([c['model']],c)
    threading.Thread(target=self.reader,args=(self.worker,self.messages),daemon=True).start()
    ready=self.reply(90)
    if ready.get('status')!='ready':raise ValueError(ready.get('message','Pro could not load.'))
   if self.stop_requested:raise InterruptedError()
   self.check();self.worker.stdin.write('{"op":"live"}\n');self.worker.stdin.flush()
   while True:
    value=self.reply(90)
    if value.get('status') in ('complete','error'):result=value;break
    if value.get('status')=='recording':
     self.update(**value)
     if self.stop_requested:
      self.worker.stdin.write('{"op":"stop"}\n');self.worker.stdin.flush();self.update(status='transcribing',message='Finishing your last words…')
   if result.get('status')=='error':raise ValueError(result['message'])
  except InterruptedError:result={'status':'cancelled','message':'Dictation cancelled.'}
  except Exception as ex:result={'status':'error','message':str(ex)[:1000]}
  finally:
   if not result or result.get('status')!='complete':
    p=self.worker
    if p and p.poll() is None:p.terminate();p.wait(timeout=10)
    self.worker=None
   if self.cancelled.is_set():result={'status':'cancelled','message':'Dictation cancelled.'}
   self.update(**(result or {'status':'error','message':'Dictation failed.'}));self.finished.set();GATE.release()
 def release_idle(self):
  with self.lock:
   if self.state['status'] in ACTIVE:raise ValueError('Stop voice input before changing models or creating media.')
   p=self.worker
   if p and p.poll() is None:p.terminate();p.wait(timeout=10)
   self.worker=None
