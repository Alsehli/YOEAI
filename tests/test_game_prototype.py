import json,time,threading
from pathlib import Path
from unittest.mock import patch
import unittest
import test_game_studio as base

class PrototypeTests(unittest.TestCase):
 setUp=base.GameStudioTests.setUp
 tearDown=base.GameStudioTests.tearDown
 def task(self,action='create'):
  return {'id':'plan-a','agent':'game','status':'COMPLETED','gameNextAction':action,'gameProposal':self.d['spec']}
 def body(self,task):return {'approve':True,'parent':str(self.root),'spec':task['gameProposal'],'project':task.get('gameProject')}
 def fake_start(self,body):
  j={'id':str(len(self.s.jobs)),'project':body['project'],'operation':body['operation'],'status':'COMPLETED','result':{'passed':True}};self.s.jobs.append(j);return dict(j)
 def reports(self,ident):return {'reports':{'scene-report.json':{'passed':True,'scenes':[{}]},'validation.json':{'passed':True,'checks':['scripts']}}}
 def wait(self,manager):
  end=time.time()+4
  while manager.items[-1]['status'] in ['QUEUED','RUNNING'] and time.time()<end:time.sleep(.02)
  return manager.items[-1]
 def test_workflow_approval_required(self):
  t=self.task();b=self.body(t);b['approve']=False
  with self.assertRaises(ValueError):self.s.prototypes().start(t,b)
 def test_workflow_discussion_does_not_write(self):
  t=self.task('discuss');n=len(self.s.projects())
  with self.assertRaises(ValueError):self.s.prototypes().start(t,self.body(t))
  self.assertEqual(len(self.s.projects()),n)
 def test_workflow_modified_plan_blocked(self):
  t=self.task();b=self.body(t);b['spec']={**b['spec'],'levels':5}
  with self.assertRaises(ValueError):self.s.prototypes().start(t,b)
 def test_workflow_wrong_project_blocked(self):
  t=self.task();b=self.body(t);b['project']=self.d['id']
  with self.assertRaises(ValueError):self.s.prototypes().start(t,b)
 def test_workflow_requires_folder(self):
  t=self.task();b=self.body(t);b['parent']=''
  with self.assertRaises(ValueError):self.s.prototypes().start(t,b)
 def test_workflow_order_and_verified_result(self):
  m=self.s.prototypes();t=self.task()
  with patch.object(self.s,'start',side_effect=self.fake_start) as start,patch.object(self.s,'inspect',side_effect=self.reports):
   m.start(t,self.body(t));r=self.wait(m)
  self.assertEqual(r['status'],'COMPLETED');self.assertTrue(r['verified']);self.assertEqual([c.args[0]['operation'] for c in start.call_args_list],['assemble','validate'])
  with self.assertRaises(ValueError):m.start(t,self.body(t))
 def test_workflow_failure_never_ready(self):
  m=self.s.prototypes();t=self.task()
  with patch.object(self.s,'start',side_effect=ValueError('compiler error')):
   m.start(t,self.body(t));r=self.wait(m)
  self.assertEqual(r['status'],'FAILED');self.assertFalse(r['verified']);self.assertIn('compiler error',r['error'])
 def test_workflow_missing_report_never_ready(self):
  m=self.s.prototypes();t=self.task()
  with patch.object(self.s,'start',side_effect=self.fake_start),patch.object(self.s,'inspect',return_value={'reports':{}}):
   m.start(t,self.body(t));r=self.wait(m)
  self.assertEqual(r['status'],'FAILED');self.assertFalse(r['verified'])
 def test_workflow_restart_cancels_without_repeat(self):
  from game_studio import atomic,Studio
  atomic(self.s.home/'prototypes.json',[{'id':'x','task':'a','status':'RUNNING','events':[]}]);other=Studio(self.root/'Profile');m=other.prototypes();self.assertEqual(m.items[0]['status'],'CANCELLED');self.assertFalse(other.jobs)
 def test_workflow_stop_interrupts_next_step(self):
  m=self.s.prototypes();t=self.task()
  def running(b):
   j=self.fake_start(b);self.s.jobs[-1]['status']='RUNNING';self.s.events[j['id']]=threading.Event();return j
  with patch.object(self.s,'start',side_effect=running):
   r=m.start(t,self.body(t));time.sleep(.05);m.stop(r['id']);r=self.wait(m)
  self.assertEqual(r['status'],'CANCELLED');self.assertEqual(len(r['jobs']),1);self.assertFalse(r['verified'])
 def test_workflow_readonly_project_blocked(self):
  t=self.task('revise');t['gameProject']=self.d['id'];(self.p/'Assets/YOE/Scripts/YoePlayer.cs').write_text('modified')
  with self.assertRaises(ValueError):self.s.prototypes().start(t,self.body(t))
 def test_workflow_busy_blocks_second(self):
  m=self.s.prototypes();m.items.append({'id':'a','status':'RUNNING'})
  with self.assertRaises(ValueError):m.start(self.task(),self.body(self.task()))
