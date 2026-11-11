import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from context_limits import capacity
from model_experience import describe
class PresetTests(unittest.TestCase):
 def info(self,limit):return {'metadata':{'general.architecture':'test','test.context_length':limit},'sizeBytes':1}
 def test_normal_presets(self):self.assertEqual(capacity(self.info(262144),196608)['presets'],{'quick':16384,'long':196608})
 def test_limit_caps_presets(self):self.assertEqual(capacity(self.info(8192),4096)['presets'],{'quick':8192,'long':8192})
 def test_unknown_limit(self):self.assertEqual(capacity(self.info(None),8192)['presets'],{'quick':16384,'long':16384})
 def test_stages_elapsed(self):
  for stage,label in [('initializing','Initializing'),('weights','transferring'),('context','Preparing context')]:
   x=describe({'model':'x'},{'busy':True,'loadStage':stage,'loadElapsedSeconds':12.9},{})
   self.assertEqual(x['state'],'loading');self.assertIn(label,x['detail']);self.assertIn('12s elapsed',x['detail'])
 def test_nonfinite_elapsed_ignored(self):self.assertNotIn('elapsed',describe({'model':'x'},{'busy':True,'loadElapsedSeconds':float('nan')},{})['detail'])
if __name__=='__main__':unittest.main()
