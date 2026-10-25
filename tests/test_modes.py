import unittest,tempfile,json
from pathlib import Path
from unittest.mock import patch
import model_modes as m
from mini_agents import GATE

class Modes(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.home=Path(self.temp.name);self.c={'model':'C:/existing-fast.gguf','projector':'C:/vision.gguf','apiPort':8080,'uiPort':8092,'context':16384,'externalBackend':True}
  self.patches=[patch.object(m,'CATALOG',self.home/'modes.json'),patch.object(m,'OWN',self.home/'owned.json'),patch.object(m,'CONFIG_FILE',self.home/'config.json'),patch.object(m,'read_config',lambda:dict(self.c)),patch.object(m.runtime,'healthy',return_value=False)]
  for p in self.patches:p.start()
  m.STATE.update(busy=False,phase='idle',error=None)
 def tearDown(self):
  for p in reversed(self.patches):p.stop()
  self.temp.cleanup()
 def test_reconcile_stale_profile(self):
  cat=m.catalog();fast=dict(cat['fast']);found={'pid':123,'identity':{'exe':str(m.BACKEND),'created':77},'model':str(m.ADVANCED),'context':8192,'port':8080,'gpuLayers':'all','args':[],'mode':'advanced'}
  with patch.object(m,'running_owned',return_value=found):self.assertEqual(m.reconcile_running(),'advanced')
  saved=json.loads(m.CONFIG_FILE.read_text());self.assertEqual(saved['modelMode'],'advanced');self.assertEqual(saved['uiPort'],8092);self.assertEqual(saved['context'],8192);self.assertEqual(m.catalog()['fast'],fast);self.assertIsNone(m.STATE['error'])
 def test_foreign_model_not_adopted(self):
  with patch.object(m,'request_json',return_value={'model_path':'C:/foreign.gguf'}):
   with self.assertRaisesRegex(ValueError,'not one of'):m.running_owned()
 def test_same_running_model_does_not_reload(self):
  with patch.object(m.runtime,'healthy',return_value=True),patch.object(m,'advanced_projector',return_value=Path(self.c['projector'])),patch.object(m,'reconcile_running',return_value='advanced'),patch.object(m,'verify_advanced'),patch.object(m,'stop_current') as stop,patch.object(m,'launch_advanced') as launch:
   m.transition('advanced');stop.assert_not_called();launch.assert_not_called()
 def test_fast_capture_is_exact(self):self.assertEqual(m.catalog()['fast'],self.c)
 def test_catalog_persists(self):m.catalog();self.assertEqual(m.catalog()['selected'],'fast')
 def test_invalid_mode(self):
  with self.assertRaises(ValueError):m.switch('../../bad')
 def test_shared_gate_blocks_switch(self):
  GATE.acquire()
  try:
   with self.assertRaisesRegex(ValueError,'active chat/agent'):m.switch('advanced')
  finally:GATE.release()
 def test_busy_blocks_switch(self):
  m.STATE['busy']=True
  with self.assertRaises(ValueError):m.switch('fast')
 def test_context_does_not_exceed_8k(self):
  with patch.object(m,'verify_advanced'),patch.object(m,'assert_idle'),patch.object(m,'stop_current') as stop:
   with self.assertRaises(ValueError):m.transition('advanced',16384)
   stop.assert_not_called()
 def test_missing_model_does_not_stop_old(self):
  with patch.object(m,'ADVANCED',self.home/'missing.gguf'),patch.object(m,'stop_current') as stop:
   with self.assertRaises(OSError):m.transition('advanced')
   stop.assert_not_called()
 def test_media_blocks(self):
  with patch.object(m,'media_busy',return_value=True):
   with self.assertRaisesRegex(ValueError,'image/video'):m.assert_idle()
 def test_generation_blocks(self):
  with patch.object(m,'media_busy',return_value=False),patch.object(m,'request_json',return_value=[{'is_processing':True}]):
   with self.assertRaisesRegex(ValueError,'generating'):m.assert_idle()
 def test_media_pause_does_not_block_itself(self):
  with patch.object(m.runtime,'healthy',return_value=True),patch.object(m,'media_busy',return_value=True),patch.object(m,'request_json',return_value=[{'is_processing':False}]),patch.object(m,'reconcile_running',return_value='fast'),patch.object(m,'stop_current') as stop:
   self.assertTrue(m.pause_for_media());stop.assert_called_once()
 def test_unowned_external_not_stopped(self):
  with patch.object(m.socket,'socket') as sock:
   sock.return_value.__enter__.return_value.connect_ex.return_value=0
   with self.assertRaisesRegex(ValueError,'ownership'):m.stop_current()
 def test_failure_no_silent_model_substitution(self):
  with patch.object(m,'verify_advanced'),patch.object(m,'assert_idle'),patch.object(m,'stop_current'),patch.object(m,'launch_advanced',side_effect=ValueError('failed')),patch.object(m,'launch_fast') as fast:
   with self.assertRaises(ValueError):m.transition('advanced')
   fast.assert_not_called();self.assertEqual(json.loads(m.CONFIG_FILE.read_text()),self.c)

if __name__=='__main__':unittest.main()
