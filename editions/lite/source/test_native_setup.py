import json,os,socket,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import native_update as native
import online_setup as setup

class NativeSetupTests(unittest.TestCase):
 def setUp(self):
  self.probe=patch("native_payload.check",return_value={"cuda":True});self.probe.start();self.addCleanup(self.probe.stop)
 def fixture(self,root,legacy=False):
  data=root/'data';installed=data/'App/0.1.0';installed.mkdir(parents=True);(installed/'Backend').mkdir()
  old=installed/('AlsehliAILite.exe' if legacy else 'YOEAILite.exe');old.write_bytes(b'previous app')
  for name in ['model.gguf','projector.gguf']:(installed/name).write_bytes(name.encode())
  profile={'backend':str(installed/'Backend/llama-server.exe'),'model':str(installed/'model.gguf'),'projector':str(installed/'projector.gguf'),'apiPort':29281,'uiPort':29282,'context':8192}
  (data/'profile.json').write_text(json.dumps(profile),encoding='utf-8');payload=root/'payload';payload.mkdir();(payload/'YOEAILite.exe').write_bytes(b'new app')
  return data,installed,payload,profile
 def test_existing_profile_models_and_context_preserved(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);data,installed,payload,profile=self.fixture(root);original=(data/'profile.json').read_bytes()
   result=native.update(payload,data,make_shortcut=lambda exe:root/'YOEAI Lite.lnk',stopper=lambda exe:None)
   self.assertEqual((installed/'YOEAILite.exe').read_bytes(),b'new app');self.assertEqual((data/'profile.json').read_bytes(),original);self.assertEqual((installed/'model.gguf').read_bytes(),b'model.gguf');self.assertFalse(result['powershellUsed'])
   self.assertEqual((Path(result['backup'])/'YOEAILite.exe').read_bytes(),b'previous app')
 def test_legacy_exe_becomes_single_yoeai_app(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);data,installed,payload,_=self.fixture(root,True);native.update(payload,data,make_shortcut=lambda exe:root/'YOEAI Lite.lnk',stopper=lambda exe:None)
   self.assertTrue((installed/'YOEAILite.exe').exists());self.assertFalse((installed/'AlsehliAILite.exe').exists())
 def test_custom_backend_is_preserved(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);data,installed,payload,profile=self.fixture(root);profile['backend']=str(root/'custom/llama-server.exe');(data/'profile.json').write_text(json.dumps(profile),encoding='utf-8')
   with self.assertRaisesRegex(RuntimeError,'Custom backend'):native.update(payload,data)
   self.assertEqual((installed/'YOEAILite.exe').read_bytes(),b'previous app')
 def test_stop_failure_never_replaces_app(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);data,installed,payload,_=self.fixture(root)
   with self.assertRaisesRegex(RuntimeError,'Cannot stop'):native.update(payload,data,stopper=lambda exe:(_ for _ in ()).throw(RuntimeError('Cannot stop')))
   self.assertEqual((installed/'YOEAILite.exe').read_bytes(),b'previous app')
 def test_partial_installation_has_clear_error(self):
  with tempfile.TemporaryDirectory() as folder:
   with self.assertRaisesRegex(RuntimeError,'incomplete'):native.update(Path(folder),Path(folder))
 def test_new_profile_uses_yoeai_name(self):
  with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'LOCALAPPDATA':folder}):self.assertEqual(native.data_home(),Path(folder)/'YOEAILite')
 def test_old_profile_remains_in_place(self):
  with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'LOCALAPPDATA':folder}):
   legacy=Path(folder)/'AlsehliAILite';legacy.mkdir();(legacy/'profile.json').write_text('{}');self.assertEqual(native.data_home(),legacy)
 def test_offline_current_package_layout_detected(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);offline=root/'8GB-Lite';(offline/'Models').mkdir(parents=True);(offline/'Runtime').mkdir();self.assertEqual(setup.find_offline(root),offline)
 def test_native_shortcut_round_trip(self):
  import pythoncom,win32com.client
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);target=root/'YOEAILite.exe';target.write_bytes(b'test');dest=native.shortcut(target,root/'YOEAI Lite.lnk')
   pythoncom.CoInitialize()
   try:self.assertEqual(Path(win32com.client.Dispatch('WScript.Shell').CreateShortCut(str(dest)).TargetPath),target)
   finally:pythoncom.CoUninitialize()
 def test_setup_sources_never_invoke_powershell(self):
  for name in ['online_setup.py','native_update.py']:
   source=(Path(__file__).parent/name).read_text(encoding='utf-8')
   self.assertNotIn("'powershell.exe'",source);self.assertNotIn('ExecutionPolicy',source);self.assertNotIn('Update-Installed-Lite.ps1',source)
 def test_fresh_offline_setup_installs_without_network_or_script_policy(self):
  import hashlib,zipfile
  from collections import namedtuple
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);payload=root/'payload';payload.mkdir();(payload/'YOEAILite.exe').write_bytes(b'new app')
   for name in ['Documents','Licenses','Source','Speech','RuntimeSupport','NativeEngine','NativeRuntime']:(payload/name).mkdir()
   (payload/'package-manifest.json').write_text(json.dumps({'files':[{'path':'YOEAILite.exe','size':7,'sha256':hashlib.sha256(b'new app').hexdigest()}]}),encoding='utf-8')
   offline=root/'8GB-Lite';(offline/'Models').mkdir(parents=True);(offline/'Runtime').mkdir()
   (offline/'Models/model.gguf').write_bytes(b'model');(offline/'Models/projector.gguf').write_bytes(b'projector')
   with zipfile.ZipFile(offline/'Runtime/runtime.zip','w') as z:z.writestr('llama-server.exe',b'fixture backend')
   files=[]
   for category,name in [('Models','model.gguf'),('Models','projector.gguf')]:
    p=offline/category/name;files.append((category,name,p.stat().st_size,hashlib.sha256(p.read_bytes()).hexdigest(),'https://example.test/unused'))
   edge=root/'Programs/Microsoft/Edge/Application/msedge.exe';edge.parent.mkdir(parents=True);edge.write_bytes(b'edge fixture');desktop=root/'Desktop';desktop.mkdir()
   usage=namedtuple('Usage','total used free')(100_000_000_000,0,100_000_000_000)
   with patch.object(setup,'PAYLOAD',payload),patch.object(setup,'DATA',root/'data'),patch.object(setup,'OFFLINE_ROOT',root),patch.object(setup,'FILES',files),patch.object(setup,'desktop_folder',return_value=desktop),patch.object(setup,'shortcut',side_effect=lambda exe,dest:Path(dest).write_bytes(b'fixture shortcut')),patch.object(setup.shutil,'disk_usage',return_value=usage),patch.object(setup.subprocess,'check_output',return_value='8192\n'),patch.object(setup.HTTP,'open',side_effect=AssertionError('Network forbidden')),patch.dict(os.environ,{'PROGRAMFILES(X86)':str(root/'Programs')}):
    self.assertIn('Installed',setup.install())
   config=json.loads((root/'data/profile.json').read_text());self.assertTrue(Path(config['model']).is_file());self.assertTrue(Path(config['projector']).is_file());self.assertEqual(config['inferenceEngine'],'native');self.assertNotIn('backend',config);self.assertEqual(config['context'],16384);self.assertTrue((desktop/'YOEAI Lite 2.0.lnk').exists())
if __name__=='__main__':unittest.main(verbosity=2)
