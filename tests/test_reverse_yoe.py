import unittest,tempfile,struct,uuid
from pathlib import Path
from reverse_yoe import register,attach,gguf,call,pe_headers,INPUTS
class Reverse(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).parent);self.root=Path(self.tmp.name)
 def tearDown(self):self.tmp.cleanup()
 def test_static_namespace_blocks_execution(self):
  for name in ['gdb_console','load_frida_script','capture_process_scenario','execute_rizin_command','install_adb_package']:self.assertRaises(ValueError,call,None,None,None,name,{})
 def test_explicit_selection_and_snapshot(self):
  p=self.root/'a.js';p.write_text('export const x=1');values=register([p]);t={'id':uuid.uuid4().hex};e=type('Fixture',(),{'home':self.root})();attach(e,t,[values[0]['token']]);record=t['reverseInputs'][0];self.assertEqual(Path(record['snapshot']).read_text(),'export const x=1');self.assertEqual(p.read_text(),'export const x=1')
 def test_changes_rejected(self):
  p=self.root/'a.js';p.write_text('a');v=register([p]);p.write_text('changed');self.assertRaises(ValueError,attach,type('Fixture',(),{'home':self.root})(),{'id':uuid.uuid4().hex},[v[0]['token']])
 def test_invalid_token_and_extension(self):
  p=self.root/'file.ps1';p.write_text('test');self.assertRaises(ValueError,register,[p]);self.assertRaises(ValueError,attach,type('Fixture',(),{'home':self.root})(),{'id':uuid.uuid4().hex},['unapproved'])
 def test_gguf_metadata_without_weights_copy(self):
  p=self.root/'model.gguf';name=b'general.name';value=b'Harmless';p.write_bytes(b'GGUF'+struct.pack('<IQQ',3,0,1)+struct.pack('<Q',len(name))+name+struct.pack('<I',8)+struct.pack('<Q',len(value))+value);r=gguf(p);self.assertEqual(r['metadata']['general.name'],'Harmless');v=register([p]);t={'id':uuid.uuid4().hex};attach(type('Fixture',(),{'home':self.root})(),t,[v[0]['token']]);self.assertNotIn('snapshot',t['reverseInputs'][0])
 def test_invalid_binary(self):
  p=self.root/'bad.exe';p.write_bytes(b'not a binary');self.assertRaises(ValueError,pe_headers,p)
 def test_memory_and_restart(self):
  import time
  from mini_agents import Engine
  root=self.root/'profile';e=Engine(root,infer=lambda *x:'fixture')
  try:
   e.set_memory('reverse',{'preferences':'Concise static evidence','maxTokens':512,'recallEnabled':True});self.assertEqual(e.memory('code')['preferences'],'');t=e.create({'agent':'reverse','objective':'Analyze this software'})
   for _ in range(200):
    t=e.get(t['id'])
    if t['status']=='COMPLETED':break
    time.sleep(.02)
   self.assertEqual(t['status'],'COMPLETED');self.assertIn('select',t['result'])
  finally:e.closed=True;e.worker.join(3)
  e=Engine(root,infer=lambda *x:'fixture')
  try:self.assertEqual(e.get(t['id'])['agent'],'reverse');self.assertEqual(e.memory('reverse')['preferences'],'Concise static evidence')
  finally:e.closed=True;e.worker.join(3)
 def test_native_procedures_are_exact_and_internal(self):
  from reverse_yoe import observed_procedures
  rows=[{'address':'EXTERNAL:0x1','procedure':{'external':True}},{'address':'0x140001000','procedure':{'external':False}},{'address':'not-an-address','procedure':{}},{'address':'0x140001000','procedure':{}}]
  self.assertEqual(observed_procedures({'structuredContent':{'normalized_result':rows}}),['0x140001000'])
 def test_native_missing_dependencies_fail_closed(self):
  import reverse_yoe,json
  from unittest.mock import patch
  import configuration
  config=self.root/'ReverseRuntime/native-provider.json';config.parent.mkdir();config.write_text(json.dumps({'ghidra':str(self.root/'missing-ghidra'),'jdk':str(self.root/'missing-java')}))
  with patch.object(configuration,'APP_DIR',self.root):self.assertRaisesRegex(ValueError,'unavailable',reverse_yoe.native_provider)
 def test_pseudocode_survives_inventory_budget(self):
  import json
  from reverse_yoe import report_evidence
  def raw(operation,value):return {'file':'fixture.exe','analysis':{'content':[{'type':'text','text':json.dumps({'operation':operation,'normalized_result':value})}]}}
  evidence=[raw('binary_overview',{'huge':'x'*15000}),raw('list_procedures',[{'address':hex(i),'procedure':{'external':False}} for i in range(1000)]),raw('procedure_pseudo_code','int observed_function(){return 42;}')]
  payload=report_evidence(evidence,1200);self.assertIn('return 42',payload);self.assertLessEqual(len(payload),1200);self.assertIsInstance(json.loads(payload),list)
 def test_selected_source_excerpt_is_preserved(self):
  import json
  from reverse_yoe import report_evidence
  payload=report_evidence([{'file':'fixture.js','sourceExcerpt':'export function add(a,b){return a+b;}'}]);self.assertIn('return a+b',json.loads(payload)[0]['sourceExcerpt'])
 def test_mcp_cancellation(self):
  import sys,os,threading,time
  from local_mcp import Client
  server=self.root/'mcp_fixture.py';server.write_text("import sys,json,time\nfor line in sys.stdin:\n r=json.loads(line)\n if 'id' not in r:continue\n if r['method']=='tools/call':time.sleep(30)\n else:print(json.dumps({'jsonrpc':'2.0','id':r['id'],'result':{'serverInfo':{'name':'fixture'}}}),flush=True)\n")
  stop=threading.Event()
  def check():
   if stop.is_set():raise InterruptedError('Stopped')
  c=Client(sys.executable,[server],self.root,os.environ.copy(),check);timer=threading.Timer(.3,stop.set);timer.start();started=time.monotonic()
  try:self.assertRaises(InterruptedError,c.tool,'fixture',{})
  finally:c.close();timer.cancel()
  self.assertLess(time.monotonic()-started,3);self.assertIsNotNone(c.process.poll())
if __name__=='__main__':unittest.main()
