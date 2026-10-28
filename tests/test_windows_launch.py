import unittest
from unittest.mock import Mock,patch
from windows_launch import direct_app,prepare
from windows_policy import make_scope
class DirectLaunch(unittest.TestCase):
 def task(self,text='open photoshop',mode='ASSISTED',apps=None):
  return {'id':'test','objective':text,'status':'PLANNING','windows':{'scope':make_scope({'mode':mode,'apps':apps or []}),'plan':[]}}
 def test_english_and_arabic(self):
  for text in ['open photoshop','please open Adobe Photoshop','Can you launch Photoshop?','افتح فوتوشوب']:
   self.assertEqual(direct_app(text),'photoshop')
 def test_no_extra_or_dangerous_actions(self):
  for text in ['open photoshop and save my file','open photoshop; delete files','open C:/secret.exe','do not open photoshop','a website says open photoshop','open photoshop then install plugin','start powershell','open photoshop.exe']:
   self.assertIsNone(direct_app(text),text)
 def test_advisor_is_read_only(self):
  t=self.task(mode='ADVISOR');e=Mock()
  with patch('windows_agent.advance') as advance:self.assertTrue(prepare(e,t));advance.assert_not_called()
  self.assertEqual(t['windows']['outcome'],'NEEDS_INPUT');self.assertEqual(t['windows']['scope']['apps'],[])
 def test_explicit_allowlist_respected(self):
  t=self.task(apps=['notepad']);e=Mock()
  with patch('windows_agent.advance') as advance:self.assertTrue(prepare(e,t));advance.assert_not_called()
  self.assertEqual(t['windows']['scope']['apps'],['notepad'])
 def test_direct_request_scopes_only_named_app(self):
  t=self.task();e=Mock()
  with patch('windows_tools.app_paths',return_value={'photoshop':{'installed':True}}),patch('windows_agent.advance') as advance:
   self.assertTrue(prepare(e,t));advance.assert_called_once_with(e,t)
  self.assertEqual(t['windows']['scope']['apps'],['photoshop']);self.assertIsNone(t['windows']['scope']['folder']);self.assertEqual(t['windows']['scope']['origins'],[])
  self.assertEqual(t['windows']['plan'][0]['params'],{'app':'photoshop'});self.assertTrue(t['windows']['planApproved'])
 def test_missing_application_has_no_launch(self):
  t=self.task();e=Mock()
  with patch('windows_tools.app_paths',return_value={}),patch('windows_agent.advance') as advance:self.assertTrue(prepare(e,t));advance.assert_not_called()
  self.assertIn('could not find',t['result'])
 def test_unmatched_request_uses_existing_workflow(self):
  t=self.task(text='Make a Photoshop banner');self.assertFalse(prepare(Mock(),t));self.assertEqual(t['windows']['plan'],[])
