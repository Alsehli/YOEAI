import sys,unittest,tempfile,threading,time,json,io,types,copy
from pathlib import Path
from unittest.mock import patch
root=Path(__file__).resolve().parents[1]/'source';sys.path.insert(0,str(root));import model_settings as m
class Tests(unittest.TestCase):
 def wait(self,s):
  end=time.monotonic()+3
  while s.state['busy'] and time.monotonic()<end:time.sleep(.01)
  self.assertFalse(s.state['busy'])
 def test_requires_explicit_confirmation(self):
  with tempfile.TemporaryDirectory() as d:
   s=m.Service(d,lambda:{},lambda c:None,threading.Lock(),lambda:None)
   with self.assertRaisesRegex(ValueError,'Confirm'):s.start({'model':'none'})
 def test_busy_gate_blocks_switch(self):
  with tempfile.TemporaryDirectory() as d,patch.object(m,'selected_model',return_value={'model':'new','projector':''}):
   gate=threading.Lock();gate.acquire();s=m.Service(d,lambda:{},lambda c:self.fail('loaded while busy'),gate,lambda:None)
   with self.assertRaisesRegex(ValueError,'active'):s.start({'confirmed':True,'model':'new'})
 def test_success_remembers_previous_and_releases_gate(self):
  with tempfile.TemporaryDirectory() as d,patch.object(m,'selected_model',return_value={'model':'new','projector':''}):
   config={'model':'old','projector':'oldvision'};gate=threading.Lock();s=m.Service(d,lambda:dict(config),lambda c:config.update(c),gate,lambda:None);s.start({'confirmed':True,'model':'new'});self.wait(s);self.assertEqual(config['model'],'new');self.assertFalse(gate.locked());self.assertEqual([x['model'] for x in json.loads(Path(d,'model-library.json').read_text())],['new','old'])
 def test_failure_reports_recovery_and_releases_gate(self):
  with tempfile.TemporaryDirectory() as d,patch.object(m,'selected_model',return_value={'model':'new','projector':''}):
   def fail(c):e=m.SwitchError('unsupported');e.rollback='Previous model restored';raise e
   gate=threading.Lock();s=m.Service(d,lambda:{'model':'old'},fail,gate,lambda:None);s.start({'confirmed':True,'model':'new'});self.wait(s);self.assertEqual(s.state['phase'],'error');self.assertEqual(s.state['rollback'],'Previous model restored');self.assertFalse(gate.locked())
 def test_preflight_failure_releases_gate(self):
  with tempfile.TemporaryDirectory() as d,patch.object(m,'selected_model',return_value={}):
   def check():raise ValueError('active agent')
   gate=threading.Lock();s=m.Service(d,lambda:{},lambda c:None,gate,check)
   with self.assertRaisesRegex(ValueError,'agent'):s.start({'confirmed':True,'model':'new'})
   self.assertFalse(gate.locked())
 def test_cross_origin_denied_before_picker_or_model(self):
  class Handler:
   path='/local-models/pick';headers={'Host':'127.0.0.1:8087','Origin':'https://evil.example'}
   def allowed(self):return True
   def reply(self,status,value):self.status=status
  h=Handler()
  with patch.object(m,'choose_file',side_effect=AssertionError('Picker invoked')):self.assertTrue(m.route(h,True,object()))
  self.assertEqual(h.status,403)
 def test_oversized_request_rejected(self):
  class Handler:
   path='/local-models/apply';headers={'Host':'127.0.0.1:8087','Origin':'http://127.0.0.1:8087','Content-Length':'999999'};rfile=io.BytesIO()
   def allowed(self):return True
   def reply(self,status,value):self.status=status
  h=Handler();m.route(h,True,object());self.assertEqual(h.status,400)
 def test_lite_failed_load_restores_previous_profile(self):
  with tempfile.TemporaryDirectory() as d:
   home=Path(d);path=home/'profile.json';original={'model':'old','projector':'','context':16384,'apiPort':8086,'uiPort':8087};path.write_text(json.dumps(original));events=[]
   def load(*a):
    value=json.loads(path.read_text());events.append(value['model'])
    if value['model']=='new':raise ValueError('unsupported new model')
   fake=types.SimpleNamespace(healthy=lambda:True,stop=lambda:None,start=load,INSTANCE=types.SimpleNamespace(state={'busy':False}))
   agents=types.SimpleNamespace(GATE=threading.Lock(),INSTANCE=None)
   with patch.dict(sys.modules,{'lite_native':fake,'mini_agents':agents}),patch.object(m,'INSTANCE',None):
    service=m.configure_lite(home,home,lambda:json.loads(path.read_text()))
    with self.assertRaises(m.SwitchError) as caught:service.apply_model({'model':'new','projector':''})
    self.assertEqual(json.loads(path.read_text()),original);self.assertEqual(events,['new','old']);self.assertIn('reloaded',caught.exception.rollback)
 def test_normal_preserves_fast_and_advanced_catalog(self):
  with tempfile.TemporaryDirectory() as d:
   home=Path(d);config={'model':'fast-model','projector':'fast-vision','context':16384,'modelMode':'fast'};cfg=home/'config.json';cfg.write_text(json.dumps(config));cat={'selected':'fast','fast':dict(config),'advanced':{'model':'advanced-model','context':8192}};catalog_path=home/'model-modes.json';catalog_path.write_text(json.dumps(cat));native=types.SimpleNamespace(state={'loaded':True},close=lambda:None)
   def load(mode,catalog):m.atomic(cfg,dict(catalog[mode],modelMode=mode))
   modes=types.SimpleNamespace(NATIVE=native,STATE={'busy':False},CATALOG=catalog_path,assert_idle=lambda:None,catalog=lambda:json.loads(catalog_path.read_text()),stop_current=lambda:None,load_native=load,set_state=lambda **k:None,atomic=m.atomic)
   conf=types.SimpleNamespace(HOME=home,CONFIG_FILE=cfg,read_config=lambda:json.loads(cfg.read_text()));agents=types.SimpleNamespace(GATE=threading.Lock(),INSTANCE=None)
   with patch.dict(sys.modules,{'model_modes':modes,'configuration':conf,'mini_agents':agents}),patch.object(m,'INSTANCE',None):
    service=m.normal_service();service.apply_model({'model':'custom-model','projector':'','customModel':True})
   saved=json.loads(catalog_path.read_text());self.assertEqual(saved['fast'],cat['fast']);self.assertEqual(saved['advanced'],cat['advanced']);self.assertEqual(saved['selected'],'custom');self.assertEqual(json.loads(cfg.read_text())['model'],'custom-model')
 def test_normal_failed_load_restores_config_and_catalog(self):
  with tempfile.TemporaryDirectory() as d:
   home=Path(d);old={'model':'old-model','projector':'','context':16384,'modelMode':'fast'};cfg=home/'config.json';cfg.write_text(json.dumps(old));catalog={'selected':'fast','fast':dict(old),'advanced':{'model':'advanced-model'}};cat=home/'model-modes.json';cat.write_text(json.dumps(catalog));calls=[]
   def load(mode,value):
    calls.append(mode)
    if mode=='custom':raise ValueError('bad tensors')
    m.atomic(cfg,dict(value[mode],modelMode=mode))
   modes=types.SimpleNamespace(NATIVE=types.SimpleNamespace(state={'loaded':True},close=lambda:None),STATE={'busy':False},CATALOG=cat,assert_idle=lambda:None,catalog=lambda:json.loads(cat.read_text()),stop_current=lambda:None,load_native=load,set_state=lambda **k:None,atomic=m.atomic)
   conf=types.SimpleNamespace(HOME=home,CONFIG_FILE=cfg,read_config=lambda:json.loads(cfg.read_text()));agents=types.SimpleNamespace(GATE=threading.Lock(),INSTANCE=None)
   with patch.dict(sys.modules,{'model_modes':modes,'configuration':conf,'mini_agents':agents}),patch.object(m,'INSTANCE',None):
    service=m.normal_service()
    with self.assertRaises(m.SwitchError) as error:service.apply_model({'model':'broken','projector':''})
   self.assertEqual(json.loads(cfg.read_text()),old);self.assertEqual(json.loads(cat.read_text()),catalog);self.assertEqual(calls,['custom','fast']);self.assertIn('reloaded',error.exception.rollback)
if __name__=='__main__':unittest.main(verbosity=2)
