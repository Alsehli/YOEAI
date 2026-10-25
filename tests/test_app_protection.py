import unittest
from unittest.mock import patch
import configuration
import test_engine as fixtures
class AppProtection(unittest.TestCase):
 def test_code_agent_cannot_bypass_native_application_updater(self):
  fixture=fixtures.Tests();fixture.setUp()
  try:
   task=fixture.wait(fixture.code())
   with patch.object(configuration,'APP_DIR',fixture.project):
    self.assertRaisesRegex(ValueError,'native deployment dialog',fixture.e.approve_patch,task['id'],{'approve':True})
   self.assertIn('a - b',(fixture.project/'calc.py').read_text())
  finally:fixture.tearDown()

