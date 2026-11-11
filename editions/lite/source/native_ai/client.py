"""In-process inference client facade. No socket/HTTP operation is performed.

The response shape preserves existing streaming consumers while the actual
transport to the bundled libllama worker uses private inherited pipes.
"""
import io,json,threading
from .manager import INSTANCE
class Response:
 def __init__(self,iterator=None,value=None,stream=False,cancel=None):
  self.cancel=cancel;self.status=200;self.iterator=iterator;self.stream=stream;self.buffer=io.BytesIO(json.dumps(value).encode())if value is not None else None;self.pending=bytearray();self.done=value is not None
 def getheader(self,name,default=None):return 'text/event-stream'if self.stream else 'application/json'
 def next_bytes(self):
  if self.done:return b''
  try:
   event=next(self.iterator)
   if 'native_result'in event:self.done=True;self.iterator.close();return b'data: [DONE]\n\n'if self.stream else b''
   return ('data: '+json.dumps(event)+'\n\n').encode()
  except StopIteration:self.done=True;return b''
  except Exception as ex:
   self.done=True
   if self.stream:return ('data: '+json.dumps({'error':str(ex)})+'\n\n').encode()
   raise
 def readline(self,*args):
  if self.buffer:return self.buffer.readline(*args)
  return self.next_bytes()
 def read1(self,size=8192):
  if self.buffer:return self.buffer.read(size)
  if not self.pending:self.pending.extend(self.next_bytes())
  out=bytes(self.pending[:size]);del self.pending[:size];return out
 def read(self,size=-1):
  if self.buffer:return self.buffer.read(size)
  if size<0:
   out=bytes(self.pending)+b''.join(self.iterator_bytes());self.pending.clear();return out
  while len(self.pending)<size and not self.done:self.pending.extend(self.next_bytes())
  out=bytes(self.pending[:size]);del self.pending[:size];return out
 def iterator_bytes(self):
  while not self.done:
   value=self.next_bytes()
   if value:yield value
 def close(self):
  if self.cancel and not self.done:
   self.cancel.set()
   # A disconnected UI consumer stops polling its generator. Send cancellation
   # immediately rather than waiting for a next iteration that may never occur.
   INSTANCE.cancel()
   if self.iterator:
    try:self.iterator.close()
    except ValueError:pass  # Another thread is reading; its cancel poll owns cleanup.
  self.done=True
class Connection:
 def __init__(self,*args,**kwargs):self.response=None;self.path=None;self.payload=None;self.cancel=threading.Event();self.timeout=kwargs.get('timeout',180)
 def request(self,method,path,body=None,headers=None):
  if method not in ('GET','POST'):raise ValueError('Unsupported native operation.')
  if path not in ('/v1/chat/completions','/tokenize','/props','/slots','/health'):raise ValueError('Unknown native operation.')
  self.path=path;self.payload=json.loads(body)if body else {}
 def getresponse(self):
  if self.path=='/props':value={'model_path':INSTANCE.state.get('model'),'default_generation_settings':{'n_ctx':INSTANCE.state.get('context')}}
  elif self.path=='/health':value={'status':'ok'if INSTANCE.state['loaded']else'loading'}
  elif self.path=='/slots':value=[{'is_processing':INSTANCE.state['busy']}]
  elif self.path=='/tokenize':value=list(INSTANCE.request('tokenize',text=self.payload['content']))[-1]['native_result']
  else:
   iterator=INSTANCE.request('generate',payload=self.payload,cancel_event=self.cancel,timeout=self.timeout)
   if self.payload.get('stream'):self.response=Response(iterator=iterator,stream=True,cancel=self.cancel);return self.response
   chunks=list(iterator);text=''.join((x.get('choices')or[{}])[0].get('delta',{}).get('content','')or''for x in chunks);last=next((x for x in reversed(chunks)if x.get('usage')),{});value={'choices':[{'index':0,'message':{'role':'assistant','content':text},'finish_reason':'stop'}],'usage':last.get('usage',{}),'timings':last.get('timings',{})}
  self.response=Response(value=value);return self.response
 def close(self):
  if self.response is None or not self.response.done:self.cancel.set()
  if self.response is not None:self.response.close()
