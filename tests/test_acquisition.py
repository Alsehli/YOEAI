import sys,tempfile,unittest,hashlib,threading,types
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,r'F:\YOEAI-Autonomy\Source')
import update_acquire as a
U='https://raw.githubusercontent.com/google/fonts/'+'a'*40+'/ofl/test/Test.ttf'
L=U.rsplit('/',1)[0]+'/OFL.txt'
FONT=b'\0\1\0\0'+b'\0\1'+b'\0'*6+b'name'+b'\0'*4+(28).to_bytes(4,'big')+(4).to_bytes(4,'big')+b'test'
class Tests(unittest.TestCase):
 def test_urls(self):
  a.check_url(U)
  for u in ['http://localhost/x','https://raw.githubusercontent.com/x/y/main/a.ttf',U+'?secret=a',U.replace('raw.githubusercontent.com','evil.com'),U.replace('/ofl/','/../')]:
   with self.assertRaises(ValueError):a.check_url(u)
 def test_lifecycle(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'assets/fonts').mkdir(parents=True);m=types.SimpleNamespace(home=root,root=root,audit=lambda *x:None);x=a.Acquisition(m);b=dict(approve=True,url=U,licenseUrl=L,sha256=hashlib.sha256(FONT).hexdigest())
   with patch.object(a,'fetch',side_effect=[b'SIL OPEN FONT LICENSE Version 1.1',FONT]):r=x.download(b)
   native=types.SimpleNamespace(approve=lambda *x:False)
   with patch.dict(sys.modules,{'update_native':native}):
    with self.assertRaises(ValueError):x.install(dict(approve=True,id=r['id'],digest=r['sha256']))
   self.assertFalse(list((root/'assets/fonts').glob('*.ttf')))
   native.approve=lambda *x:True
   with patch.dict(sys.modules,{'update_native':native}):
    r=x.install(dict(approve=True,id=r['id'],digest=r['sha256']));self.assertEqual(r['status'],'INSTALLED');r=x.rollback(dict(approve=True,id=r['id']));self.assertEqual(r['status'],'ROLLED_BACK')
 def test_hash_and_binary(self):
  with tempfile.TemporaryDirectory() as d:
   m=types.SimpleNamespace(home=Path(d),root=Path(d),audit=lambda *x:None);x=a.Acquisition(m)
   with patch.object(a,'fetch',side_effect=[b'MIT License',b'not font']):
    with self.assertRaises(ValueError):x.download(dict(approve=True,url=U,licenseUrl=L,sha256='0'*64))
 def test_no_redirect(self):
  with self.assertRaises(ValueError):a.NoRedirect().redirect_request(None,None,None,None,None,None)
if __name__=='__main__':unittest.main()
