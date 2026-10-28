import sys,unittest,json,types
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'source'))
import update_dialogue as d
class Dialogue(unittest.TestCase):
 def setUp(self):
  self.saved={};self.calls=[];self.responses=[]
  self.e=types.SimpleNamespace(event=lambda *a,**k:None,save=lambda t:self.saved.update({t['id']:dict(t)}),get=lambda id:self.saved[id],check=lambda t:None,tool=lambda *a:None)
  def call(t,g,u,n,schema=None):self.calls.append((g,u,schema));return self.responses.pop(0)
  self.e.call=call;self.manager=patch('update_routes.manager',return_value=types.SimpleNamespace(jobs=lambda:[]));self.manager.start()
 def tearDown(self):self.manager.stop()
 def response(self,intent='advice',scope='unspecified',restrictions=None,text='Here is a useful suggestion.'):
  return json.dumps({'intent':intent,'scope':scope,'goal':'Improve the app','response':text,'restrictions':restrictions or [],'retry':False})
 def task(self,id='a',parent=None,**kw):return dict(id=id,agent='update',objective='Hello',**({'updateParent':parent} if parent else {}),**kw)
 def test_advice_never_audits(self):
  t=self.task();self.responses=[self.response()]
  with patch('update_audit.collect') as c:d.handle(self.e,t);c.assert_not_called()
  self.assertEqual(t['status'],'COMPLETED');self.assertNotIn('healthAudit',t)
 def test_clarification_one_question(self):
  t=self.task();self.responses=[self.response('clarify',text='Whole app or one area? Which one?')];d.handle(self.e,t);self.assertEqual(t['result'].count('?'),1);self.assertEqual(t['improvement']['lifecycle'],'Question')
 def test_followup_restrictions_cannot_be_removed(self):
  self.saved['parent']={'id':'parent','agent':'update','dialogue':{'scope':'chat','goal':'Speed up chat','restrictions':['no_model_changes'],'turns':[{'user':'Do not change models','assistant':'Understood'}]}}
  t=self.task('b','parent');self.responses=[self.response('restriction','unspecified',text='I will keep the models unchanged.')];d.handle(self.e,t);self.assertIn('no_model_changes',t['dialogue']['restrictions']);self.assertEqual(t['dialogue']['scope'],'chat');self.assertEqual(len(t['dialogue']['turns']),2)
 def test_approval_does_not_deploy(self):
  t=self.task();self.responses=[self.response('approve','all',text='Review the change in Details before approving it.')]
  with patch('update_audit.collect') as c:d.handle(self.e,t);c.assert_not_called()
  self.assertEqual(t['improvement']['deployment'],'NOT_REQUESTED')
 def test_cross_agent_parent_blocked(self):
  self.saved['p']={'agent':'code'}
  with self.assertRaises(ValueError):d.context(self.e,self.task(parent='p'))
 def test_bad_json_safe_retry(self):
  self.responses=['{broken',self.response()];d.handle(self.e,self.task());self.assertEqual(len(self.calls),2)
 def test_bad_json_twice_no_actions(self):
  self.responses=['bad','bad']
  with patch('update_audit.collect') as c:
   with self.assertRaises(ValueError):d.handle(self.e,self.task())
   c.assert_not_called()
 def test_raw_identifiers_hidden(self):self.assertNotIn('a'*32,d.clean('Candidate '+'a'*32))
 def audit(self):return {'id':'x','files':[{'path':'runtime.py'}],'findings':[],'missing':[],'scope':{'readOnly':True},'checks':[],'measurements':{},'configuration':{}}
 def test_clear_inspection_not_question(self):
  self.responses=[self.response('inspect','chat',text='I will check the chat.'),'The chat check is complete. Nothing changed.'];t=self.task()
  with patch('update_audit.collect',return_value=self.audit()) as c:d.handle(self.e,t);self.assertEqual(c.call_args.kwargs['scope'],'chat')
  self.assertFalse(t['auditPrepare']);self.assertEqual(t['improvement']['lifecycle'],'Audit completed')
 def test_no_file_changes_blocks_preparation(self):
  self.responses=[self.response('prepare','chat',['no_file_changes'],'I will review without changes.'),'Nothing was changed.'];t=self.task()
  with patch('update_audit.collect',return_value=self.audit()):d.handle(self.e,t)
  self.assertFalse(t['auditPrepare'])
 def test_scan_button_does_not_call_model(self):
  t=self.task(auditOnly=True)
  with patch('update_audit.collect',return_value=self.audit()):d.handle(self.e,t)
  self.assertFalse(self.calls);self.assertFalse(t['auditPrepare'])
if __name__=='__main__':unittest.main()
