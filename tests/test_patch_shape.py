"""Exercise the real Code YOE run path without inference or file writes."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from mini_agents import Engine

class PatchShapeTests(unittest.TestCase):
 def run_patch(self,raw):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);source=root/'sample.js';source.write_text('const answer = 1;',encoding='utf8')
   task={'agent':'code','objective':'Correct the answer','documents':[],'permissions':{'web':False},'files':['sample.js'],'project':str(root)}
   engine=Engine.__new__(Engine)
   for name in ('event','check','tool','save'):setattr(engine,name,Mock())
   engine.call=Mock(side_effect=['Plan','Draft','Review',raw])
   with patch('mini_agents.clean_root',return_value=root),patch('code_preview.publish'):
    engine.run(task)
   self.assertEqual(source.read_text(encoding='utf8'),'const answer = 1;')
   self.assertEqual(engine.call.call_count,4)
   self.assertIn('Draft',task['result']);self.assertIn('Review',task['result'])
   engine.save.assert_called_once_with(task)
   return task
 def test_non_object_json_completes_with_warning(self):
  for value in ([],[{'noChange':True}],None,'text',3,True):
   with self.subTest(value=value):
    task=self.run_patch(json.dumps(value));self.assertEqual(task['status'],'COMPLETED');self.assertIn('safe exact-match patch',task['patchWarning']);self.assertNotIn('patch',task)
 def test_invalid_json_completes_with_warning(self):
  task=self.run_patch('{bad');self.assertEqual(task['status'],'COMPLETED');self.assertIn('patchWarning',task)
 def test_no_change_object_completes_without_warning(self):
  task=self.run_patch('{"noChange":true}');self.assertEqual(task['status'],'COMPLETED');self.assertNotIn('patchWarning',task)
 def test_valid_patch_still_requires_approval(self):
  task=self.run_patch(json.dumps({'path':'sample.js','find':'1','replace':'2','explanation':'Correction'}));self.assertEqual(task['status'],'WAITING_FOR_APPROVAL');self.assertIn('-const answer = 1;',task['diff']);self.assertNotIn('patchWarning',task)
