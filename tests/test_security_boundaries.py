"""Disposable path, network and approval-boundary checks; no external requests or native UI."""
import json,os,sys,tempfile,unittest,socket
from pathlib import Path
from unittest.mock import patch,Mock,MagicMock
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'source'))
import security_paths as p
import public_transport,control_web_evidence,update_acquire,update_manager,mini_agents
class SecurityBoundaryTests(unittest.TestCase):
 def test_absolute_selection_preserves_unicode_and_spaces(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'tests') as d:
   q=Path(d)/'نماذج models'/'model.gguf';self.assertEqual(p.user_local_path(str(q)),q)
 def test_selection_rejects_network_devices_and_relative(self):
  for value in ['../model.gguf','model.gguf',r'\\host\share\file',r'\\.\PhysicalDrive0']:
   with self.subTest(value=value),self.assertRaises(ValueError):p.user_local_path(value)
 def test_segment_rejects_escape_and_streams(self):
  for value in ['../file','a/../file','a:stream','a\x00b','trailing.','trailing ','NUL','CON.txt']:
   with self.subTest(value=value),self.assertRaises(ValueError):p.segments(value)
 def test_relative_path_stays_in_root(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'tests') as d:
   self.assertEqual(p.relative_path(Path(d),'nested/file.txt'),Path(d)/'nested/file.txt')
   for value in ['/file','../file',r'C:\file',r'\file']:
    with self.subTest(value=value),self.assertRaises(ValueError):p.relative_path(Path(d),value)
 def test_job_ids_are_exact_canonical_hex(self):
  self.assertEqual(p.job_id('a'*32),'a'*32)
  for x in ['../x','A'*32,'a'*31,'a'*34,None]:
   with self.subTest(value=x),self.assertRaises(ValueError):p.job_id(x)
 def test_private_transport_addresses_rejected(self):
  for value in ['127.0.0.1','10.0.0.1','169.254.169.254','::1','fe80::1','::ffff:127.0.0.1']:
   with self.subTest(value=value),self.assertRaises(ValueError):public_transport.PublicHTTPSConnection('example.com',value)
 def test_transport_uses_validated_ip_without_second_dns_lookup(self):
  conn=public_transport.PublicHTTPSConnection('example.com','93.184.216.34')
  with patch('public_transport.socket.create_connection',return_value=object()) as connect:
   conn._create_connection(('127.0.0.1',80),3)
   self.assertEqual(connect.call_args.args[0],('93.184.216.34',443));self.assertEqual(conn.host,'example.com')
 def test_reader_rejects_non_https_and_private_resolution(self):
  for value in ['http://example.com','file:///x','https://localhost','https://example.com:8443']:
   with self.subTest(value=value),patch('control_web_evidence.socket.getaddrinfo',return_value=[(socket.AF_INET,socket.SOCK_STREAM,6,'',('127.0.0.1',443))]),self.assertRaises(ValueError):control_web_evidence.destination(value)
 def test_mixed_dns_answers_are_rejected(self):
  answers=[(socket.AF_INET,socket.SOCK_STREAM,6,'',('93.184.216.34',443)),(socket.AF_INET,socket.SOCK_STREAM,6,'',('10.0.0.1',443))]
  with patch('control_web_evidence.socket.getaddrinfo',return_value=answers),self.assertRaises(ValueError):control_web_evidence.destination('https://example.com')
 def test_acquisition_rebuilds_fixed_origin(self):
  url='https://raw.githubusercontent.com/owner/repo/'+'a'*40+'/folder/file.txt';response=Mock();response.headers={};response.read.return_value=b'source';opener=MagicMock();opener.open.return_value.__enter__.return_value=response
  with patch('update_acquire.urllib.request.build_opener',return_value=opener):self.assertEqual(update_acquire.fetch(url),b'source')
  self.assertEqual(opener.open.call_args.args[0].full_url,url)
 def test_acquisition_redirects_fail_closed(self):
  with self.assertRaises(ValueError):update_acquire.NoRedirect().redirect_request(None,None,None,None,None,None)
 def test_update_inventory_excludes_models_and_unknown_paths(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'tests') as d:
   root=Path(d);(root/'assets').mkdir();(root/'Models').mkdir();(root/'assets/theme.css').write_text('body{}');(root/'Models/example.js').write_text('secret');(root/'ui.html').write_text('UI')
   self.assertEqual(update_manager.target(root,'assets/theme.css'),root/'assets/theme.css')
   for name in ['Models/example.js','assets/../ui.html','assets/new.css','/ui.html']:
    with self.subTest(name=name),self.assertRaises(ValueError):update_manager.target(root,name)
 def test_project_scope_and_reparse_policy_still_apply(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'tests') as d:
   root=Path(d);project=root/'project';project.mkdir();f=project/'source.py';f.write_text('print(1)');self.assertEqual(mini_agents.scoped(mini_agents.clean_root(str(project)),'source.py'),f)
   for name in ['../outside.py','.ssh/id_rsa','source.py:stream']:
    with self.subTest(name=name),self.assertRaises(ValueError):mini_agents.scoped(project,name)
 def test_secret_rejection_is_bounded_and_still_matches_headers(self):
  mini_agents.reject_secrets('-----BEGIN '*10000)
  with self.assertRaises(ValueError):mini_agents.reject_secrets('-----BEGIN '+'PRIVATE KEY-----')
if __name__=='__main__':unittest.main()
