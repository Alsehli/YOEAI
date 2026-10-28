import os,sys,tempfile,unittest,json,hashlib,io
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtGui import QGuiApplication
APP=QGuiApplication.instance() or QGuiApplication([])
from precision_text import *
from PIL import Image

class PrecisionTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir='F:/YOEAI-Autonomy/Precision-Text');self.home=Path(self.tmp.name);self.store=TextProjects(self.home);self.png=io.BytesIO();Image.new('RGB',(512,512),'#14304c').save(self.png,'PNG')
 def tearDown(self):self.tmp.cleanup()
 def project(self,prompt):return self.store.create(uuid.uuid4().hex,exact_recipe(prompt),self.png.getvalue())
 def test_exact_english(self):
  prompt='Create a premium YOEAI advertisement with the words The Future of Local AI.';recipe=exact_recipe(prompt);self.assertEqual(recipe['requested'],['The Future of Local AI.']);self.assertNotIn('The Future of Local AI.',recipe['visualPrompt']);doc=self.project(prompt);self.assertTrue(doc['verification']['textExact']);self.assertTrue(doc['verification']['layoutPassed'],doc['verification'])
 def test_arabic_shaping(self):
  doc=self.project('صمم إعلاناً بعبارة «مرحباً بكم في عالم الذكاء الاصطناعي»');v=doc['verification'];self.assertTrue(v['layoutPassed'],v);self.assertFalse(v['layers'][0]['missingGlyphs']);self.assertIn('Noto Sans Arabic',v['layers'][0]['fontsUsed']);self.assertGreater(v['layers'][0]['glyphCount'],0)
  from PySide6.QtGui import QFont,QRawFont
  layer=dict(doc['layers'][0],text='\u0633\u0644\u0627\u0645');layout,check,pad=layout_text(layer,400,200,1);font=QFont(layer['font']);font.setPixelSize(round(layer['size']));font.setWeight(QFont.Weight.Bold);isolated=list(QRawFont.fromFont(font).glyphIndexesForString(layer['text']));shaped=[g for run in layout.glyphRuns() for g in run.glyphIndexes()];self.assertNotEqual(isolated,shaped)
 def test_mixed_and_punctuation(self):
  text='YOEAI 2.0 — مرحباً، AI!';doc=self.project('Create a poster saying "'+text+'"');self.assertEqual(doc['verification']['currentText'],[text]);self.assertTrue(doc['verification']['layoutPassed'])
 def test_multiple_blocks(self):
  doc=self.project('Create a certificate with title "Certificate of Achievement" and subtitle "محمد — 2026"');self.assertEqual(len(doc['layers']),2);self.assertTrue(doc['verification']['layoutPassed'],doc['verification'])
 def test_edit_does_not_change_art(self):
  doc=self.project('Create a logo saying "YOEAI"');before=(self.store.folder(doc['id'])/'background.png').read_bytes();doc['layers'][0]['text']='YOEAI 2.0';changed=self.store.edit(doc['id'],{'revision':1,'layers':doc['layers']});self.assertTrue(changed['verification']['textChanged']);self.assertEqual(before,(self.store.folder(doc['id'])/'background.png').read_bytes())
 def test_export_gates_and_high_resolution(self):
  doc=self.project('Create a poster saying "Exact Words!"')
  with self.assertRaises(ValueError):self.store.export(doc['id'],{'revision':1})
  result=self.store.export(doc['id'],{'revision':1,'backgroundReviewed':True,'width':2048});self.assertEqual(result['verification']['width'],2048);self.assertTrue(result['verification']['textExact'])
 def test_clipping_blocks_export(self):
  doc=self.project('Create a poster saying "Exact Words!"');doc['layers'][0].update(x=.99,autoFit=False);doc=self.store.edit(doc['id'],{'revision':1,'layers':doc['layers']});self.assertFalse(doc['verification']['layoutPassed'])
  with self.assertRaises(ValueError):self.store.export(doc['id'],{'revision':2,'backgroundReviewed':True})
 def test_edit_approval_required(self):
  doc=self.project('Create a logo saying "YOEAI"');doc['layers'][0]['text']='Changed';self.store.edit(doc['id'],{'revision':1,'layers':doc['layers']})
  with self.assertRaises(ValueError):self.store.export(doc['id'],{'revision':2,'backgroundReviewed':True})
  self.assertTrue(self.store.export(doc['id'],{'revision':2,'backgroundReviewed':True,'textEditsApproved':True})['verification']['layoutPassed'])
 def test_art_only_and_override(self):
  self.assertIsNone(exact_recipe('Create an image of a landscape'));self.assertIsNone(exact_recipe('Poster saying "Hello"','off'));self.assertIsNotNone(exact_recipe('A landscape','on'))
 def test_invalid_paths_styles_revision(self):
  with self.assertRaises(ValueError):self.store.folder('../outside')
  doc=self.project('A poster saying "Hello"');doc['layers'][0]['font']='../../secret'
  with self.assertRaises(ValueError):self.store.edit(doc['id'],{'revision':1,'layers':doc['layers']})
 def test_long_paragraph(self):
  text='Natural writing, preserved exactly. '*45;doc=self.project('A poster saying "'+text+'"');self.assertEqual(doc['layers'][0]['text'],text);self.assertLess(doc['verification']['layers'][0]['actualSize'],doc['layers'][0]['size'])
 def test_editable_zip(self):
  doc=self.project('A social media poster saying "Be You."');v=self.store.export(doc['id'],{'revision':1,'backgroundReviewed':True,'format':'zip'});path=self.store.folder(doc['id'])/v['url'].split('/')[-1]
  with zipfile.ZipFile(path) as z:self.assertEqual(set(z.namelist()),{'background.png','text-layers.json','preview.png'})

 def test_wrapper_uses_art_only_prompt(self):
  class Base:
   def __init__(b):b.request=None;b.state={}
   def start(b,body):b.request=body;b.state={'id':'a'*32,'status':'running'};return b.state.copy()
   def status(b):return b.state.copy()
   def output(b,ident):return self.png.getvalue()
  base=Base();engine=PrecisionEngines(base,self.home/'Wrapper');engine.start({'prompt':'A premium poster saying "Exact spelling!"'});self.assertNotIn('Exact spelling!',base.request['prompt']);base.state.update(status='complete');state=engine.status();self.assertIn('precisionProject',state);self.assertEqual(engine.projects.load(state['precisionProject'])['layers'][0]['text'],'Exact spelling!')
 def test_normal_engine_unchanged(self):
  class Base:
   def start(b,body):b.request=body;return {'id':'b'*32,'status':'running'}
  base=Base();engine=PrecisionEngines(base,self.home/'Wrapper');engine.start({'prompt':'A fox in a forest'});self.assertEqual(base.request['prompt'],'A fox in a forest');engine.start({'prompt':'Poster saying "Design text"','engine':'design'});self.assertEqual(base.request['prompt'],'Poster saying "Design text"')
 def test_quoted_font_is_not_a_text_layer(self):
  r=exact_recipe('A poster saying "Hello" using font "Inter"');self.assertEqual(r['requested'],['Hello'])
 def test_opaque_cover_over_text_blocked(self):
  doc=self.project('A poster saying "Keep visible"');cover=dict(doc['layers'][0],id=uuid.uuid4().hex,kind='cover',text='',panelOpacity=100);doc['layers'].append(cover);changed=self.store.edit(doc['id'],{'revision':1,'layers':doc['layers']});self.assertFalse(changed['verification']['layoutPassed'])
 def test_stale_editor_rejected(self):
  doc=self.project('A poster saying "Hi"');self.store.edit(doc['id'],{'revision':1,'layers':doc['layers']})
  with self.assertRaises(ValueError):self.store.edit(doc['id'],{'revision':1,'layers':doc['layers']})

 def test_outline_preserves_letter_fill(self):
  doc=self.project('A poster saying "Your Private AI."');layer=doc['layers'][0];layer.update(outline=0,shadow=False,autoFit=False)
  plain,_=render(doc,self.store.folder(doc['id'])/'background.png',1024);layer['outline']=4;outlined,_=render(doc,self.store.folder(doc['id'])/'background.png',1024)
  def white(data):return sum(r>245 and g>245 and b>245 for r,g,b in Image.open(io.BytesIO(data)).convert('RGB').getdata())
  self.assertGreater(white(outlined),white(plain)*.96)
 def test_unicode_not_normalized(self):
  text='Cafe\u0301 — YOEAI';r=exact_recipe('A poster saying "'+text+'"');self.assertEqual(r['requested'][0],text)
 def test_4096_export(self):
  doc=self.project('A poster saying "YOEAI"');v=self.store.export(doc['id'],{'revision':1,'width':4096,'backgroundReviewed':True});self.assertEqual(v['verification']['width'],4096);self.assertTrue(v['verification']['textExact'])

 def test_no_text_intent_false_positives(self):
  for prompt in ['Create an image with textured fur','Paint a writer beside a window','A landscape without words']:
   self.assertIsNone(exact_recipe(prompt),prompt)
