"""Private pipe worker: no listening sockets, network server, or side effects."""
import json,queue,sys,threading
from .engine import Engine

def main():
 # Frozen Windows console programs otherwise inherit a legacy code page.
 # Pipe encoding must be explicit on BOTH ends for Arabic and mixed text.
 for stream in (sys.stdin,sys.stdout):
  if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8',errors='strict')
 output_lock=threading.Lock();jobs=queue.Queue(maxsize=2);cancel=threading.Event();engine=None
 def emit(value):
  with output_lock:sys.stdout.write(json.dumps(value,ensure_ascii=False)+'\n');sys.stdout.flush()
 def reader():
  while True:
   line=sys.stdin.readline(35000001)
   if not line:break
   if len(line)>35000000:
    while line and not line.endswith('\n'):line=sys.stdin.readline(65536)
    emit({'event':'error','error':'Native input exceeds the request limit.'});continue
   request={}
   try:
    request=json.loads(line)
    if not isinstance(request,dict):raise ValueError('Native request must be an object.')
    if request.get('op')=='cancel':cancel.set();continue
    jobs.put(request,timeout=.2)
   except Exception as ex:emit({'id':request.get('id')if isinstance(request,dict)else None,'event':'error','error':str(ex)})
  cancel.set();jobs.put({'op':'shutdown'})
 threading.Thread(target=reader,daemon=True).start()
 emit({'event':'ready','protocol':1,'encoding':sys.stdout.encoding})
 while True:
  item=jobs.get();ident=item.get('id');op=item.get('op');cancel.clear()
  try:
   if op=='shutdown':break
   if op=='load':
    if engine is None:engine=Engine(item['runtime'])
    result=engine.load(item['model'],item['context'],item['layers'],lambda p:emit({'id':ident,'event':'progress','value':p}),cancel,item.get('projector'))
   elif op=='unload':
    if engine:engine.close()
    result={'unloaded':True}
   elif op=='tokenize':result={'tokens':engine.tokenize(item['text'])}
   elif op=='generate':
    for chunk in engine.generate(item['payload'],cancel):emit({'id':ident,'event':'chunk','value':chunk})
    result={'finished':True}
   else:raise ValueError('Unknown native operation.')
   emit({'id':ident,'event':'done','value':result})
  except Exception as ex:emit({'id':ident,'event':'error','error':str(ex),'cancelled':isinstance(ex,InterruptedError)})
 if engine:engine.close();engine.lib.backend_free()

if __name__=='__main__':main()
