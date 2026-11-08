"""Portable Lite image contracts; no models, GPU or application writes."""
import importlib.util,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('lite_image_candidate',ROOT/'editions/lite/source/lite_image_generation.py')
MODULE=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(MODULE)
class LiteImageTests(unittest.TestCase):
 def test_invalid_request_never_launches(self):
  with tempfile.TemporaryDirectory() as directory:
   gen=MODULE.LiteGenerator(Path(directory)/'missing.json',directory,max_size=768)
   for value in [None,[],{'prompt':'x','size':1024},{'prompt':'','size':512}]:
    with self.assertRaises(ValueError):gen.start(value)
   self.assertIsNone(gen.process)
 def test_normal_budget_is_not_inherited_on_8gb(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);files={k:str(root/k) for k in ['executable','diffusion','encoder','vae']}
   for file in files.values():Path(file).write_bytes(b'fixture')
   config=root/'config.json';config.write_text(json.dumps(dict(files,arguments=['--max-vram','cuda0=12'])),encoding='utf8')
   gen=MODULE.LiteGenerator(config,root/'output',max_size=768)
   with patch.object(MODULE.subprocess,'check_output',return_value='8192\n'):
    options=gen.config()['arguments'];self.assertEqual(options[options.index('--max-vram')+1],'cuda0=6')
 def test_foreign_configuration_is_rejected(self):
  class Handler:
   path='/imagegen/configure';headers={'Host':'127.0.0.1:8000','Origin':'https://example.com'}
   def allowed(self):return False
   def reply(self,code,value):self.code=code
  h=Handler();self.assertTrue(MODULE.route(h,True,ROOT,ROOT,ROOT,lambda:{}));self.assertEqual(h.code,403)
