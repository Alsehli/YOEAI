import base64,io,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from game_studio import Studio,safe_folder,specification,detect,sha
from game_assets import prepare

class GameStudioTests(unittest.TestCase):
 def setUp(self):
  parent=Path('D:/YOEAI-GameStudio-Verification/Unit');parent.mkdir(parents=True,exist_ok=True);self.tmp=tempfile.TemporaryDirectory(dir=parent);self.root=Path(self.tmp.name);self.s=Studio(self.root/'Profile');self.doc=self.s.create({'parent':str(self.root),'approve':True,'spec':{'title':'لعبة Fox'}});self.p,self.d=self.s.project(self.doc['id'])
 def tearDown(self):self.tmp.cleanup()
 def test_detection_uses_installed_editor(self):
  caps=detect();self.assertTrue(caps['editors']);self.assertIn('Windows',caps['editors'][0]['targets']);self.assertIn('com.unity.2d.sprite',caps['editors'][0]['packages'])
 def test_creation_and_memory_manifest(self):
  self.assertTrue((self.p/'Assets/Editor/YoeStudioBridge.cs').is_file());self.assertEqual(self.d['spec']['title'],'لعبة Fox');self.s.integrity(self.p,self.d);other=Studio(self.root/'Profile');self.assertEqual(other.projects()[0]['id'],self.d['id'])
 def test_production_roots_blocked(self):
  for root in ['F:/YOEAI-Autonomy/Source','C:/Users/Mohamed/Documents/Codex/YOEAI','D:/YOEAI-Packages','C:/Windows','C:/']:
   with self.assertRaises(ValueError):safe_folder(root)
 def test_required_approvals(self):
  for fn,body in [(self.s.create,{'parent':str(self.root)}),(self.s.start,{'project':self.d['id'],'operation':'build'}),(self.s.revise,{'project':self.d['id'],'spec':{}})]:
   with self.assertRaises(ValueError):fn(body)
 def test_custom_cs_not_trusted_by_editing_manifest_hash(self):
  p=self.p/'Assets/YOE/Scripts/YoePlayer.cs';p.write_text('malicious change',encoding='utf8');self.d['trusted']['Assets/YOE/Scripts/YoePlayer.cs']=sha(p)
  with self.assertRaisesRegex(ValueError,'executable'):self.s.integrity(self.p,self.d)
 def test_untrusted_plugin_blocked(self):
  (self.p/'Assets/untrusted.dll').write_bytes(b'fake')
  with self.assertRaises(ValueError):self.s.integrity(self.p,self.d)
 def test_external_registry_blocked(self):
  p=self.p/'Packages/manifest.json';v=json.loads(p.read_text());v['scopedRegistries']=[{'name':'untrusted'}];p.write_text(json.dumps(v))
  with self.assertRaises(ValueError):self.s.integrity(self.p,self.d)
 def test_revisions_preserve_checkpoint(self):
  d=self.s.revise({'project':self.d['id'],'approve':True,'spec':{'title':'Winter','theme':'winter','levels':5}});self.assertTrue((self.p/d['history'][-1]['checkpoint']).is_file());self.assertEqual(d['spec']['levels'],5);self.s.integrity(self.p,d)
 def test_unsafe_paths_and_shell_actions(self):
  for rel in ['../config.json','C:/Windows/win.ini','Assets/no.exe']:
   with self.assertRaises(ValueError):self.s.file(self.d['id'],rel)
  with self.assertRaises(ValueError):self.s.start({'project':self.d['id'],'operation':'powershell','approve':True})
 def test_invalid_specs(self):
  for v in [{'levels':100},{'speed':float('nan')},{'genre':'unimplemented'},{'seed':'42'},{'title':'\n'}]:
   with self.assertRaises(ValueError):specification(v)
 def test_sprite_grid_alpha_and_frame_order(self):
  im=Image.new('RGBA',(64,32),(0,0,0,0));im.paste((255,0,0,255),(8,8,24,24));im.paste((0,255,0,255),(40,8,56,24));buf=io.BytesIO();im.save(buf,format='PNG');r=prepare(self.s,{'project':self.d['id'],'approve':True,'data':base64.b64encode(buf.getvalue()).decode(),'columns':2,'rows':1,'frames':2,'size':64,'state':'walk'});self.assertTrue(r['alphaPresent']);self.assertEqual(len(r['files']),2)
  with Image.open(self.p/r['files'][0]) as a:self.assertEqual(a.size,(64,64));self.assertEqual(a.getpixel((32,48))[:3],(255,0,0))
 def test_invalid_sprite_grid_no_write(self):
  b=io.BytesIO();Image.new('RGB',(33,32),'white').save(b,'PNG')
  with self.assertRaises(ValueError):prepare(self.s,{'project':self.d['id'],'approve':True,'data':base64.b64encode(b.getvalue()).decode(),'columns':2})
 def test_restart_does_not_repeat_jobs(self):
  from game_studio import atomic
  atomic(self.s.jobsfile,[{'id':'a','project':self.d['id'],'status':'RUNNING'}]);s=Studio(self.root/'Profile');self.assertEqual(s.jobs[0]['status'],'CANCELLED')
 def test_existing_project_inspection_is_read_only(self):
  other=self.root/'Existing';(other/'Assets').mkdir(parents=True);(other/'ProjectSettings').mkdir();(other/'ProjectSettings/ProjectVersion.txt').write_text('m_EditorVersion: 6000.6.0f1');p=self.s.register({'path':str(other),'approve':True});self.assertTrue(self.s.inspect(p['id'])['readOnly']);self.assertFalse((other/'yoe-game.json').exists())
 def test_game_agent_shared_inference_and_typed_revision(self):
  import time,game_studio
  from mini_agents import Engine
  calls=[]
  def infer(t,messages,tokens):calls.append(t['agent']);return json.dumps({'summary':'Night revision proposed.','settings':{'theme':'night'}})
  with patch.object(game_studio,'INSTANCE',self.s):
   e=Engine(self.root/'Agent',infer=infer,config=lambda:{'context':8192});t=e.create({'agent':'game','gameProject':self.d['id'],'objective':'Make the game night.'})
   try:
    end=time.time()+8
    while e.get(t['id'])['status'] in ['RUNNING','PLANNING','QUEUED'] and time.time()<end:time.sleep(.05)
    t=e.get(t['id']);self.assertEqual(t['status'],'COMPLETED');self.assertEqual(t['gameProposal']['theme'],'night');self.assertEqual(self.s.project(self.d['id'])[1]['spec']['theme'],'forest');self.assertEqual(calls,['game'])
   finally:e.closed=True;e.worker.join(5)
 def test_game_memory_preferences_separate(self):
  from mini_agents import Engine
  e=Engine(self.root/'Memory',infer=lambda *args:'ok')
  try:
   e.set_memory('game',{'preferences':'pixel art','maxTokens':1024});self.assertEqual(e.memory('game')['preferences'],'pixel art');self.assertEqual(e.memory('code')['preferences'],'')
  finally:e.closed=True;e.worker.join(5)
 def test_literal_theme_mismatch_is_corrected_only_in_proposal(self):
  import time,game_studio
  from mini_agents import Engine
  with patch.object(game_studio,'INSTANCE',self.s):
   e=Engine(self.root/'Mismatch',infer=lambda *args:json.dumps({'summary':'Night theme.','settings':{'theme':'winter'}}),config=lambda:{'context':8192})
   try:
    t=e.create({'agent':'game','gameProject':self.d['id'],'objective':'Change the theme to night.'});end=time.time()+8
    while e.get(t['id'])['status'] in ['QUEUED','PLANNING','RUNNING'] and time.time()<end:time.sleep(.05)
    t=e.get(t['id']);self.assertEqual(t['gameProposal']['theme'],'night');self.assertEqual(self.s.project(self.d['id'])[1]['spec']['theme'],'forest')
   finally:e.closed=True;e.worker.join(5)
 def test_audio_requires_license_and_valid_wave(self):
  import wave
  from game_assets import audio
  b=io.BytesIO()
  with wave.open(b,'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(22050);w.writeframes(b'\0\0'*100)
  body={'project':self.d['id'],'approve':True,'data':base64.b64encode(b.getvalue()).decode()}
  with self.assertRaises(ValueError):audio(self.s,body)
  result=audio(self.s,{**body,'licensed':True});self.assertTrue((self.p/result['imported']).is_file())
 def test_unknown_pivot_filter_rejected(self):
  with self.assertRaises(ValueError):prepare(self.s,{'project':self.d['id'],'approve':True,'ppu':-1})
 def test_project_save_identity(self):
  data=json.loads((self.p/'Assets/Resources/yoe-game.json').read_text(encoding='utf8'));self.assertEqual(data['projectId'],self.d['id'])
 def test_upgrade_checks_previous_template_and_preserves_assets(self):
  history=json.loads((Path(__import__('game_studio').ASSETS)/'template-history.json').read_text());old=Path(__file__).parent/'Fixtures/GameStudioV1';self.assertTrue(old.is_dir())
  for p in old.glob('*.cs'):
   rel=('Assets/Editor/' if p.name=='YoeStudioBridge.cs' else 'Assets/YOE/Scripts/')+p.name;(self.p/rel).write_bytes(p.read_bytes())
  (self.p/'Assets/Resources/yoe-game.json').write_text(json.dumps(self.d['spec']));art=self.p/'Assets/YOE/Art/preserve.txt';art.write_text('user art')
  with self.assertRaises(ValueError):self.s.upgrade({'project':self.d['id']})
  doc=self.s.upgrade({'project':self.d['id'],'approve':True});self.s.integrity(self.p,doc);self.assertEqual(art.read_text(),'user art');self.assertTrue((self.p/doc['history'][-1]['checkpoint']).is_file())
 def test_upgrade_does_not_overwrite_custom_code(self):
  p=self.p/'Assets/YOE/Scripts/YoePlayer.cs';p.write_text('custom user source')
  with self.assertRaises(ValueError):self.s.upgrade({'project':self.d['id'],'approve':True})
  self.assertEqual(p.read_text(),'custom user source')
 def test_large_background_removal_is_resized_first(self):
  import time
  from PIL import ImageDraw
  im=Image.new('RGB',(2048,2048),'white');ImageDraw.Draw(im).rectangle((400,400,1800,1800),fill='red');b=io.BytesIO();im.save(b,'PNG');start=time.monotonic();r=prepare(self.s,{'project':self.d['id'],'approve':True,'data':base64.b64encode(b.getvalue()).decode(),'removeBackground':True,'size':128});self.assertTrue(r['alphaPresent']);self.assertLess(time.monotonic()-start,3)
 def test_empty_frame_rejected(self):
  b=io.BytesIO();Image.new('RGB',(32,32),'white').save(b,'PNG')
  with self.assertRaisesRegex(ValueError,'empty'):prepare(self.s,{'project':self.d['id'],'approve':True,'data':base64.b64encode(b.getvalue()).decode(),'removeBackground':True})

if __name__=='__main__':unittest.main()

