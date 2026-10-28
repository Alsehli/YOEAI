import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from video_generation import VideoGenerator

class LtxVideoTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
  self.c={'engine':'ltx'}
  for key in ('python','worker','ffmpeg','checkpoint','encoderIndex'):
   f=self.root/key;f.write_text('fixture');self.c[key]=str(f)
  self.c['gpuLock']=str(self.root/'gpu.lock');self.path=self.root/'config.json';self.path.write_text(json.dumps(self.c))
  self.v=VideoGenerator(self.path,self.root/'Outputs')
 def tearDown(self):self.v.shutdown();self.temp.cleanup()
 def test_config_no_legacy_weights(self):
  self.assertEqual(self.v.config()['engine'],'ltx');self.assertNotIn('diffusion',self.v.config())
 def test_missing_runtime_clear_error(self):
  (self.root/'worker').unlink()
  with self.assertRaisesRegex(ValueError,'worker'):self.v.config()
 def test_ltx_install_never_downloads_wan(self):
  with patch.object(self.v,'download',side_effect=AssertionError):self.assertTrue(self.v.install()['installed'])
 def test_progress(self):
  self.v.home.mkdir();self.v.state={'status':'running','id':'a'*32,'message':'Loading'}
  (self.v.home/('a'*32+'.progress.json')).write_text(json.dumps({'message':'Creating video · step 3 of 8','step':3,'steps':8}))
  self.assertEqual(self.v.status()['step'],3)
 def test_error_detail(self):
  log=self.root/'job.log';log.with_suffix('.progress.json').write_text(json.dumps({'error':True,'message':'CUDA out of memory'}))
  with patch('video_generation.subprocess.Popen') as process:
   process.return_value.wait.return_value=1
   with self.assertRaisesRegex(ValueError,'CUDA out of memory'):self.v.execute(['fixture'],log,1)
 def test_validation(self):
  for body in ({'prompt':''},{'prompt':'x','seconds':2},{'prompt':'x','quality':'unknown'}):
   with self.assertRaises(ValueError):self.v.start(body)
 def test_output(self):
  self.v.home.mkdir();p=self.v.home/('a'*32+'.mp4');p.write_bytes(b'fixture')
  self.assertEqual(self.v.output_path('a'*32),p)
 def test_preview_cache_and_original_preserved(self):
  import types
  self.v.home.mkdir();job='a'*32;original=self.v.home/(job+'.mp4');original.write_bytes(b'original-mp4')
  def convert(args,**kwargs):Path(args[-1]).write_bytes(b'webm-fixture'*200);return types.SimpleNamespace(returncode=0)
  with patch('video_generation.subprocess.run',side_effect=convert) as run:
   preview=self.v.preview_path(job);self.assertTrue(preview.name.endswith('.webm'));self.v.preview_path(job)
   self.assertEqual(run.call_count,1);self.assertIn('libvpx-vp9',run.call_args[0][0]);self.assertEqual(original.read_bytes(),b'original-mp4')
 def test_preview_invalid_id(self):
  with self.assertRaisesRegex(ValueError,'Invalid'):self.v.preview_path('../private')

if __name__=='__main__':unittest.main()
