"""Shared Mini YOE workflows hosted by Lite's existing local HTTP server."""
import threading
_lock=threading.RLock()
_engine=None
def initialize(home,bundle,config):
 global _engine
 with _lock:
  if _engine is None:
   import configuration
   configuration.bind(home,bundle,config)
   import mini_agents
   class LiteEngine(mini_agents.Engine):
    def gpu_busy(self):return False
    def memory(self,agent):
     value=super().memory(agent)
     with self.connect() as db:saved=db.execute('SELECT 1 FROM memory WHERE agent=?',(agent,)).fetchone()
     if not saved:value['maxTokens']=512
     return value
    def call(self,t,instructions,user,limit=None,schema=None,images=None):
     budget=max(128,min(1024,int(self.config().get('context',2048))//3))
     return super().call(t,instructions,user,min(limit or t['memory']['maxTokens'],budget),schema,images)
   _engine=LiteEngine(home=home,config=configuration.read_config)
   mini_agents.INSTANCE=_engine
  return _engine
def route_agents(handler,post,home,bundle,config):
 if not handler.path.startswith('/mini/'):return False
 initialize(home,bundle,config)
 from mini_agents import route
 return route(handler,post)
def shared_request(handler,home,bundle,config):
 initialize(home,bundle,config)
 from mini_agents import shared_request as guard
 return guard(handler)
def shutdown():
 if _engine is None:return
 _engine.closed=True
 for task in _engine.tasks():
  if task['status'] in ['QUEUED','PLANNING','RUNNING','WAITING_FOR_APPROVAL','PAUSED']:_engine.cancel(task['id'])
 _engine.worker.join(timeout=3)
