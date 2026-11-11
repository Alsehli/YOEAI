"""Installed chat with deterministic research/model responses; never performs a live search."""
import json,time,zipfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'docs/visual-results';OUT.mkdir(exist_ok=True);base='http://127.0.0.1:8087';results=[]
def view(price=180,url='https://example.com/b'):
 return {'schemaVersion':'1.1','type':'dataView','id':'prices','revision':0,'title':'Fixture Bahrain prices','provenance':'retrieved','dataset':{'id':'data','columns':[{'key':'name','label':'GPU','type':'text'},{'key':'price','label':'Price','type':'number','unit':'BHD','format':'currency'}],'rows':[{'id':'a','values':{'name':'GPU A','price':300.125},'sources':['s1']},{'id':'b','values':{'name':'GPU B','price':price},'sources':['s2']}]},'charts':[{'chartType':'bar','x':'name','series':[{'field':'price'}]}],'sources':[{'id':'s1','url':'https://example.com/a','title':'Fixture shop A'},{'id':'s2','url':url,'title':'Fixture shop B'}]}
with sync_playwright() as p:
 browser=p.chromium.launch(channel='chrome',headless=True)
 def run(spec):
  context=browser.new_context(accept_downloads=True);page=context.new_page();page.set_default_timeout(5000)
  sources=[{'url':'https://example.com/a','title':'Fixture shop A'},{'url':'https://example.com/b','title':'Fixture shop B'}];pages=[{'url':sources[0]['url'],'text':'GPU A price 300.125 BHD.'},{'url':sources[1]['url'],'text':'GPU B price 180 BHD.'}]
  evidence={'sources':sources,'evidence':[{'tool':'web.research','result':{'pages':pages,'sources':sources}}],'approvals':[],'notices':[]}
  page.route('**/assistant/prepare',lambda r:r.fulfill(json=evidence))
  page.route('**/assistant/fit',lambda r:r.fulfill(json={'messages':r.request.post_data_json['messages']}))
  page.route('**/assistant/progress/*',lambda r:r.fulfill(json={'message':'Fixture research'}))
  sse='data: '+json.dumps({'choices':[{'delta':{'content':json.dumps(spec)}}]})+'\n\ndata: [DONE]\n\n'
  page.route('**/v1/chat/completions',lambda r:r.fulfill(status=200,content_type='text/event-stream',body=sse))
  page.goto(base);page.locator('#prompt').fill('Find current GPU prices in Bahrain and make a comparison table and chart.');page.locator('#send').click();page.wait_for_timeout(300)
  deadline=time.monotonic()+10
  while not page.locator('#stop-response').is_disabled() and time.monotonic()<deadline:page.wait_for_timeout(50)
  assert page.locator('#stop-response').is_disabled()
  answer=page.evaluate("JSON.parse(localStorage.getItem('deepseek-chat')).at(-1)");return context,page,answer
 c,page,a=run(view());assert a['dataView']['dataset']['rows'][0]['values']['price']==300.125;assert a['dataView']['dataset']['rows'][1]['values']['price']==180;results.append({'name':'research evidence produces exact prices','status':'passed'})
 assert page.locator('.vie-table').count()==1 and page.locator('.vie-component').count()==1;results.append({'name':'one shared research table/chart','status':'passed'})
 assert page.locator('.vie-cell-source').count()==2;assert page.locator('.vie-cell-source').first.get_attribute('href')=='https://example.com/a';results.append({'name':'row citations preserved','status':'passed'})
 assert '300.125' in page.locator('.vie-table').inner_text();results.append({'name':'BHD precision retained in chat','status':'passed'})
 with page.expect_download() as d:page.locator('.vie-table').get_by_role('button',name='XLSX',exact=True).click()
 f=OUT/'research-fixture.xlsx';d.value.save_as(f)
 with zipfile.ZipFile(f) as z:xml=z.read('xl/worksheets/sheet1.xml').decode();assert 'https://example.com/a' in xml and 'https://example.com/b' in xml
 results.append({'name':'spreadsheet retains source URLs','status':'passed'});c.close()
 c,page,a=run(view(999));assert a['dataView']['dataset']['rows'][1]['values']['price'] is None;assert 'missing' in a['dataView']['summary'];results.append({'name':'unsupported researched price becomes missing','status':'passed'});c.close()
 c,page,a=run(view(url='https://fabricated.example/'));assert 'dataView' not in a;assert page.locator('.vie-table').count()==0;assert 'could not validate' in a['content'];results.append({'name':'fabricated citation cannot render','status':'passed'});c.close()
 spec=view();spec['dataset']['columns'][1]['unit']='USD';c,page,a=run(spec);assert all(r['values']['price'] is None for r in a['dataView']['dataset']['rows']);assert a['dataView']['charts']==[];results.append({'name':'unjustified currency relabeling blocked','status':'passed'});c.close()
 browser.close()
(OUT/'research-fixtures.json').write_text(json.dumps(results,indent=2));print(json.dumps({'executed':len(results),'passed':len(results),'liveSearches':0,'realInferenceCalls':0}))
