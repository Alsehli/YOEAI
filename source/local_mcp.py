"""Reusable bounded stdio MCP client. No shell or model-selected process commands."""
import json,subprocess,queue,threading,time,os,contextlib
from pathlib import Path
class Client:
 def __init__(self,command,args,cwd,env,check=lambda:None):
  self.check=check;self.counter=0;self.events=queue.Queue();self.stderr=[]
  self.process=subprocess.Popen([str(command),*map(str,args)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=cwd,env=env,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
  def read():
   try:
    while True:
     line=self.process.stdout.readline(12_000_001)
     if not line:break
     if len(line)>12_000_000:self.events.put(ValueError('MCP response exceeds limit.'));break
     self.events.put(json.loads(line))
   except Exception as ex:self.events.put(ex)
  def errors():
   for line in iter(self.process.stderr.readline,b''):
    if sum(map(len,self.stderr))<8000:self.stderr.append(line[:1000].decode(errors='replace'))
  self.threads=[threading.Thread(target=read,daemon=True),threading.Thread(target=errors,daemon=True)]
  for thread in self.threads:thread.start()
  try:
   self.identity=self.call('initialize',{'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'YOEAI Reverse','version':'2.0'}},45)
   self.send({'jsonrpc':'2.0','method':'notifications/initialized'})
  except BaseException:self.close();raise
 def send(self,value):self.process.stdin.write((json.dumps(value)+'\n').encode());self.process.stdin.flush()
 def call(self,method,params,timeout=90):
  self.counter+=1;identifier=self.counter;self.send({'jsonrpc':'2.0','id':identifier,'method':method,'params':params});deadline=time.monotonic()+timeout
  while time.monotonic()<deadline:
   self.check()
   try:r=self.events.get(timeout=.2)
   except queue.Empty:
    if self.process.poll() is not None:raise ValueError('MCP server exited: '+''.join(self.stderr)[-500:])
    continue
   if isinstance(r,Exception):raise r
   if r.get('id')!=identifier:continue
   if r.get('error'):raise ValueError('MCP error: '+str(r['error'])[:500])
   return r['result']
  raise TimeoutError('Local analysis timed out. No target software was executed.')
 def tools(self):return self.call('tools/list',{})['tools']
 def tool(self,name,arguments,timeout=90):
  result=self.call('tools/call',{'name':name,'arguments':arguments},timeout)
  if result.get('isError'):raise ValueError('Analysis tool failed: '+json.dumps(result)[:700])
  return result
 def close(self):
  import psutil
  with contextlib.suppress(psutil.Error):
   process=psutil.Process(self.process.pid)
   for child in process.children(recursive=True):
    with contextlib.suppress(psutil.Error):child.terminate()
  if self.process.poll() is None:self.process.terminate()
  with contextlib.suppress(Exception):self.process.wait(5)
  for thread in self.threads:thread.join(1)
  for stream in [self.process.stdin,self.process.stdout,self.process.stderr]:
   with contextlib.suppress(Exception):stream.close()
 def __enter__(self):return self
 def __exit__(self,*args):self.close()
