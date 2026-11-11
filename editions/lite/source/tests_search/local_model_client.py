"""Test-only client reusing the already loaded selected model, no profile writes."""
import json,time,urllib.request
BASE='http://127.0.0.1:8087'
class Client:
 def __init__(self):self.events=[]
 def __call__(self,system,user,limit,*ctx):return self.generate(system,user,limit,structured=True)
 def generate(self,system,user,limit,structured=False):
  start=time.perf_counter();first=None;parts=[]
  payload={'messages':[{'role':'system','content':system},{'role':'user','content':user}],'max_tokens':limit,'stream':True,'temperature':0,'chat_template_kwargs':{'enable_thinking':False}}
  if structured:payload['response_format']={'type':'json_object'}
  req=urllib.request.Request(BASE+'/v1/chat/completions',json.dumps(payload).encode(),{'Content-Type':'application/json','Origin':BASE})
  with urllib.request.urlopen(req,timeout=100) as response:
   for line in response:
    if not line.startswith(b'data:') or line[5:].strip()==b'[DONE]':continue
    value=json.loads(line[5:]);delta=(value.get('choices')or[{}])[0].get('delta',{}).get('content','')or''
    if delta and first is None:first=time.perf_counter()-start
    parts.append(delta)
  raw=''.join(parts);self.events.append({'system':system,'user':user,'response':raw,'seconds':time.perf_counter()-start,'firstModelTokenSeconds':first});return raw
