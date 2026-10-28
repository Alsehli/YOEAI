import unittest,tempfile
from pathlib import Path
from unittest.mock import patch
from design_generation import ImageEngines
from image_generation import ImageGenerator
from design_generation import DesignGenerator
import video_generation_adapter as v
class PortableOptional(unittest.TestCase):
 def test_absent_video_addon_does_not_break_chat_route(self):
  old=v.INSTANCE
  try:
   v.INSTANCE=None
   with tempfile.TemporaryDirectory() as folder,patch.object(v,'APP_DIR',Path(folder)),patch.object(Path,'is_file',return_value=False):
    g=v.generator();self.assertEqual(g.state['status'],'idle');self.assertFalse(g.status()['installed'])
  finally:v.INSTANCE=old
 def test_missing_turbo_is_not_advertised_ready(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);turbo=ImageGenerator(root/'config.json',root/'Outputs');design=DesignGenerator(root/'Design/config.json',None,None,root/'lock');engines=ImageEngines(turbo,design);s=engines.models()['turbo'];self.assertEqual(s['state'],'Not installed');self.assertFalse(s['canGenerate']);self.assertTrue(s['error'])
 def test_verified_turbo_still_ready(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);turbo=ImageGenerator(root/'config.json',root/'Outputs');design=DesignGenerator(root/'Design/config.json',None,None,root/'lock');engines=ImageEngines(turbo,design)
   with patch.object(turbo,'config',return_value={}):self.assertEqual(engines.models()['turbo']['state'],'Ready')
if __name__=='__main__':unittest.main()
