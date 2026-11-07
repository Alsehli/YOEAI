import sys,os,unittest,tempfile,threading,json,time,types,importlib.util
from pathlib import Path
from unittest.mock import patch
source=Path(__file__).resolve().parents[1]/'source';sys.path.insert(0,str(source));path=Path(os.environ.get('YOEAI_SETTINGS_TEST_MODULE',str(source/'model_settings.py')));spec=importlib.util.spec_from_file_location('model_settings_under_test',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class BugTests(unittest.TestCase):
 def done(self,s):
  deadline=time.monotonic()+3
  while s.state['busy'] and time.monotonic()<deadline:time.sleep(.01)
  self.assertFalse(s.state['busy'])
 def test_read_failure_does_not_lock_out_future_tasks(self):
  with tempfile.TemporaryDirectory() as d,patch.object(m,'selected_model',return_value={'model':'new','projector':''}):
   gate=threading.Lock();s=m.Service(d,lambda:(_ for _ in ()).throw(OSError('profile unreadable')),lambda x:None,gate,lambda:None)
   with self.assertRaises(OSError):s.start({'model':'new','confirmed':True})
   self.assertFalse(gate.locked())
 def test_thread_start_failure_releases_gate(self):
  with tempfile.TemporaryDirectory() as d,patch.object(m,'selected_model',return_value={'model':'new','projector':''}),patch.object(m.threading.Thread,'start',side_effect=RuntimeError('no thread')):
   gate=threading.Lock();s=m.Service(d,lambda:{'model':'old'},lambda x:None,gate,lambda:None)
   with self.assertRaises(ValueError):s.start({'model':'new','confirmed':True})
   self.assertFalse(gate.locked());self.assertFalse(s.state['busy'])
 def test_bad_field_types_get_clear_errors(self):
  with tempfile.TemporaryDirectory() as d:
   s=m.Service(d,lambda:{},lambda x:None,threading.Lock(),lambda:None)
   for value in [None,[],123,{'path':'a'}]:
    with self.subTest(value=value),self.assertRaises(ValueError):s.start({'model':value,'confirmed':True})
 def test_recent_storage_failure_is_not_a_model_load_failure(self):
  with tempfile.TemporaryDirectory() as d,patch.object(m,'selected_model',return_value={'model':'new','projector':''}),patch.object(m,'atomic',side_effect=OSError('disk full')):
   config={'model':'old'};s=m.Service(d,lambda:dict(config),lambda v:config.update(v),threading.Lock(),lambda:None);s.start({'model':'new','confirmed':True});self.done(s);self.assertEqual(s.state['phase'],'ready');self.assertIn('recent',s.state['warning']);self.assertEqual(config['model'],'new')
 def test_wrong_json_shape_in_recent_library_is_repaired(self):
  with tempfile.TemporaryDirectory() as d,patch.object(m,'selected_model',return_value={'model':'new','projector':''}):
   path=Path(d)/'model-library.json';path.write_text('{"not":"a list"}');s=m.Service(d,lambda:{'model':'old'},lambda v:None,threading.Lock(),lambda:None);s.start({'model':'new','confirmed':True});self.done(s);self.assertEqual(s.state['phase'],'ready');self.assertIsInstance(json.loads(path.read_text()),list)
 def test_recent_paths_deduplicate_windows_spelling_and_keep_projector_variants(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'model-library.json';path.write_text(json.dumps([{'model':'D:/MODEL.gguf','projector':''},{'model':'d:\\model.gguf','projector':''},{'model':'D:/MODEL.gguf','projector':'D:/vision.gguf'},'bad',{'model':None}]))
   items=m.recent_models(path);self.assertEqual(len(items),2)
 def test_factory_returns_one_service_under_concurrent_initialization(self):
  with tempfile.TemporaryDirectory() as d:
   agents=types.SimpleNamespace(GATE=threading.Lock(),INSTANCE=None);config=types.SimpleNamespace(HOME=Path(d),CONFIG_FILE=Path(d)/'config.json',read_config=lambda:{})
   modes=types.SimpleNamespace();created=[];results=[]
   def create(*a):time.sleep(.05);value=object();created.append(value);return value
   with patch.dict(sys.modules,{'mini_agents':agents,'configuration':config,'model_modes':modes}),patch.object(m,'INSTANCE',None),patch.object(m,'Service',side_effect=create):
    threads=[threading.Thread(target=lambda:results.append(m.normal_service())) for _ in range(8)]
    for t in threads:t.start()
    for t in threads:t.join()
   self.assertEqual(len(created),1);self.assertEqual(len({id(x) for x in results}),1)
if __name__=='__main__':unittest.main(verbosity=2)
