import sys,unittest,tempfile,time,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'source'))
from agent_skills import evidence_sources,audit_report,check_cases,example_test
import mini_agents as m

class EvidenceTests(unittest.TestCase):
 def test_sources_deduplicate_and_reject_unsafe(self):
  sources=evidence_sources([{'url':'https://docs.python.org/3/#a','title':'Docs'},{'url':'https://docs.python.org/3/#b'},{'url':'javascript:alert(1)'},{'url':'https://user:pass@example.org'}])
  self.assertEqual(len(sources),1);self.assertEqual(sources[0]['id'],'S1');self.assertEqual(sources[0]['domain'],'docs.python.org')
 def test_invented_references_removed(self):
  sources=evidence_sources([{'url':'https://example.org/real'}])
  text,audit=audit_report('Fact [S1]. Invented [S9] https://fake.example/a. See https://example.org/real.',sources)
  self.assertNotIn('https://fake',text);self.assertNotIn('[S9]',text);self.assertIn('https://example.org/real.',text);self.assertEqual(len(audit['removedReferences']),2)
 def test_empty_search_never_claims_disabled(self):
  with tempfile.TemporaryDirectory() as d:
   e=m.Engine(d,infer=lambda *a:'Insufficient evidence.',search=lambda *a:{'results':[]})
   try:
    t=e.create({'agent':'research','objective':'Latest facts','permissions':{'web':True}})
    for _ in range(200):
     t=e.get(t['id'])
     if t['status'] not in m.ACTIVE:break
     time.sleep(.01)
    self.assertEqual(t['status'],'COMPLETED');self.assertIn('no usable sources',t['result']);self.assertNotIn('Web search disabled',t['result'])
   finally:e.closed=True;e.worker.join(2)
 def test_grouped_and_range_references_checked(self):
  sources=evidence_sources([{'url':'https://example.org/1'},{'url':'https://example.org/2'}])
  text,audit=audit_report('Supported [S1, S2] [S1-S2]. Invented [S1, S99] [S1-S99].',sources)
  self.assertIn('[S1, S2]',text);self.assertIn('[S1-S2]',text);self.assertNotIn('S99',text);self.assertEqual(len(audit['removedReferences']),2)

class ExamplesTests(unittest.TestCase):
 def case(self,args=None,expected=5):return {'file':'calc.py','function':'add','args':[2,3] if args is None else args,'expected':expected}
 def test_behavior_detects_bug_and_fix(self):
  self.assertEqual(example_test('def add(a,b):\n return a-b',self.case())['status'],'FAIL')
  self.assertEqual(example_test('def add(a,b):\n return a+b',self.case())['status'],'PASS')
 def test_branch_boundary(self):
  code='def add(a,b):\n if a<0:\n  return b\n value=a+b\n return value'
  self.assertEqual(example_test(code,self.case([-1,3],3))['status'],'PASS')
 def test_calls_imports_attributes_and_loops_blocked(self):
  for body in ['return __import__("os").system("echo bad")','import os\n return 5','while True:\n  pass','return a.real','return [a,b]','return a**999999','return (lambda: 5)()']:
   code='def add(a,b):\n '+body.replace('\n','\n ')
   self.assertEqual(example_test(code,self.case())['status'],'BLOCKED',body)
 def test_module_side_effects_not_executed(self):
  with tempfile.TemporaryDirectory() as d:
   marker=Path(d)/'should-not-exist'
   code=f'open({str(marker)!r},"w").write("bad")\ndef add(a,b):\n return a+b'
   self.assertEqual(example_test(code,self.case())['status'],'PASS');self.assertFalse(marker.exists())
 def test_numeric_limits(self):
  self.assertRaises(ValueError,check_cases,[self.case([10**1000,3])])
  self.assertEqual(example_test('def add(a,b):\n return a*b',self.case([1e12,1e12]))['status'],'BLOCKED')
 def test_error_is_fail_not_success(self):
  self.assertEqual(example_test('def add(a,b):\n return a/b',self.case([1,0]))['status'],'FAIL')
 def test_global_and_recursion_blocked(self):
  for code in ['def add(a,b):\n return outside','def add(a,b):\n return add(a,b)']:
   self.assertEqual(example_test(code,self.case())['status'],'BLOCKED')
 def test_cases_require_shape_and_scalars(self):
  self.assertRaises(ValueError,check_cases,[dict(self.case(),command='echo bad')])
  self.assertRaises(ValueError,check_cases,[self.case([[1],2])])
 def test_approved_workflow(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as d:
   root=Path(d);p=root/'project';p.mkdir();f=p/'calc.py';f.write_text('def add(a,b):\n return a-b')
   e=m.Engine(root,infer=lambda *a:'No change suggested.')
   try:
    t=e.create({'agent':'code','objective':'Test sum','project':str(p),'files':['calc.py'],'permissions':{'readProject':True}})
    def wait(t):
     for _ in range(300):
      t=e.get(t['id'])
      if t['status'] not in m.ACTIVE:return t
      time.sleep(.01)
     raise AssertionError('Timed out')
    t=wait(t)
    self.assertRaises(ValueError,e.request_examples,t['id'],{'cases':[self.case()]})
    t=wait(e.request_examples(t['id'],{'approve':True,'cases':[self.case()]}));self.assertEqual(t['exampleResults'][0]['status'],'FAIL')
    f.write_text('def add(a,b):\n return a+b')
    t=wait(e.request_examples(t['id'],{'approve':True,'cases':[self.case()]}));self.assertEqual(t['exampleResults'][0]['status'],'PASS')
    self.assertRaises(ValueError,e.request_examples,t['id'],{'approve':True,'cases':[dict(self.case(),file='../outside.py')]})
   finally:e.closed=True;e.worker.join(2)

if __name__=='__main__':unittest.main(verbosity=2)
