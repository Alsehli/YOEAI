import hashlib,io,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch,Mock
import online_setup as setup
class Response(io.BytesIO):
 status=200;headers={}
 def geturl(self):return 'https://example.test/file'
class DownloadTests(unittest.TestCase):
 def test_new_file_is_verified(self):
  data=b'verified test payload';digest=hashlib.sha256(data).hexdigest()
  with tempfile.TemporaryDirectory() as folder,patch.object(setup.HTTP,'open',return_value=Response(data)):
   path=Path(folder)/'file';setup.download('https://example.test/file',path,len(data),digest);self.assertEqual(path.read_bytes(),data)
 def test_cached_file_skips_network(self):
  data=b'cached';digest=hashlib.sha256(data).hexdigest()
  with tempfile.TemporaryDirectory() as folder,patch.object(setup.HTTP,'open',side_effect=AssertionError('Unexpected network')):
   path=Path(folder)/'file';path.write_bytes(data);setup.download('https://example.test/file',path,len(data),digest)
 def test_range_ignored_restarts_safely(self):
  data=b'whole file';digest=hashlib.sha256(data).hexdigest()
  with tempfile.TemporaryDirectory() as folder,patch.object(setup.HTTP,'open',return_value=Response(data)):
   path=Path(folder)/'file';path.with_name('file.part').write_bytes(b'whole');setup.download('https://example.test/file',path,len(data),digest);self.assertEqual(path.read_bytes(),data)
 def test_corrupt_download_is_not_installed(self):
  with tempfile.TemporaryDirectory() as folder,patch.object(setup.HTTP,'open',return_value=Response(b'bad')):
   path=Path(folder)/'file'
   with self.assertRaises(RuntimeError):setup.download('https://example.test/file',path,3,hashlib.sha256(b'yes').hexdigest())
   self.assertFalse(path.exists());self.assertTrue(list(Path(folder).glob('*.unverified-*')))
 def test_zip_traversal_is_rejected(self):
  with tempfile.TemporaryDirectory() as folder:
   archive=Path(folder)/'bad.zip'
   with zipfile.ZipFile(archive,'w') as z:z.writestr('../escape',b'bad')
   with self.assertRaises(RuntimeError):setup.extract_verified(archive,Path(folder)/'backend')
 def test_offline_folder_skips_network(self):
  data=b'offline payload';digest=hashlib.sha256(data).hexdigest()
  with tempfile.TemporaryDirectory() as folder,patch.object(setup.HTTP,'open',side_effect=AssertionError('Network must not be used')):
   root=Path(folder);offline=root/'offline';(offline/'Models').mkdir(parents=True);(offline/'Models/file').write_bytes(data)
   result=setup.obtain_file('Models','file',len(data),digest,'https://example.test/file',root/'cache',offline)
   self.assertEqual(result.read_bytes(),data)
 def test_invalid_offline_folder_does_not_download(self):
  with tempfile.TemporaryDirectory() as folder,patch.object(setup.HTTP,'open',side_effect=AssertionError('Network must not be used')):
   root=Path(folder);offline=root/'offline';offline.mkdir()
   with self.assertRaises(RuntimeError):setup.obtain_file('Models','missing',3,'bad','https://example.test/file',root/'cache',offline)
if __name__=='__main__':unittest.main(verbosity=2)
