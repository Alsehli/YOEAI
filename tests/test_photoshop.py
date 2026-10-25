import sys,unittest,tempfile
from pathlib import Path
sys.path.insert(0,r'F:\YOEAI-Autonomy\Source')
from windows_policy import validate_action,automatic,plan_schema
from photoshop_yoe import script
class PhotoshopTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).parent);self.scope={'mode':'ASSISTED','apps':['photoshop'],'folder':self.tmp.name,'reuseLowRisk':False}
 def tearDown(self):self.tmp.cleanup()
 def action(self,**p):return {'tool':'photoshop_preview','params':dict(width=1280,height=720,text='Test',color='#102040',**p)}
 def test_approval(self):
  a=validate_action(self.action(),self.scope);self.assertFalse(automatic(a,self.scope));self.assertIn('photoshop_preview',plan_schema()['properties']['steps']['items']['properties']['tool']['enum'])
 def test_scope(self):
  self.scope['apps']=[]
  with self.assertRaises(ValueError):validate_action(self.action(),self.scope)
 def test_advisor(self):
  self.scope['mode']='ADVISOR'
  with self.assertRaises(ValueError):validate_action(self.action(),self.scope)
 def test_bad_dimensions(self):
  a=self.action();a['params']['width']=100000
  with self.assertRaises(ValueError):validate_action(a,self.scope)
 def test_escape(self):
  with self.assertRaises(ValueError):validate_action(self.action(path='../x.png'),self.scope)
 def test_no_overwrite(self):
  Path(self.tmp.name,'existing.psd').write_bytes(b'test')
  with self.assertRaises(ValueError):validate_action({'tool':'photoshop_export','params':{'draft':'a'*32,'destination':'existing.psd'}},self.scope)
 def test_no_javascript_parameter(self):
  a=self.action();a['params']['script']='app.quit()'
  with self.assertRaises(ValueError):validate_action(a,self.scope)
 def test_quote_injection(self):
  value='";app.quit();//\u2028';s=script({'text':value});self.assertIn('\\";app.quit();//\\u2028',s);self.assertNotIn('eval(',s)
if __name__=='__main__':unittest.main()

