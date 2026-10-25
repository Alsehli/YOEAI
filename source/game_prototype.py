"""One approved, bounded prototype workflow; never runs model-written commands."""
import threading,time,uuid
from pathlib import Path
from game_studio import atomic,safe_folder,specification,ACTIVE

class Prototypes:
 def __init__(self,studio):
  self.s=studio;self.file=studio.home/'prototypes.json';self.items=studio.read(self.file,[]);self.stops={}
  for item in self.items:
   if item['status'] in ACTIVE:item.update(status='CANCELLED',message='App restarted. The project is preserved; no actions were repeated.',updated=time.time())
  atomic(self.file,self.items)
 def record(self,item,message,**values):
  with self.s.lock:
   item.update(message=message,updated=time.time(),**values);item['events'].append({'time':time.time(),'message':message});atomic(self.file,self.items)
 def start(self,task,body):
  if body.get('approve') is not True:raise ValueError('Approve the exact project location and prototype plan first.')
  if task.get('agent')!='game' or task.get('status')!='COMPLETED' or task.get('gameNextAction') not in ['create','revise'] or not task.get('gameProposal'):raise ValueError('Finish a supported game creation plan first.')
  spec=specification(task['gameProposal'])
  if body.get('spec')!=spec:raise ValueError('The plan changed. Review the current game settings again.')
  if body.get('project')!=task.get('gameProject'):raise ValueError('The selected project does not match this plan.')
  with self.s.lock:
   if any(i['status'] in ACTIVE for i in self.items) or any(j['status'] in ACTIVE for j in self.s.jobs):raise ValueError('Finish or stop the current game creation first.')
   if any(i['task']==task['id'] and i['status']=='COMPLETED' for i in self.items):raise ValueError('This plan already created a prototype. Describe a new change to continue.')
   if task.get('gameProject'):
    doc=self.s.revise({'project':task['gameProject'],'spec':spec,'approve':True})
   else:
    if not isinstance(body.get('parent'),str) or not body['parent'].strip():raise ValueError('Choose where to save your game first.')
    parent=safe_folder(body['parent']);doc=self.s.create({'parent':str(parent),'spec':spec,'approve':True})
   item={'id':uuid.uuid4().hex,'task':task['id'],'project':doc['id'],'title':doc['title'],'status':'QUEUED','created':time.time(),'updated':time.time(),'events':[],'jobs':[],'message':'Preparing your prototype...','error':None,'verified':False,'approval':{'time':time.time(),'spec':spec,'scope':['project files','shipped template assembly','Unity verification'],'project':doc['id']}}
   self.items.append(item);self.items=self.items[-60:];self.stops[item['id']]=threading.Event();self.record(item,item['message'])
   threading.Thread(target=self.run,args=(item,),daemon=True,name='YOE-Prototype').start();return dict(item)
 def check(self,item):
  if self.stops[item['id']].is_set():raise InterruptedError('Stopped. Your project and checkpoints are preserved.')
 def run(self,item):
  try:
   self.check(item);self.record(item,'Preparing your game...',status='RUNNING')
   for operation,message in [('assemble','Building your levels...'),('validate','Checking the game and Unity scripts...')]:
    self.check(item);self.record(item,message)
    job=self.s.start({'project':item['project'],'operation':operation,'approve':True,'prototype':item['id']})
    item['jobs'].append(job['id']);self.record(item,message)
    while True:
     if self.stops[item['id']].wait(.15):
      active=next(j for j in self.s.jobs if j['id']==job['id'])
      if active['status'] in ACTIVE:self.s.stop(job['id'])
      raise InterruptedError('Stopped. Partial work is not marked ready.')
     actual=next(j for j in self.s.jobs if j['id']==job['id'])
     if actual['status'] not in ACTIVE:break
    if actual['status']!='COMPLETED' or not actual.get('result',{}).get('passed'):raise ValueError(actual.get('error') or 'The game check did not pass. Open Advanced for details.')
   self.check(item)
   report=self.s.inspect(item['project'])['reports'];scenes=report.get('scene-report.json',{});validation=report.get('validation.json',{})
   if not scenes.get('passed') or not validation.get('passed'):raise ValueError('The required verification reports are missing.')
   self.record(item,'Your prototype is ready.',status='COMPLETED',verified=True,result={'scenes':len(scenes.get('scenes',[])),'checks':validation.get('checks',[]),'scope':'Scenes assembled and Unity scripts checked. Play in Unity to review the game. Template art; custom art and gameplay are not automatically certified.'})
  except InterruptedError as ex:self.record(item,str(ex),status='CANCELLED',verified=False)
  except Exception as ex:self.record(item,'I could not finish the prototype. Your project is preserved.',status='FAILED',verified=False,error=str(ex)[:1200])
 def stop(self,ident):
  item=next((i for i in self.items if i['id']==ident),None)
  if not item or item['status'] not in ACTIVE:raise ValueError('Choose an active prototype.')
  self.stops[ident].set();return {'stopping':True}
