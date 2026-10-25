import unittest,tempfile
from pathlib import Path
from unittest.mock import patch
import model_modes as m
class AdvancedVision(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'mmproj.gguf';self.cat={'advanced':{'model':str(Path(self.temp.name)/'model.gguf'),'projector':str(self.path)}}
 def tearDown(self):self.temp.cleanup()
 def test_missing_projector_preserves_text_mode(self):self.assertIsNone(m.advanced_projector(self.cat,verify=True))
 def test_wrong_size_rejected(self):
  self.path.write_bytes(b'GGUF')
  with self.assertRaisesRegex(ValueError,'size'):m.advanced_projector(self.cat,verify=True)
 def test_corrupt_checksum_rejected(self):
  self.path.write_bytes(b'GGUF')
  with patch.object(m,'PROJECTOR_BYTES',4):
   with self.assertRaisesRegex(ValueError,'checksum'):m.advanced_projector(self.cat,verify=True)
 def test_projector_is_taken_from_actual_process(self):self.assertEqual(m.projector_argument(['server','--mmproj','C:/27b.gguf']),'C:/27b.gguf')
 def test_wrong_running_projector_blocked(self):
  c={'projector':str(self.path)}
  with patch.object(m,'catalog',return_value=self.cat),patch.object(m,'advanced_projector',return_value=self.path),patch.object(m,'running_owned',return_value={'mode':'advanced','args':['server','--mmproj','C:/9b.gguf']}):
   with self.assertRaisesRegex(ValueError,'active backend'):m.require_advanced_vision(c)
