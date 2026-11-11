import sys,tempfile,unittest,json,struct,os,threading,time
from pathlib import Path
from unittest.mock import patch,Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from model_library import Library,local_folder

def gguf(path,version=3):path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'GGUF'+struct.pack('<I',version)+b'\0'*24)
class Cases(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(dir='tests_models');self.root=Path(self.temp.name).resolve();self.home=self.root/'profile';self.home.mkdir();self.folder=self.root/'models';self.lib=Library(self.home,self.folder,start=False)
 def tearDown(self):self.lib.close();self.temp.cleanup()
 def scan(self):self.lib.scan_once(now=10);self.lib.scan_once(now=12);return self.lib.snapshot()
 def test_01_default_folder_created(self):self.assertTrue(self.folder.is_dir())
 def test_02_default_persisted(self):self.assertEqual(json.loads(self.lib.config.read_text())['folder'],str(self.folder))
 def test_03_add_discovered(self):gguf(self.folder/'new.gguf');self.assertEqual(self.scan()['count'],1)
 def test_04_remove_disappears(self):
  path=self.folder/'new.gguf';gguf(path);self.scan();path.unlink();self.lib.scan_once(now=15);self.assertEqual(self.lib.snapshot()['count'],0)
 def test_05_growing_file_waits(self):
  path=self.folder/'copy.gguf';gguf(path);self.lib.scan_once(now=1);path.write_bytes(path.read_bytes()+b'grow');self.lib.scan_once(now=2);self.assertEqual(self.lib.snapshot()['count'],0);self.lib.scan_once(now=4);self.assertEqual(self.lib.snapshot()['count'],1)
 def test_06_projectors_hidden(self):gguf(self.folder/'mmproj-F32.gguf');gguf(self.folder/'projector.gguf');self.assertEqual(self.scan()['count'],0)
 def test_07_partial_download_hidden(self):gguf(self.folder/'model.gguf.part');self.assertEqual(self.scan()['count'],0)
 def test_08_split_gguf_hidden(self):gguf(self.folder/'model-00001-of-00002.gguf');self.assertEqual(self.scan()['count'],0)
 def test_09_invalid_magic_hidden(self):(self.folder/'bad.gguf').write_bytes(b'bad!'*20);self.assertEqual(self.scan()['count'],0)
 def test_10_invalid_version_hidden(self):gguf(self.folder/'new.gguf',99);self.assertEqual(self.scan()['count'],0)
 def test_11_nested_models(self):gguf(self.folder/'Author'/'Model'/'file.GGUF');self.assertEqual(self.scan()['count'],1)
 def test_12_unicode_filename(self):gguf(self.folder/'نموذج.gguf');self.assertEqual(self.scan()['models'][0]['name'],'نموذج.gguf')
 def test_13_folder_change_saved(self):
  other=self.root/'other';other.mkdir();self.lib.set_folder(str(other));again=Library(self.home,self.root/'unused',start=False);self.assertEqual(again.folder,other);again.close()
 def test_14_folder_change_clears_old_models(self):
  gguf(self.folder/'a.gguf');self.scan();other=self.root/'other';other.mkdir();self.lib.set_folder(str(other));self.assertEqual(self.lib.snapshot()['count'],0)
 def test_15_missing_folder_clear_error(self):
  self.folder.rmdir();self.lib.scan_once();self.assertFalse(self.lib.snapshot()['available']);self.assertIn('unavailable',self.lib.snapshot()['error'])
 def test_16_reconnected_folder_recovers(self):
  self.folder.rmdir();self.lib.scan_once();self.folder.mkdir();gguf(self.folder/'a.gguf');self.assertEqual(self.scan()['count'],1);self.assertIsNone(self.lib.snapshot()['error'])
 def test_17_relative_path_rejected(self):
  with self.assertRaises(ValueError):local_folder('relative/models')
 def test_18_network_path_rejected(self):
  with self.assertRaises(ValueError):local_folder('\\\\server\\models')
 def test_19_missing_user_folder_not_created(self):
  missing=self.root/'missing'
  with self.assertRaises(ValueError):self.lib.set_folder(str(missing))
  self.assertFalse(missing.exists())
 def test_20_scan_does_not_load_model(self):
  import model_settings
  service=model_settings.Service(self.home,lambda:{'model':'unchanged'},Mock(),threading.Lock(),lambda:None);service.linked_library=self.lib;gguf(self.folder/'a.gguf');service.scan({});self.scan();service.apply_model.assert_not_called()
 def test_21_snapshot_is_copy(self):gguf(self.folder/'a.gguf');state=self.scan();state['models'].clear();self.assertEqual(self.lib.snapshot()['count'],1)
 def test_22_truncated_header_hidden(self):(self.folder/'small.gguf').write_bytes(b'GGUF');self.assertEqual(self.scan()['count'],0)
 def test_23_corrupt_config_requires_relink(self):
  self.lib.config.write_text('not json');other=Library(self.home,self.folder,start=False);other.scan_once();self.assertTrue(other.snapshot()['error']);other.set_folder(str(self.folder));self.assertIsNone(other.snapshot()['error']);other.close()
 def test_24_explicit_model_loading_still_requires_confirmation(self):
  import model_settings
  service=model_settings.Service(self.home,lambda:{'model':'unchanged'},Mock(),threading.Lock(),lambda:None)
  with self.assertRaisesRegex(ValueError,'Confirm'):service.start({'model':'anything.gguf'})
  service.apply_model.assert_not_called()
 def test_25_actual_background_discovery(self):
  running=Library(self.home,self.folder,interval=1);gguf(self.folder/'a.gguf');deadline=time.monotonic()+5
  while not running.snapshot()['count'] and time.monotonic()<deadline:time.sleep(.05)
  self.assertEqual(running.snapshot()['count'],1);running.close();self.assertFalse(running.thread.is_alive())
 def test_26_no_nested_junction_traversal(self):
  outside=self.root/'outside';outside.mkdir();gguf(outside/'outside.gguf')
  with patch('model_library.linked',side_effect=lambda p:p.name=='external'):
   (self.folder/'external').mkdir();gguf(self.folder/'external'/'outside.gguf');self.assertEqual(self.scan()['count'],0)
 def test_27_sorted_by_name(self):gguf(self.folder/'Z.gguf');gguf(self.folder/'a.gguf');self.assertEqual([m['name'] for m in self.scan()['models']],['a.gguf','Z.gguf'])
 def test_28_depth_bounded(self):gguf(self.folder/'a/b/c/d/e/f.gguf');self.assertEqual(self.scan()['count'],0)
 def test_29_library_request_scan_preserves_profile(self):
  profile=self.home/'profile.json';profile.write_text('{"model":"original"}');gguf(self.folder/'a.gguf');self.scan();self.assertEqual(profile.read_text(),'{"model":"original"}')
 def route(self,path,body=None,origin='http://127.0.0.1:8087'):
  import model_settings,io
  service=model_settings.Service(self.home,lambda:{'model':'unchanged'},Mock(),threading.Lock(),lambda:None);service.linked_library=self.lib;service.snapshot=lambda:{'modelFolder':self.lib.snapshot()};raw=json.dumps(body or {}).encode();replies=[]
  handler=Mock();handler.path=path;handler.headers={'Origin':origin,'Host':'127.0.0.1:8087','Content-Length':str(len(raw))};handler.rfile=io.BytesIO(raw);handler.allowed.return_value=True;handler.json=lambda code,value:replies.append((code,value))
  self.assertTrue(model_settings.route(handler,body is not None,service));return replies[0]
 def test_30_state_endpoint_reports_link(self):
  code,value=self.route('/local-models/state');self.assertEqual(code,200);self.assertEqual(value['modelFolder']['folder'],str(self.folder))
 def test_31_link_endpoint_persists(self):
  other=self.root/'other';other.mkdir();code,value=self.route('/local-models/folder',{'folder':str(other)});self.assertEqual(code,200);self.assertEqual(self.lib.folder,other)
 def test_32_foreign_origin_cannot_link(self):
  code,value=self.route('/local-models/folder',{'folder':str(self.root)},origin='https://evil.example');self.assertEqual(code,403);self.assertEqual(self.lib.folder,self.folder)
 def test_33_bad_link_returns_useful_error(self):
  code,value=self.route('/local-models/folder',{'folder':'relative'});self.assertEqual(code,400);self.assertIn('full',value['error'])
 def test_34_open_only_linked_folder(self):
  with patch('os.startfile') as opened:
   code,value=self.route('/local-models/open-folder',{});self.assertEqual(code,200);opened.assert_called_once_with(str(self.folder))
 def test_35_picker_is_explicit_user_worker(self):
  import intelligence.process
  with patch('intelligence.process.run',return_value={'path':None}) as worker:
   code,value=self.route('/local-models/pick-folder',{});self.assertEqual(code,200);self.assertIsNone(value['path']);self.assertEqual(worker.call_args.args[1]['kind'],'model-folder');self.assertEqual(self.lib.folder,self.folder)
if __name__=='__main__':
 sys.path.insert(0,str(Path('tests_search').resolve()));from regressions import Capture
 result=unittest.TextTestRunner(verbosity=1,resultclass=Capture).run(unittest.defaultTestLoader.loadTestsFromTestCase(Cases));Path('docs/model-folder-results.json').write_text(json.dumps(result.rows,indent=2),encoding='utf8');sys.exit(not result.wasSuccessful())
