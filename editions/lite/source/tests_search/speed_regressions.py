import sys,json,time,threading,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from intelligence.orchestrator import planning_evidence,Assistant
from intelligence.automatic_web import Research
from intelligence.research import Web
from intelligence.store import Store
from intelligence.registry import Context,Cancelled,Registry,Tool,obj

def model(system,user,limit,*ctx):
 if 'Decide whether' in system:return '{"search":true,"queries":["public latest fact"],"language":"en"}'
 return '{"needsMore":false,"claimChecks":[{"claim":"A fixture fact","supportingSourceIds":["S1"]}]}'
def provider(*args):return [{'url':'https://example.org/a','title':'Fact','content':'snippet'}]
def reader(url,event):return {'url':url,'text':'Fact is documented.','untrusted':True}
class Cases(unittest.TestCase):
 def test_01_page_bodies_not_replanned(self):
  v=planning_evidence([{'tool':'web.research','result':{'pages':[{'text':'UNIQUE_LONG_PAGE'*10000}],'sources':[]}}]);self.assertNotIn('UNIQUE_LONG_PAGE',json.dumps(v))
 def test_02_sources_preserved(self):
  source=[{'url':'https://example.org/a','title':'A'}];self.assertEqual(planning_evidence([{'tool':'web.research','result':{'sources':source}}])[0]['result']['sources'],source)
 def test_03_limitations_preserved(self):
  self.assertEqual(planning_evidence([{'tool':'web.research','result':{'limitations':'Unverified'}}])[0]['result']['limitations'],'Unverified')
 def test_04_private_evidence_preserved(self):
  original={'tool':'documents.search','result':{'passages':[{'text':'authorized context'}]}};self.assertEqual(planning_evidence([original]),[original])
 def test_05_original_read_text_unchanged(self):
  original={'tool':'web.research','result':{'pages':[{'text':'Original read text'}]}};planning_evidence([original]);self.assertEqual(original['result']['pages'][0]['text'],'Original read text')
 def test_06_failed_status_preserved(self):
  self.assertTrue(planning_evidence([{'tool':'web.research','result':{'failed':True,'error':'offline'}}])[0]['result']['failed'])
 def test_07_assessment_ids_map_to_real_pages(self):
  v=Research(model,provider,reader).run('Find current fact');self.assertEqual(v['claimChecks'][0]['supportingUrls'],['https://example.org/a'])
 def test_08_invented_source_ids_removed(self):
  def bad(s,u,n):return model(s,u,n) if 'Decide' in s else '{"claimChecks":[{"claim":"fake","supportingSourceIds":["S99"]}]}'
  self.assertEqual(Research(bad,provider,reader).run('Find current fact')['claimChecks'][0]['supportingUrls'],[])
 def test_09_source_ids_wrong_type_safe(self):
  def bad(s,u,n):return model(s,u,n) if 'Decide' in s else '{"claimChecks":[{"claim":"fake","supportingSourceIds":[{},null,4]}]}'
  self.assertEqual(Research(bad,provider,reader).run('Find current fact')['claimChecks'][0]['supportingUrls'],[])
 def test_10_legacy_actual_url_support_still_valid(self):
  def old(s,u,n):return model(s,u,n) if 'Decide' in s else '{"claimChecks":[{"claim":"fact","supportingUrls":["https://example.org/a"]}]}'
  self.assertEqual(Research(old,provider,reader).run('Find current fact')['claimChecks'][0]['supportingUrls'],['https://example.org/a'])
 def test_11_assessment_small_token_budget(self):
  limits=[]
  def measured(s,u,n):limits.append(n);return model(s,u,n)
  Research(measured,provider,reader).run('Find current fact');self.assertEqual(limits,[220,240])
 def test_12_snippets_not_repeated_in_assessment(self):
  inputs=[]
  def measured(s,u,n):inputs.append(u);return model(s,u,n)
  Research(measured,lambda *a:[{'url':'https://example.org/a','content':'UNIQUE_SNIPPET'}],reader).run('Find current fact');self.assertNotIn('UNIQUE_SNIPPET',inputs[-1])
 def setup_web(self,home):
  store=Store(home);w=Web(Path('../..'),store,model);w.provider.search=provider;w.provider.read=reader;return w
 def test_13_same_question_same_session_cached(self):
  with tempfile.TemporaryDirectory(dir='tests_search') as home:
   w=self.setup_web(home);ctx=Context('speed-session','speed-request','Find current fact');w.research({},ctx);v=w.research({},ctx);self.assertIn('cacheAgeSeconds',v);w.provider.close()
 def test_14_cached_question_no_new_search(self):
  with tempfile.TemporaryDirectory(dir='tests_search') as home:
   w=self.setup_web(home);calls=[];w.provider.search=lambda *a:calls.append(1) or provider();ctx=Context('speed-session','speed-request','Find current fact');w.research({},ctx);w.research({},ctx);self.assertEqual(len(calls),1);w.provider.close()
 def test_15_changed_question_searches(self):
  with tempfile.TemporaryDirectory(dir='tests_search') as home:
   w=self.setup_web(home);calls=[];w.provider.search=lambda *a:calls.append(1) or provider();w.research({},Context('speed-session','speed-request','Find current fact'));w.research({},Context('speed-session','speed-request','Find another fact'));self.assertEqual(len(calls),2);w.provider.close()
 def test_16_empty_result_not_cached(self):
  with tempfile.TemporaryDirectory(dir='tests_search') as home:
   w=self.setup_web(home);calls=[];w.provider.search=lambda *a:calls.append(1) or [];ctx=Context('speed-session','speed-request','Find current fact');w.research({},ctx);w.research({},ctx);self.assertEqual(len(calls),2);w.provider.close()
 def test_17_offline_recovery_not_cached(self):
  with tempfile.TemporaryDirectory(dir='tests_search') as home:
   w=self.setup_web(home);ctx=Context('speed-session','speed-request','Find current fact')
   def offline(*a):raise ConnectionError('offline')
   w.provider.search=offline;v=w.research({},ctx);self.assertFalse(v['pages']);w.provider.search=provider;v=w.research({},ctx);self.assertTrue(v['pages']);self.assertNotIn('cacheAgeSeconds',v);w.provider.close()
 def test_18_expired_cache_searches_again(self):
  with tempfile.TemporaryDirectory(dir='tests_search') as home:
   w=self.setup_web(home);calls=[];w.provider.search=lambda *a:calls.append(1) or provider();ctx=Context('speed-session','speed-request','Find current fact');w.research({},ctx)
   for k,(stamp,value) in list(w.cache.items()):w.cache[k]=(stamp-100,value)
   w.research({},ctx);self.assertEqual(len(calls),2);w.provider.close()
 def test_19_failed_reader_retried(self):
  with tempfile.TemporaryDirectory(dir='tests_search') as home:
   w=self.setup_web(home);calls=[]
   def failed(*a):calls.append(1);raise ValueError('403')
   w.provider.read=failed;ctx=Context('speed-session','speed-request','Find current fact');w.research({},ctx);w.research({},ctx);self.assertEqual(len(calls),2);w.provider.close()
 def test_20_cancellation_not_cached(self):
  with tempfile.TemporaryDirectory(dir='tests_search') as home:
   w=self.setup_web(home);ctx=Context('speed-session','speed-request','Find current fact');ctx.cancel.set()
   with self.assertRaises(Cancelled):w.research({},ctx)
   self.assertFalse(w.cache);w.provider.close()
 def test_21_cache_bounded(self):
  with tempfile.TemporaryDirectory(dir='tests_search') as home:
   w=self.setup_web(home)
   for n in range(25):w.research({},Context('speed-session','speed-request','Find current fact '+str(n)))
   self.assertLessEqual(len(w.cache),34);w.provider.close()
 def test_22_claims_and_queries_preserved_for_next_tool(self):
  result={'claimChecks':[{'claim':'fact'}],'queries':['public query'],'coverage':{'pagesRead':3}}
  self.assertEqual(planning_evidence([{'tool':'web.research','result':result}])[0]['result'],result)
 def test_23_official_sources_override_local_research_decision(self):
  def selected(s,u,n):return '{"search":false,"queries":[]}' if 'Decide' in s else model(s,u,n)
  self.assertTrue(Research(selected,provider,reader).run('Is a Windows installer available? Use official sources.')['searched'])
 def test_24_official_sources_override_empty_tool_plan(self):
  registry=Registry(lambda *a:None);registry.add(Tool('web.research','research',obj({}),{'type':'object'},lambda *a:{'sources':[]}))
  result=Assistant(registry,lambda *a:'{"calls":[],"done":true}').prepare(Context('speed-session','speed-request','Is an installer available? Use official sources.'));self.assertEqual(result['toolCalls'],1)
 def test_25_provided_official_summary_does_not_force_search(self):
  from intelligence.search_intent import requires_sources
  self.assertFalse(requires_sources('Summarize the provided official sources.'))
 def test_26_thin_client_gets_public_context(self):
  from intelligence.service import Service
  with tempfile.TemporaryDirectory(dir='tests_search') as home:
   seen=[]
   def selected(s,u,n,*c):seen.append(json.loads(u));return '{"calls":[],"done":true}'
   service=Service(home,Path('../..'),selected);service.store.session('speed-session',public_context=json.dumps([{'role':'user','content':'Public queries: Python latest release'}]));service.prepare({'session':'speed-session','requestId':'speed-request','query':'Tell me more.'},threading.Event());self.assertIn('Python',seen[0]['history'][0]['content']);service.web.provider.close()
 def test_27_explicit_history_preserved(self):
  from intelligence.service import Service
  with tempfile.TemporaryDirectory(dir='tests_search') as home:
   seen=[]
   def selected(s,u,n,*c):seen.append(json.loads(u));return '{"calls":[],"done":true}'
   service=Service(home,Path('../..'),selected);history=[{'role':'user','content':'Current client topic'}];service.prepare({'session':'speed-session','requestId':'speed-request','query':'Tell me more.','history':history},threading.Event());self.assertEqual(seen[0]['history'],history);service.web.provider.close()
if __name__=='__main__':
 from regressions import Capture
 result=unittest.TextTestRunner(verbosity=1,resultclass=Capture).run(unittest.defaultTestLoader.loadTestsFromTestCase(Cases));out=Path('docs/search-results/speed');out.mkdir(parents=True,exist_ok=True);(out/'regressions.json').write_text(json.dumps(result.rows,indent=2),encoding='utf8');sys.exit(not result.wasSuccessful())
