import sys,tempfile,unittest,json
from pathlib import Path
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import model_settings,lite_native
class LoadingTests(unittest.TestCase):
 def test_selection_preserves_worker(self):
  with tempfile.TemporaryDirectory() as d:
   home=Path(d);cfg={'model':'old.gguf','context':8192};(home/'profile.json').write_text(json.dumps(cfg))
   with patch.object(model_settings,'INSTANCE',None),patch('model_library.Library'),patch.object(lite_native,'healthy',return_value=True),patch.object(lite_native,'start') as start,patch.object(lite_native,'stop') as stop:
    service=model_settings.configure_lite(home,home,lambda:json.loads((home/'profile.json').read_text()))
    service.apply_model({'model':'new.gguf'})
    stop.assert_not_called();start.assert_called_once();self.assertEqual(json.loads((home/'profile.json').read_text())['model'],'new.gguf')
 def test_failure_restores_profile(self):
  with tempfile.TemporaryDirectory() as d:
   home=Path(d);cfg={'model':'old.gguf','context':8192};(home/'profile.json').write_text(json.dumps(cfg))
   with patch.object(model_settings,'INSTANCE',None),patch('model_library.Library'),patch.object(lite_native,'healthy',return_value=True),patch.object(lite_native,'start',side_effect=[RuntimeError('load failed'),None]) as start,patch.object(lite_native,'stop') as stop:
    service=model_settings.configure_lite(home,home,lambda:json.loads((home/'profile.json').read_text()))
    with self.assertRaises(model_settings.SwitchError):service.apply_model({'model':'new.gguf'})
    self.assertEqual(json.loads((home/'profile.json').read_text()),cfg);self.assertEqual(start.call_count,2);stop.assert_called_once()
 def test_ready_model_not_reloaded(self):
  with tempfile.TemporaryDirectory() as d:
   model=Path(d)/'model.gguf';model.touch();native=Mock();native.worker.poll.return_value=None;native.state={'loaded':True,'busy':False,'context':8192,'model':str(model.resolve())};native.last_load={'projector':None}
   with patch.object(lite_native,'INSTANCE',native),patch.object(lite_native,'initialize'),patch('native_ai.resources.plans') as plans:
    lite_native.start(d,d,lambda:{'model':str(model),'context':8192})
    native.request.assert_not_called();plans.assert_not_called()
if __name__=='__main__':unittest.main()
