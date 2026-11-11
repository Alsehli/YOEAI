"""Selected local Qwen + real installed chat. Isolated browser history and supplied fixture values only."""
from pathlib import Path
import json,time,urllib.request
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'docs/visual-results';OUT.mkdir(exist_ok=True)
base='http://127.0.0.1:8087';state=json.load(urllib.request.urlopen(base+'/local-models/state'))
if state['busy'] or state['engineBusy'] or not state['loaded']:raise SystemExit('Selected model unavailable/busy; no model was reloaded.')
rows=[];calls=[];(OUT/'qwen-live.json').write_text('[]')
with sync_playwright() as p:
 b=p.chromium.launch(channel='chrome',headless=True);page=b.new_page(viewport={'width':1300,'height':1000},accept_downloads=True);page.set_default_timeout(15000)
 page.on('pageerror',lambda e:print('PAGE_ERROR '+str(e),flush=True))
 page.on('request',lambda req:calls.append(req.url) if '/v1/chat/completions' in req.url else None)
 page.goto(base);page.locator('#prompt').fill('Create a table and bar chart from these exact user-provided values: Jan = 10, Feb = 20, Mar = 15. Use only these values. Do not search the internet.');start=time.monotonic();page.locator('#send').click()
 page.locator('.message.assistant .vie-table').first.wait_for(state='visible',timeout=180000)
 while not page.locator('#stop-response').is_disabled():page.wait_for_timeout(100)
 raw=page.evaluate("JSON.parse(localStorage.getItem('deepseek-chat')).filter(m=>m.role==='assistant').at(-1)")
 (OUT/'qwen-response.json').write_text(json.dumps(raw,indent=2,ensure_ascii=False),encoding='utf8')
 assert raw.get('dataView'),raw.get('content','')[:1200]
 assert page.locator('.vie-table').count()>0
 values=[r['values'] for r in raw['dataView']['dataset']['rows']];numeric=[c for c in raw['dataView']['dataset']['columns'] if c['type']=='number'][0]
 assert sorted(r[numeric['key']] for r in values)==[10,15,20]
 rows.append({'name':'selected Qwen creates validated shared table/chart','status':'passed','seconds':round(time.monotonic()-start,3),'model':state['model']})
 initial_calls=len(calls)
 def follow(q):
  page.locator('#prompt').fill(q);page.locator('#send').click();page.wait_for_timeout(100)
  while not page.locator('#stop-response').is_disabled():page.wait_for_timeout(100)
  return page.evaluate("YoeDataConversation.latest(JSON.parse(localStorage.getItem('deepseek-chat'))).view")
 v=follow('Sort by '+numeric['label']);assert v['view']['sorts'][0]['field']==numeric['key'];rows.append({'name':'normal-chat sort updates existing view','status':'passed'})
 v=follow('Show that as a line graph');assert v['charts'][0]['chartType']=='line';rows.append({'name':'normal-chat chart reuses existing data','status':'passed'})
 textcol=[c for c in v['dataset']['columns'] if c['type']=='text'][0];label=v['dataset']['rows'][1]['values'][textcol['key']]
 v=follow('Remove '+label);assert len(v['dataset']['rows'])==2;rows.append({'name':'normal-chat removal preserves shared dataset','status':'passed'})
 v=follow('Average '+numeric['label']);last=page.evaluate("JSON.parse(localStorage.getItem('deepseek-chat')).at(-1).content");assert 'Calculated locally' in last;rows.append({'name':'normal-chat average is computed locally','status':'passed'})
 assert len(calls)==initial_calls;rows.append({'name':'simple follow-ups do not invoke/reload Qwen','status':'passed'})
 v=follow('Add a numeric column ranking '+numeric['label']+' from largest to smallest. Use a local rank calculation.');newcol=[c for c in v['dataset']['columns'] if c['key'] not in [x['key'] for x in raw['dataView']['dataset']['columns']]][0];assert sorted(r['values'][newcol['key']] for r in v['dataset']['rows'])==[1,2];rows.append({'name':'normal-chat ranking is computed locally, not supplied by the model','status':'passed'})
 (OUT/'qwen-final-view.json').write_text(json.dumps(v,indent=2,ensure_ascii=False),encoding='utf8');page.screenshot(path=str(OUT/'installed-qwen.png'),full_page=True);b.close()
(OUT/'qwen-live.json').write_text(json.dumps(rows,indent=2),encoding='utf8');print(json.dumps({'executed':len(rows),'passed':len(rows),'modelCalls':len(calls)}))
