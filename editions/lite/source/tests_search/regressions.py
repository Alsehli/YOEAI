"""Security, fallback, boundedness and integration regression checks."""
import unittest,json,threading,time,tempfile,socket,sys,subprocess,types,statistics
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from intelligence.automatic_web import Research,Cancelled,public_query,deduplicate
from intelligence import public_reader
from intelligence.registry import Registry,Tool,Context,obj,PermissionDenied
from intelligence.orchestrator import Assistant
from intelligence.search_backend import Backend,NoRedirect
from intelligence.search_server import private_app

def plan(system,user,limit,*ctx):
 if 'Decide whether' in system:return '{"search":true,"queries":["public current fact"],"language":"en"}'
 return '{"needsMore":false,"claimChecks":[{"claim":"unsupported","supportingUrls":["https://example.org/a","https://invented.example/a"]}]}'
def provider(*args):return [{'url':'https://example.org/a','title':'Current fact','content':'snippet'}]
def reader(url,cancel):return {'url':url,'text':'public evidence','untrusted':True}
class Regressions(unittest.TestCase):
 def test_01_invalid_json_tool_plan_fallback(self):
  r=Registry(lambda *a:None);calls=[];r.add(Tool('web.research','search',obj({}),{'type':'object'},lambda a,c:calls.append(1) or {'sources':[]},network=True))
  value=Assistant(r,lambda *a:'not JSON').prepare(Context('session00','request00','Find the latest Python release.'))
  self.assertEqual(calls,[1]);self.assertTrue(value['notices'])
 def test_02_invalid_schema_fallback(self):
  r=Registry(lambda *a:None);r.add(Tool('web.research','search',obj({}),{'type':'object'},lambda a,c:{'sources':[]}))
  value=Assistant(r,lambda *a:'{"calls":"bad"}').prepare(Context('session00','request00','Find current prices.'));self.assertEqual(value['toolCalls'],1)
 def test_03_invalid_planner_direct_safe(self):
  r=Registry(lambda *a:None);self.assertTrue(Assistant(r,lambda *a:'bad').prepare(Context('session00','request00','Explain prefill.'))['direct'])
 def test_04_arabic_fallback(self):
  value=Research(lambda *a:'invalid',provider,reader).run('ابحث عن أحدث إصدار بايثون');self.assertTrue(value['searched'])
 def test_05_create_image_not_search(self):
  self.assertFalse(Research(lambda *a:'invalid',provider,reader).run('Create an image of a car.')['searched'])
 def test_06_claim_must_have_read_page(self):
  v=Research(plan,provider,lambda *a:(_ for _ in ()).throw(ValueError('403'))).run('Find current fact.');self.assertEqual(v['claimChecks'],[]);self.assertIn('could not',v['limitations'])
 def test_07_fabricated_claim_source_removed(self):
  v=Research(plan,provider,reader).run('Find current fact.');self.assertEqual(v['claimChecks'][0]['supportingUrls'],['https://example.org/a'])
 def test_08_private_tool_blocks_public_search(self):
  r=Registry(lambda *a:None);r.add(Tool('web.research','search',obj({}),{'type':'object'},lambda *a:{},network=True));ctx=Context('session00','request00','public',private_seen=True)
  with self.assertRaises(PermissionDenied):r.execute('web.research',{},ctx)
 def test_09_email_query_rejected(self):
  with self.assertRaises(ValueError):public_query('find person private@example.org')
 def test_10_credential_query_rejected(self):
  with self.assertRaises(ValueError):public_query('api_key=secretvalue')
 def test_11_private_path_query_rejected(self):
  with self.assertRaises(ValueError):public_query('read C:\\Users\\private.txt')
 def test_12_local_urls_rejected(self):
  self.assertEqual(deduplicate([{'url':u} for u in ['https://127.0.0.1/','https://localhost/','https://10.0.0.1/','file:///C:/a','http://example.org/','https://example.org:9000/']]),[])
 def test_13_dns_rebinding_mixed_addresses(self):
  addresses=[(2,1,6,'',('8.8.8.8',443)),(2,1,6,'',('127.0.0.1',443))]
  with patch.object(socket,'getaddrinfo',return_value=addresses):
   with self.assertRaises(ValueError):public_reader.destination('https://example.org/a')
 def test_14_ipv6_loopback_rejected(self):
  with patch.object(socket,'getaddrinfo',return_value=[(10,1,6,'',('::1',443,0,0))]):
   with self.assertRaises(ValueError):public_reader.destination('https://[::1]/')
 def test_15_auth_token_required(self):self.auth(token='wrong',expected='403')
 def test_16_origin_blocked(self):self.auth(origin='https://evil.example',expected='403')
 def test_17_host_blocked(self):self.auth(host='evil.example',expected='403')
 def test_18_post_blocked(self):self.auth(method='POST',expected='403')
 def test_19_health_auth_success(self):self.auth(expected='200')
 def auth(self,token='secret',origin='',host='127.0.0.1:12345',method='GET',expected='200'):
  status=[];app=private_app(lambda e,s:[],12345,'secret');data=app({'HTTP_HOST':host,'HTTP_X_YOEAI_SEARCH_TOKEN':token,'HTTP_ORIGIN':origin,'REQUEST_METHOD':method,'PATH_INFO':'/health'},lambda s,h:status.append(s));self.assertTrue(status[0].startswith(expected))
 def test_20_no_private_service_redirects(self):
  with self.assertRaises(ValueError):NoRedirect().redirect_request(None,None,None,None,None,None)
 def test_21_cancellation_ignores_slow_worker(self):
  cancel=threading.Event();entered=threading.Event()
  def slow(url,event):entered.set();time.sleep(.35);return reader(url,event)
  threading.Thread(target=lambda:(entered.wait(1),cancel.set()),daemon=True).start();start=time.perf_counter()
  with self.assertRaises(Cancelled):Research(plan,provider,slow).run('current fact',cancel=cancel)
  self.assertLess(time.perf_counter()-start,.2)
 def test_22_cooperative_total_deadline(self):
  start=time.perf_counter()
  with self.assertRaises(TimeoutError):Research(plan,lambda *a:(time.sleep(.3) or []),reader,budget_seconds=.05).run('current fact')
  self.assertLess(time.perf_counter()-start,.2)
 def test_23_duplicate_search_queries(self):
  calls=[]
  def model(s,u,n):return '{"search":true,"queries":["same query","same query"],"language":"en"}' if 'Decide' in s else '{"needsMore":false}'
  Research(model,lambda q,*a:calls.append(q) or provider(),reader).run('find fact');self.assertEqual(calls,['same query'])
 def test_24_infinite_missing_fact_loop_bounded(self):
  calls=[]
  def model(s,u,n):return plan(s,u,n) if 'Decide' in s else '{"needsMore":true,"query":"new evidence"}'
  Research(model,lambda q,*a:calls.append(q) or provider(),reader).run('find fact');self.assertEqual(len(calls),2)
 def test_25_pages_size_bounded(self):
  v=Research(plan,provider,lambda url,e:{'url':url,'text':'x'*100000}).run('find fact');self.assertEqual(len(v['pages'][0]['text']),6000);self.assertTrue(v['pages'][0]['untrusted'])
 def test_26_startup_no_process_or_network(self):
  with tempfile.TemporaryDirectory(dir='tests_search') as home,patch('subprocess.Popen') as spawn,patch('socket.create_connection') as connect:
   b=Backend(Path('../..'),home);b.describe();b.close();spawn.assert_not_called();connect.assert_not_called()
 def test_27_missing_components_clear_error(self):
  with tempfile.TemporaryDirectory(dir='tests_search') as home:
   b=Backend(home,home)
   with self.assertRaisesRegex(ValueError,'missing'):b.search('public question','en',threading.Event())
   b.close()
 def test_28_backend_disabled_no_network(self):
  with tempfile.TemporaryDirectory(dir='tests_search') as home:
   b=Backend(home,home);b.settings['enabled']=False
   with self.assertRaisesRegex(ValueError,'unavailable'):b.search('public question','en',threading.Event())
 def test_29_managed_http_rejected(self):
  with tempfile.TemporaryDirectory(dir='tests_search') as home:
   b=Backend(home,home);b.settings.update(backend='managed-https',managedHttpsEndpoint='http://example.org/search')
   with self.assertRaisesRegex(ValueError,'HTTPS'):b.search('public question','en',threading.Event())
 def test_30_unsafe_redirect_page_not_cited(self):
  v=Research(plan,provider,lambda url,cancel:{'url':'https://127.0.0.1/','text':'private'}).run('current fact');self.assertEqual(v['pages'],[])
 def test_31_script_and_styles_removed(self):
  p=public_reader.Text();p.feed('<article>Visible<script>bad()</script><style>secret</style>text</article>');self.assertEqual(' '.join(p.body),'Visible text')
 def test_32_json_object_strict(self):
  from intelligence.automatic_web import object_json
  with self.assertRaises(ValueError):object_json('[]')
 def test_33_public_context_and_cache(self):
  from intelligence.research import Web
  from intelligence.store import Store
  with tempfile.TemporaryDirectory(dir='tests_search') as home:
   store=Store(home);w=Web(Path('../..'),store,lambda s,u,n,c:plan(s,u,n));w.provider.search=provider;w.provider.read=reader
   ctx=Context('session00','request00','Find current fact');v=w.research({},ctx);store.session('session00',public_context='[]');v=w.research({},ctx);self.assertIn('cacheAgeSeconds',v)
   public=json.loads(store.session('session00')['public_context']);self.assertFalse(any('private' in x.get('content','') for x in public));w.provider.close()
 def test_34_service_startup_tools_registered(self):
  from intelligence.service import Service
  with tempfile.TemporaryDirectory(dir='tests_search') as home,patch('subprocess.Popen') as spawn:
   s=Service(home,Path('../..'),lambda *a:'{}');self.assertIn('web.research',s.registry.tools);spawn.assert_not_called();s.web.provider.close()
 def test_35_selected_text_model_not_reloaded_per_tool(self):
  # The production model callback reuses manager state; this is a source contract check, not GPU benchmarking.
  source=Path('lite_native.py').read_text(encoding='utf8');self.assertIn("INSTANCE.state.get('model')==str(model)",source);self.assertIn("if INSTANCE.worker:list(INSTANCE.request('unload'))",source)

 def test_36_packaged_snapshot_does_not_require_git(self):
  from intelligence.search_server import register_bundled_version
  name='searx.version_frozen';previous=sys.modules.pop(name,None)
  try:
   with tempfile.TemporaryDirectory(dir='tests_search') as home,patch('subprocess.run') as run:
    register_bundled_version(home);self.assertEqual(sys.modules[name].VERSION_STRING,'bundled-snapshot-unversioned');run.assert_not_called()
  finally:
   sys.modules.pop(name,None)
   if previous is not None:sys.modules[name]=previous

class Capture(unittest.TextTestResult):
 def __init__(self,*args,**kwargs):super().__init__(*args,**kwargs);self.rows=[];self.started={}
 def startTest(self,test):self.started[str(test)]=time.perf_counter();super().startTest(test)
 def addSuccess(self,test):super().addSuccess(test);self.rows.append({'id':test._testMethodName,'status':'passed','seconds':time.perf_counter()-self.started[str(test)]})
 def addFailure(self,test,error):super().addFailure(test,error);self.rows.append({'id':test._testMethodName,'status':'failed','error':self._exc_info_to_string(error,test)})
 def addError(self,test,error):super().addError(test,error);self.rows.append({'id':test._testMethodName,'status':'failed','error':self._exc_info_to_string(error,test)})
if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=1,resultclass=Capture).run(unittest.defaultTestLoader.loadTestsFromTestCase(Regressions));out=Path('docs/search-results/regressions');out.mkdir(parents=True,exist_ok=True);(out/'results.json').write_text(json.dumps(result.rows,indent=2),encoding='utf8');sys.exit(not result.wasSuccessful())
