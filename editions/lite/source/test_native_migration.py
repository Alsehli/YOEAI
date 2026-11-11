import ast,unittest
from pathlib import Path
S=Path(__file__).parent
class NativeMigration(unittest.TestCase):
 def test_no_model_http_client(self):
  for name in ['app.py','mini_agents.py','developer_mode.py','language_understanding.py']:
   tree=ast.parse((S/name).read_text(encoding='utf8'))
   for n in ast.walk(tree):
    if isinstance(n,ast.Call)and isinstance(n.func,ast.Attribute):self.assertNotEqual(n.func.attr,'HTTPConnection',name)
 def test_utf8_interface_symbols(self):
  text=(S/'ui.html').read_text(encoding='utf8')
  self.assertIn('\u2122',text)
  for bad in ['\u00e2\u20ac','\u00c3','\u00c2']:
   self.assertNotIn(bad,text)
 def test_arabic_detection_markers_preserved(self):
  text=(S/'language_understanding.py').read_text(encoding='utf8')
  self.assertEqual(sum('\u0600'<=c<='\u06ff'for c in text),4)
 def test_no_server_startup_or_runtime_downloads(self):
  self.assertNotIn('llama-server.exe',(S/'app.py').read_text(encoding='utf8'))
  import online_setup
  self.assertTrue(all(row[0]=='Models'for row in online_setup.FILES))
if __name__=='__main__':unittest.main(verbosity=2)
