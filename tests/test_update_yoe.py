import tempfile,time,unittest
from pathlib import Path
import mini_agents as m
import update_yoe as u
class UpdateTests(unittest.TestCase):
 def test_fail_closed_policy(self):
  for op in u.RED:self.assertEqual(u.policy(op),'RED')
  self.assertEqual(u.policy('unknown_tool'),'RED')
  self.assertEqual(u.policy('deploy'),'AMBER')
  self.assertFalse(u.execution_capability()['enabled'])
 def test_shared_engine_proposal_and_scope(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as d:
   root=Path(d);project=root/'approved';project.mkdir();f=project/'example.py';f.write_text('print(1)')
   seen=[]
   def infer(t,messages,tokens):
    seen.append(t['agent']);return 'Problem: example. Tests: proposed only. Approval required.'
   e=m.Engine(root,infer=infer)
   try:
    t=e.create({'agent':'update','objective':'Review this file','project':str(project),'files':['example.py'],'permissions':{'readProject':True}})
    for _ in range(200):
     t=e.get(t['id'])
     if t['status'] not in m.ACTIVE and e.running_id!=t['id']:break
     time.sleep(.02)
    self.assertEqual(t['status'],'COMPLETED');self.assertEqual(t['agent'],'update');self.assertEqual(t['improvement']['evidenceCount'],1)
    self.assertEqual(f.read_text(),'print(1)');self.assertTrue(seen and all(x=='update' for x in seen))
    self.assertRaises(ValueError,u.delegate,e,t['id'],{'agent':'code'})
    self.assertRaises(ValueError,u.delegate,e,t['id'],{'agent':'code','approve':True,'proposalSha256':'changed'})
    child=u.delegate(e,t['id'],{'agent':'code','approve':True,'proposalSha256':t['improvement']['proposalSha256']})
    self.assertEqual(child['agent'],'code');self.assertEqual(child['project'],str(project));self.assertFalse(child['permissions']['web'])
    self.assertFalse(t['improvement']['verified']);self.assertEqual(t['improvement']['deployment'],'NOT_REQUESTED')
    e.set_memory('update',{'preferences':'Preserve branding','maxTokens':512})
    self.assertEqual(e.memory('code')['preferences'],'')
    self.assertRaises(ValueError,e.create,{'agent':'update','objective':'Read','files':['example.py'],'project':str(project)})
   finally:e.closed=True;e.worker.join(2)
if __name__=='__main__':unittest.main()

