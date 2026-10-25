import sys,unittest,tempfile,json,io,wave
from pathlib import Path
from unittest.mock import patch
sys.path[:0]=['F:/YOEAI-Autonomy/Source','F:/YOEAI-2.0/Web-Search/Dependencies']
from windows_policy import make_scope,validate_action,automatic
from windows_productivity import execute
from windows_tools import files_tool
from windows_understanding import link
class Productivity(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(dir=Path(__file__).parent);self.root=Path(self.temp.name);self.scope=make_scope({'mode':'ASSISTED','folder':str(self.root),'apps':['notepad','explorer']})
  from PIL import Image
  Image.new('RGB',(800,400),'blue').save(self.root/'صورة.png')
 def tearDown(self):self.temp.cleanup()
 def run_tool(self,name,p):validate_action({'tool':name,'params':p},self.scope);return execute(name,p,self.scope,{})
 def test_image_pdf_and_info(self):
  r=self.run_tool('images_pdf',{'paths':json.dumps(['صورة.png']),'destination':'صور.pdf','size':'a4'});self.assertTrue(r['verified']);self.assertEqual(r['pages'],1)
  self.assertEqual(self.run_tool('document_info',{'path':'صور.pdf'})['pages'],1)
 def test_pdf_operations(self):
  self.test_image_pdf_and_info()
  for op in ['merge','rotate','compress','a4']:
   r=self.run_tool('pdf_transform',{'paths':json.dumps(['صور.pdf','صور.pdf']),'destination':op+'.pdf','operation':op,'degrees':90});self.assertTrue(r['verified']);self.assertEqual(r['pages'],2)
  r=self.run_tool('pdf_transform',{'paths':json.dumps(['صور.pdf']),'destination':'extract','operation':'extract_images'});self.assertGreaterEqual(r['images'],1)
 def test_images(self):
  for op in ['rotate','contact_sheet']:
   r=self.run_tool('image_transform',{'paths':json.dumps(['صورة.png']),'destination':op+'.png','operation':op,'degrees':90});self.assertTrue(r['verified'])
 def test_office_formats(self):
  for fmt in ['docx','xlsx','pptx']:
   r=self.run_tool('office_create',{'destination':'ملف.'+fmt,'format':fmt,'title':'YOEAI اختبار','text':'Title\nHello\n\nSecond\nMore'});self.assertTrue(r['verified']);self.assertTrue(self.run_tool('document_info',{'path':'ملف.'+fmt})['verified'])
 def test_formula_block(self):
  from openpyxl import load_workbook
  self.run_tool('office_create',{'destination':'safe.xlsx','format':'xlsx','title':'Test','text':'=HYPERLINK("https://example.com")\t+1+2'})
  w=load_workbook(self.root/'safe.xlsx');self.assertEqual(w.active['A1'].data_type,'s');self.assertTrue(w.active['A1'].value.startswith("'="));w.close()
 def test_calendar(self):
  r=self.run_tool('calendar_draft',{'destination':'appointment.ics','title':'Meeting\nBEGIN:EVIL','start':'2026-11-01T10:00:00+03:00','minutes':30});self.assertTrue(r['verified']);self.assertFalse(r['activeReminder']);self.assertNotIn('\nBEGIN:EVIL',(self.root/'appointment.ics').read_text())
 def test_no_overwrite(self):
  p={'paths':json.dumps(['صورة.png']),'destination':'existing.pdf','size':'letter'};(self.root/'existing.pdf').write_bytes(b'keep')
  with self.assertRaises(ValueError):self.run_tool('images_pdf',p)
  self.assertEqual((self.root/'existing.pdf').read_bytes(),b'keep')
 def test_scopes_and_permissions(self):
  with self.assertRaises(ValueError):validate_action({'tool':'images_pdf','params':{'paths':'["../secret.png"]','destination':'no.pdf'}},self.scope)
  with self.assertRaises(ValueError):validate_action({'tool':'web_search','params':{'query':'test'}},self.scope)
  for tool in ['images_pdf','office_create','calendar_draft','pdf_transform']:
   self.assertFalse(automatic({'tool':tool,'params':{}},self.scope))
 def test_missing_time(self):
  with self.assertRaises(ValueError):self.run_tool('calendar_draft',{'destination':'a.ics','title':'A','start':'tomorrow','minutes':10})
 def test_bounded_folder_copy_search(self):
  folder=self.root/'project';folder.mkdir();(folder/'a.txt').write_text('hello');r=files_tool('files_copy',{'path':'project','destination':'backup'},self.scope);self.assertTrue(r['verified']);self.assertEqual((self.root/'backup/a.txt').read_text(),'hello')
  self.assertTrue(any(x['type']=='folder' for x in files_tool('files_search',{'path':'.','query':'project'},self.scope)['entries']))
 def test_wav(self):
  with wave.open(str(self.root/'voice.wav'),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(8000);w.writeframes(b'\0\0'*8000)
  self.assertEqual(self.run_tool('media_info',{'path':'voice.wav'})['seconds'],1)
 def test_no_macro_export(self):
  with self.assertRaises(ValueError):self.run_tool('office_pdf',{'path':'صورة.png','destination':'fake.pdf'})
class Dialogue(unittest.TestCase):
 def test_scope_does_not_transfer_permissions(self):
  old={'agent':'windows','status':'COMPLETED','objective':'find files','result':'found note.txt','windows':{'scope':{'folder':'old','apps':['notepad']},'window':{'app':'notepad'},'planApproved':True,'pending':{'nonce':'secret'},'dialogue':{'turns':[]}},'tools':[]}
  new={'windows':{'scope':{'folder':'new','apps':[]}}};e=type('Engine',(),{'get':lambda self,p:old})();link(e,new,'parent');self.assertNotIn('planApproved',new['windows']);self.assertNotIn('pending',new['windows']);self.assertNotIn('window',new['windows']);self.assertEqual(len(new['windows']['dialogue']['turns']),1)
if __name__=='__main__':unittest.main()
