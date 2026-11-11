import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import app

class FirstLaunchTests(unittest.TestCase):
 def test_packaged_download_opens_setup(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);(root/'Runtime').mkdir();(root/'package-manifest.json').write_text('{}')
   with patch.object(app,'APP',root),patch.object(app,'CONFIG',root/'profile.json'):
    self.assertTrue(app.needs_setup())
 def test_existing_profile_is_preserved(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);(root/'Runtime').mkdir();(root/'package-manifest.json').write_text('{}');(root/'profile.json').write_text('{}')
   with patch.object(app,'APP',root),patch.object(app,'CONFIG',root/'profile.json'):
    self.assertFalse(app.needs_setup())
 def test_installed_app_does_not_open_setup(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder)
   with patch.object(app,'APP',root),patch.object(app,'CONFIG',root/'profile.json'):
    self.assertFalse(app.needs_setup())

if __name__=='__main__':unittest.main(verbosity=2)
