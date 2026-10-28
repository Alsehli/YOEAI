import unittest,tempfile,json,uuid,hashlib
from pathlib import Path
from PIL import Image
from windows_policy import plan_schema,make_scope
from windows_productivity import execute
from windows_reporting import summary
class Contracts(unittest.TestCase):
 def test_schema_requires_exact_output(self):
  variants=plan_schema()['properties']['steps']['items']['anyOf']
  office=next(x for x in variants if x['properties']['tool']['enum']==['office_create'])
  self.assertIn('destination',office['properties']['params']['required'])
  image=next(x for x in variants if x['properties']['tool']['enum']==['images_pdf'])
  self.assertEqual(image['properties']['params']['properties']['size']['enum'],['a4','letter','original'])
 def test_actual_image_and_pdf_preview(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
   root=Path(tmp);Image.new('RGB',(300,200),'blue').save(root/'test.png');scope=make_scope({'folder':tmp});ctx={'home':str(root/'cache'),'task':uuid.uuid4().hex};original=(root/'test.png').read_bytes()
   execute('images_pdf',{'paths':json.dumps(['test.png']),'destination':'test.pdf','size':'a4'},scope,ctx)
   for filename in ['test.png','test.pdf']:
    result=execute('document_preview',{'path':filename,'page':1},scope,ctx);target=root/'cache'/'WindowsShots'/ctx['task']/result['screenshot']
    self.assertTrue(result['verified']);self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(),result['sha256']);self.assertGreater(result['width'],100)
   self.assertEqual((root/'test.png').read_bytes(),original)
 def test_missing_metrics_not_invented(self):
  result=summary([{'name':'system_info','status':'PASS','verification':'VERIFIED','result':{'cpuPercent':12}}]);self.assertNotIn('0.0%',result)
if __name__=='__main__':unittest.main()
