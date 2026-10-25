import unittest,tempfile,json,time
from pathlib import Path
from unittest.mock import patch
from language_understanding import POLICY,preserve,context
from mini_agents import Engine
class Language(unittest.TestCase):
 def test_literals_preserved(self):
  for original,candidate in [('save 123.pdf','save 124.pdf'),('copy a.py to b.py','copy a.py to c.py'),('open https://nvidia.com','open https://evil.test'),('arrive 2026-10-22','arrive 2026-10-23'),('do this at 10:30','do this at 11:30')]:self.assertEqual(preserve(original,candidate),original)
  self.assertEqual(preserve('plz open report.pdf','Please open report.pdf'),'Please open report.pdf')
 def test_context_bounded_and_unmodified(self):
  rows=[{'role':'user','content':'x'*2000} for _ in range(12)];copy=json.dumps(rows);self.assertLessEqual(sum(len(x['content']) for x in context(rows)),3000);self.assertEqual(json.dumps(rows),copy)
 def test_shared_policy_and_followup(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
   seen=[]
   e=Engine(Path(tmp),infer=lambda t,m,tokens:seen.append(m) or 'OK');e.windows_enabled=True
   try:
    for agent in ['code','research','windows','update']:
     t={'id':agent,'agent':agent,'objective':'plz help','memory':e.memory(agent),'cancelled':False,'recall':[],'conversationContext':[{'role':'user','content':'My project is a calculator.'}]}
     e.call(t,'Answer the current request.','make it simpler',128);self.assertIn(POLICY,seen[-1][0]['content']);self.assertIn('My project is a calculator.',seen[-1][-1]['content']);self.assertEqual(t['objective'],'plz help')
   finally:e.closed=True;e.worker.join(3)
if __name__=='__main__':unittest.main()
