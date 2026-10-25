import unittest,tempfile,threading,time,os,json
from pathlib import Path
from windows_explorer import Explorer

class Engine:
 def __init__(self,home):self.home=home;self.home.mkdir();self.windows_enabled=True;self.closed=False;self.db_lock=threading.RLock()

class ExplorerTests(unittest.TestCase):
 def setUp(self):
  fixtures=Path('F:/YOEAI-Autonomy/Storage-Explorer/Fixtures');fixtures.mkdir(parents=True,exist_ok=True)
  self.tmp=tempfile.TemporaryDirectory(dir=fixtures);self.base=Path(self.tmp.name);self.root=self.base/'Approved';self.root.mkdir();self.dest=self.base/'Destination';self.dest.mkdir();self.e=Engine(self.base/'Profile');self.x=Explorer(self.e);self.sid=self.x.grant(str(self.root))['id'];self.target=self.x.grant(str(self.dest))['id']
 def tearDown(self):
  self.e.closed=True
  for j in self.x.jobs.values():j['cancel'].set()
  time.sleep(.04)
  if self.base.exists() and os.name=='nt':
   import shutil
   assert self.base.resolve().parent==Path('F:/YOEAI-Autonomy/Storage-Explorer/Fixtures').resolve()
   shutil.rmtree('\\\\?\\'+str(self.base.resolve()))
  self.tmp.cleanup()
 def wait(self,j):
  for _ in range(500):
   value=self.x.state(j['id'])
   if value['status']!='RUNNING':time.sleep(.02);return value
   time.sleep(.01)
  self.fail('Job did not finish')
 def act(self,operation,paths,**extra):
  plan=self.x.propose(dict(scope=self.sid,operation=operation,paths=paths,**extra));return self.wait(self.x.execute(plan['id'],True))
 def test_empty_and_paginated_listing(self):
  self.wait(j:=self.x.start(self.sid));self.assertEqual(self.x.listing(j['id'])['rows'],[])
  for i in range(230):(self.root/f'file-{i:04}.txt').write_text('a')
  self.wait(j:=self.x.start(self.sid));page=self.x.listing(j['id']);self.assertEqual(len(page['rows']),100);self.assertEqual(page['total'],230);self.assertEqual(self.x.listing(j['id'],200)['rows'][0]['name'],'file-0200.txt')
 def test_recursive_actual_sizes_and_category_filter(self):
  (self.root/'Nested').mkdir();(self.root/'Nested/a.gguf').write_bytes(b'G'*32);(self.root/'b.txt').write_bytes(b'T'*10)
  self.wait(j:=self.x.start(self.sid,recursive=True));d=self.x.dashboard(j['id']);self.assertEqual(sum(c['bytes'] for c in d['categories']),42);self.assertEqual(d['largestFolders'][0]['bytes'],32);self.assertEqual(self.x.listing(j['id'],cat='AI Models')['rows'][0]['name'],'a.gguf')
 def test_hidden_and_protected_names(self):
  (self.root/'.hidden.txt').write_text('x');(self.root/'password.txt').write_text('secret');(self.root/'Windows').mkdir()
  self.wait(j:=self.x.start(self.sid));self.assertEqual(self.x.listing(j['id'])['total'],0)
  self.wait(j:=self.x.start(self.sid,show_hidden=True));self.assertEqual(self.x.listing(j['id'])['total'],1)
 def test_traversal_and_revoke(self):
  for path in ['../outside','C:/Windows','a/../../b']:
   with self.assertRaises(ValueError):self.x.path(self.sid,path,False)
  self.x.revoke(self.sid)
  with self.assertRaises(ValueError):self.x.start(self.sid)
 def test_copy_move_and_no_overwrite(self):
  (self.root/'a.txt').write_text('verified content');out=self.act('copy',['a.txt'],targetScope=self.target);self.assertEqual(out['status'],'COMPLETED');self.assertEqual((self.dest/'a.txt').read_text(),'verified content')
  with self.assertRaises(ValueError):self.x.propose(dict(scope=self.sid,operation='copy',paths=['a.txt'],targetScope=self.target))
  (self.root/'b.txt').write_text('move');out=self.act('move',['b.txt'],targetScope=self.target);self.assertEqual(out['status'],'COMPLETED');self.assertFalse((self.root/'b.txt').exists());self.assertEqual((self.dest/'b.txt').read_text(),'move')
 def test_rename_and_new_folder_arabic(self):
  (self.root/'صورة.txt').write_text('test');self.assertEqual(self.act('rename',['صورة.txt'],name='ملف.txt')['status'],'COMPLETED');self.assertTrue((self.root/'ملف.txt').exists());self.assertEqual(self.act('mkdir',[''],name='صور')['status'],'COMPLETED');self.assertTrue((self.root/'صور').is_dir())
 def test_approval_single_use_changed_file_and_disabled(self):
  (self.root/'a.txt').write_text('old');plan=self.x.propose(dict(scope=self.sid,operation='rename',paths=['a.txt'],name='b.txt'));(self.root/'a.txt').write_text('changed')
  with self.assertRaises(ValueError):self.x.execute(plan['id'],True)
  plan=self.x.propose(dict(scope=self.sid,operation='rename',paths=['a.txt'],name='b.txt'));self.e.windows_enabled=False
  with self.assertRaises(ValueError):self.x.execute(plan['id'],True)
  self.assertTrue((self.root/'a.txt').exists())
 def test_protected_model_and_executable_open(self):
  (self.root/'model.gguf').write_text('model');(self.root/'setup.exe').write_text('exe')
  for op,name in [('recycle','model.gguf'),('open','setup.exe')]:
   with self.assertRaises(ValueError):self.x.propose(dict(scope=self.sid,operation=op,paths=[name]))
 def test_source_link_rejected(self):
  target=self.base/'Outside';target.mkdir()
  try:os.symlink(target,self.root/'link',target_is_directory=True)
  except OSError:self.skipTest('Symlink creation unavailable without Windows developer privilege')
  with self.assertRaises(ValueError):self.x.path(self.sid,'link')
 def test_cancel_scan(self):
  for i in range(1500):(self.root/f'{i}.txt').touch()
  j=self.x.start(self.sid);self.x.jobs[j['id']]['cancel'].set();value=self.wait(j);self.assertEqual(value['status'],'CANCELLED');self.assertLess(value['count'],1500)
 def test_folder_copy_and_atomic_move(self):
  (self.root/'Tree/sub').mkdir(parents=True);(self.root/'Tree/sub/a.txt').write_text('inside')
  result=self.act('copy',['Tree'],targetScope=self.target);self.assertEqual(result['status'],'COMPLETED');self.assertEqual((self.dest/'Tree/sub/a.txt').read_text(),'inside')
  (self.root/'MoveTree').mkdir();(self.root/'MoveTree/x.txt').write_text('x');result=self.act('move',['MoveTree'],targetScope=self.target);self.assertEqual(result['status'],'COMPLETED');self.assertFalse((self.root/'MoveTree').exists())
 def test_verified_duplicates_not_same_size_only(self):
  for name,data in [('one.txt','same'),('two.txt','same'),('other.txt','xxxx')]:(self.root/name).write_text(data)
  result=self.wait(self.x.verify_duplicates(self.sid,['one.txt','two.txt','other.txt']));self.assertEqual(result['status'],'COMPLETED');self.assertEqual(result['results'][0]['paths'],['one.txt','two.txt']);self.assertTrue(result['results'][0]['contentVerified']);self.assertTrue((self.root/'two.txt').exists())
 def test_organization_conflicts_and_undo(self):
  (self.root/'a.txt').write_text('a');(self.root/'b.txt').write_text('b');(self.root/'Documents').mkdir();(self.root/'Documents/b.txt').write_text('existing')
  self.wait(j:=self.x.start(self.sid));plan=self.x.organize_plan(j['id']);self.assertEqual(len(plan['items']),1);self.assertEqual(len(plan['conflicts']),1)
  result=self.wait(self.x.execute(plan['id'],True));self.assertEqual(result['status'],'COMPLETED');self.assertEqual((self.root/'Documents/a.txt').read_text(),'a');self.assertEqual((self.root/'Documents/b.txt').read_text(),'existing')
  undo=self.x.undo_plan(result['id']);restored=self.wait(self.x.execute(undo['id'],True));self.assertEqual(restored['status'],'COMPLETED');self.assertEqual((self.root/'a.txt').read_text(),'a')
 def test_low_space_blocks_copy(self):
  from unittest.mock import patch
  (self.root/'a.txt').write_text('a');plan=self.x.propose(dict(scope=self.sid,operation='copy',paths=['a.txt'],targetScope=self.target))
  with patch('windows_explorer.shutil.disk_usage',return_value=type('Usage',(),{'free':0})()):
   with self.assertRaises(ValueError):self.x.execute(plan['id'],True)
  self.assertFalse((self.dest/'a.txt').exists())
 def test_locked_file_detected(self):
  import ctypes
  from ctypes import wintypes
  (self.root/'a.txt').write_text('a');k=ctypes.WinDLL('kernel32');k.CreateFileW.restype=wintypes.HANDLE;k.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE];k.CloseHandle.argtypes=[wintypes.HANDLE]
  h=k.CreateFileW(str(self.root/'a.txt'),0x80000000,0,None,3,0,None)
  try:
   with self.assertRaises(OSError):self.x.propose(dict(scope=self.sid,operation='recycle',paths=['a.txt']))
  finally:k.CloseHandle(h)
 def test_agent_cannot_recycle_protected_data(self):
  from windows_policy import validate_action,make_scope
  scope=make_scope({'mode':'ADVANCED','folder':str(self.root),'apps':[]})
  for name in ['config.json','project.py','engine.dll','weights.gguf','data.sqlite3']:
   (self.root/name).write_text('protected')
   with self.assertRaises(ValueError):validate_action({'tool':'files_recycle','params':{'path':name}},scope)
   self.assertTrue((self.root/name).exists())
 def test_recycle_failure_keeps_original(self):
  from unittest.mock import patch
  (self.root/'a.txt').write_text('keep')
  with patch('windows_tools.files_tool',side_effect=OSError('Recycle Bin unavailable')):result=self.act('recycle',['a.txt'])
  self.assertEqual(result['status'],'FAILED');self.assertEqual((self.root/'a.txt').read_text(),'keep')
 def test_restart_recovers_without_repeating(self):
  (self.root/'a.txt').write_text('keep');plan=self.x.propose(dict(scope=self.sid,operation='move',paths=['a.txt'],targetScope=self.target))
  j={'id':'interrupted','scope':self.sid,'status':'RUNNING','created':time.time(),'count':0,'bytes':0,'cancel':threading.Event(),'results':[]};self.x.jobs[j['id']]=j;self.x.journal(plan,j);j['status']='CANCELLED'
  recovered=Explorer(self.e);self.assertGreaterEqual(recovered.recovered,1);self.assertEqual(recovered.history()['actions'][0]['status'],'INTERRUPTED');self.assertTrue((self.root/'a.txt').exists());self.assertFalse((self.dest/'a.txt').exists())
 def test_long_paths(self):
  deep=self.root/('a'*100)/('b'*100)/('c'*60)
  try:
   native=self.x.path(self.sid,deep.relative_to(self.root).as_posix(),False);native.mkdir(parents=True);(native/'long.txt').write_text('long')
  except OSError as error:self.skipTest('This Windows environment does not enable long paths: '+str(error))
  self.assertEqual(self.x.path(self.sid,(deep/'long.txt').relative_to(self.root).as_posix()).read_text(),'long')

 def test_scope_namespace_security(self):
  from windows_policy import root_folder
  for folder in [str(Path.home()),'\\\\?\\'+str(Path.home()),'C:/Windows','F:/','\\\\.\\PhysicalDrive0','\\\\?\\GLOBALROOT\\Device']:
   with self.assertRaises((ValueError,OSError)):root_folder(folder)
 def test_folder_into_itself(self):
  (self.root/'Tree/sub').mkdir(parents=True)
  with self.assertRaises(ValueError):self.x.propose(dict(scope=self.sid,operation='copy',paths=['Tree'],destination='Tree/sub'))
 def test_expired_approval(self):
  (self.root/'a.txt').write_text('keep');plan=self.x.propose(dict(scope=self.sid,operation='rename',paths=['a.txt'],name='new.txt'));self.x.pending[plan['id']]['expires']=0
  with self.assertRaises(ValueError):self.x.execute(plan['id'],True)
  self.assertTrue((self.root/'a.txt').exists())
 def test_signature_does_not_trust_extension(self):
  (self.root/'fake.pdf').write_text('not a pdf');self.assertIn('Not identified',self.x.properties(self.sid,'fake.pdf')['signature'])
 def test_large_model_metadata_no_full_read(self):
  import ctypes,msvcrt
  with (self.root/'huge.gguf').open('wb') as f:
   f.write(b'GGUF');f.flush();done=ctypes.c_ulong();ok=ctypes.windll.kernel32.DeviceIoControl(ctypes.c_void_p(msvcrt.get_osfhandle(f.fileno())),0x900c4,None,0,None,0,ctypes.byref(done),None)
   if not ok:self.skipTest('Sparse file fixture unavailable')
   handle=ctypes.c_void_p(msvcrt.get_osfhandle(f.fileno()));ctypes.windll.kernel32.SetFilePointerEx(handle,ctypes.c_longlong(8*1024**3),None,0)
   if not ctypes.windll.kernel32.SetEndOfFile(handle):raise ctypes.WinError()
  # Sparse allocation avoids filling the fixture disk.
  self.wait(j:=self.x.start(self.sid));self.assertEqual(self.x.dashboard(j['id'])['categories'][0]['bytes'],8*1024**3)

 def test_real_recycle_disposable_file(self):
  (self.root/'disposable-recycle-test.txt').write_text('Disposable YOEAI file-explorer test only.')
  result=self.act('recycle',['disposable-recycle-test.txt']);self.assertEqual(result['status'],'COMPLETED',result);self.assertFalse((self.root/'disposable-recycle-test.txt').exists());self.assertTrue(result['results'][0]['verified'])
 def test_real_cross_drive_move(self):
  import uuid,shutil
  if not Path('D:/').is_dir():self.skipTest('D drive unavailable')
  target=Path('D:/YOEAI-Storage-Test-'+uuid.uuid4().hex);target.mkdir()
  try:
   tid=self.x.grant(str(target))['id'];(self.root/'cross-drive.txt').write_text('cross-drive fixture')
   result=self.act('move',['cross-drive.txt'],targetScope=tid);self.assertEqual(result['status'],'COMPLETED',result);self.assertEqual((target/'cross-drive.txt').read_text(),'cross-drive fixture');self.assertFalse((self.root/'cross-drive.txt').exists())
  finally:
   assert target.parent==Path('D:/') and target.name.startswith('YOEAI-Storage-Test-')
   shutil.rmtree(target)
 def test_denied_scan_reports_partial(self):
  from unittest.mock import patch
  with patch('windows_explorer.os.scandir',side_effect=PermissionError('fixture denied')):
   result=self.wait(self.x.start(self.sid));self.assertTrue(result['partial']);self.assertEqual(result['skipped'],1)
 def test_video_compatibility_preview(self):
  import subprocess
  from video_generation_adapter import generator
  ffmpeg=generator().config(require=False)['ffmpeg']
  subprocess.run([ffmpeg,'-v','error','-f','lavfi','-i','color=c=blue:s=160x96:d=1','-c:v','libx264',str(self.root/'clip.mp4')],check=True,timeout=15,creationflags=0x08000000)
  result=self.wait(self.x.video_preview(self.sid,'clip.mp4'));self.assertEqual(result['status'],'COMPLETED',result);self.assertGreater((self.x.home/'VideoPreviews'/(result['id']+'.webm')).stat().st_size,20)
