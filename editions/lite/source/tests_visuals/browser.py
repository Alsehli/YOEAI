"""Real Chromium/ECharts/table interactions with deterministic data; no model or media inference."""
import json,time,threading,re,zipfile,xml.etree.ElementTree as ET
from pathlib import Path
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from functools import partial
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'docs/visual-results';OUT.mkdir(parents=True,exist_ok=True)
class Quiet(SimpleHTTPRequestHandler):
 def log_message(self,*a):pass
server=ThreadingHTTPServer(('127.0.0.1',0),partial(Quiet,directory=str(ROOT)));threading.Thread(target=server.serve_forever,daemon=True).start();base=f'http://127.0.0.1:{server.server_port}';results=[]
def case(name,fn):
 start=time.monotonic()
 try:fn();results.append({'name':name,'status':'passed','seconds':round(time.monotonic()-start,4)})
 except Exception as e:results.append({'name':name,'status':'failed','error':str(e)})
with sync_playwright() as p:
 browser=p.chromium.launch(channel='chrome',headless=True);context=browser.new_context(accept_downloads=True,viewport={'width':1200,'height':900},permissions=['clipboard-read','clipboard-write']);page=context.new_page();page.set_default_timeout(5000);page.goto(base+'/tests_visuals/fixture.html')
 page.evaluate('''()=>{window.fixture=n=>({schemaVersion:'1.1',type:'dataView',id:'fixture',revision:0,title:'GPU comparison · بيانات تجريبية',provenance:'example',dataset:{id:'data',columns:[{key:'name',label:'GPU',type:'text'},{key:'price',label:'Price',type:'number',unit:'BHD',format:'currency'},{key:'vram',label:'VRAM',type:'number',unit:'GB'},{key:'date',label:'Date',type:'date'}],rows:Array.from({length:n},(_,i)=>({id:'r'+i,values:{name:i===0?'بطاقة عربية':'GPU '+i,price:i+.125,vram:8+i%3*8,date:new Date(Date.UTC(2026,0,i+1)).toISOString().slice(0,10)},sources:['s1']}))},charts:[],sources:[{id:'s1',url:'https://example.com/data',title:'Deterministic fixture'}]});window.mount=(v)=>{document.getElementById('host').replaceChildren(YoeDataViews.render(v));};mount(fixture(64));}''')
 table=lambda:page.locator('.vie-table').first
 def chart_test(kind):
  page.evaluate('''kind=>{const v=fixture(kind==='pie'||kind==='donut'?10:64);v.charts=[kind==='histogram'?{chartType:kind,value:'price'}:{chartType:kind,x:kind==='scatter'?'vram':'name',series:[{field:'price'}]}];mount(v);}''',kind)
  page.evaluate('''async()=>{await document.querySelector('.vie-component').vieReady();}''');assert page.locator('.vie-chart svg').count()>0
 for kind in ['bar','horizontalBar','line','area','pie','donut','scatter','histogram']:case('real ECharts '+kind,lambda k=kind:chart_test(k))
 case('tooltip uses rich text, not model HTML',lambda:page.wait_for_function("echarts.getInstanceByDom(document.querySelector('.vie-chart')).getOption().tooltip[0].renderMode==='richText'"))
 case('series legend available',lambda:page.wait_for_function("echarts.getInstanceByDom(document.querySelector('.vie-chart')).getOption().legend.length>0"))
 case('axis labels present',lambda:page.wait_for_function("echarts.getInstanceByDom(document.querySelector('.vie-chart')).getOption().xAxis.length>0"))
 def legend():
  assert page.evaluate("(()=>{const i=echarts.getInstanceByDom(document.querySelector('.vie-chart'));i.dispatchAction({type:'legendToggleSelect',name:'Frequency'});return i.getOption().legend[0].selected.Frequency;})()") is False
  assert page.evaluate("(()=>{const i=echarts.getInstanceByDom(document.querySelector('.vie-chart'));i.dispatchAction({type:'legendToggleSelect',name:'Frequency'});return i.getOption().legend[0].selected.Frequency;})()") is True
 case('interactive legend hides and restores series',legend)
 def zoompan():
  chart_test('line');assert page.evaluate("(()=>{const i=echarts.getInstanceByDom(document.querySelector('.vie-chart'));i.dispatchAction({type:'dataZoom',start:20,end:70});return i.getOption().dataZoom[0].start;})()") == 20
  assert page.evaluate("(()=>{const i=echarts.getInstanceByDom(document.querySelector('.vie-chart'));i.dispatchAction({type:'dataZoom',start:30,end:80});return i.getOption().dataZoom[0].start;})()") == 30
  chart_test('histogram')
 case('zoom and pan retain chart data',zoompan)
 def keyboard():
  table().get_by_role('button',name='Price',exact=True).focus();page.keyboard.press('Enter');assert page.evaluate("document.querySelector('.vie-table').vieState.sorts[0].direction")=='asc'
  page.evaluate("document.querySelector('.vie-table').vieState.sorts=[];document.querySelector('.vie-table').vieRefresh()")
 case('keyboard activates table sorting',keyboard)
 case('real numeric sorting',lambda:(table().get_by_role('button',name='Price',exact=True).click(),page.wait_for_function("document.querySelector('.vie-table').vieState.sorts[0].field==='price'")))
 case('descending sorting',lambda:(table().get_by_role('button',name=re.compile('^Price')).click(),page.wait_for_function("document.querySelector('.vie-table').vieState.sorts[0].direction==='desc'")))
 case('shift adds multi-column sort',lambda:(table().get_by_role('button',name='VRAM',exact=True).click(modifiers=['Shift']),page.wait_for_function("document.querySelector('.vie-table').vieState.sorts.length===2")))
 def filtering():
  table().get_by_text('Columns & filters',exact=True).click();table().get_by_label('Filter operator Price',exact=True).select_option('gte');table().get_by_label('Filter Price',exact=True).fill('60');page.wait_for_function("document.querySelector('.vie-table').getExportData().rows.length===4")
 case('numeric filter controls',filtering)
 case('chart and table share filtered rows',lambda:page.wait_for_function("echarts.getInstanceByDom(document.querySelector('.vie-chart')).getOption().series[0].data.reduce((a,b)=>a+b,0)===4"))
 def datefilter():
  table().get_by_label('Filter operator Date',exact=True).select_option('gte');table().get_by_label('Filter Date',exact=True).fill('2026-03-04');page.wait_for_function("document.querySelector('.vie-table').getExportData().rows.length===2")
 case('date filter controls',datefilter)
 case('missing results clear chart',lambda:(table().get_by_label('Search table rows').fill('no-such-GPU'),page.wait_for_function("document.querySelector('.vie-table').getExportData().rows.length===0"),page.wait_for_function("document.querySelector('.vie-component .vie-caption').textContent==='No matching data'")))
 case('reset search restores filtered chart',lambda:(table().get_by_label('Search table rows').fill(''),page.wait_for_function("document.querySelector('.vie-table').getExportData().rows.length===2")))
 case('column width slider',lambda:(table().get_by_label('Column width Price').fill('300'),page.wait_for_function("document.querySelector('.vie-table').vieState.widths.price===300")))
 case('hide column',lambda:(table().get_by_label('VRAM',exact=True).uncheck(),page.wait_for_function("document.querySelector('.vie-table').getExportData().columns.length===4")))
 case('row source anchor safe',lambda:page.wait_for_function("document.querySelector('.vie-cell-source').target==='_blank' && document.querySelector('.vie-cell-source').rel.includes('noopener')"))
 case('cell focus keyboard accessible',lambda:page.wait_for_function("document.querySelector('.vie-table tbody td[tabindex]').tabIndex===0"))
 def export(kind):
  with page.expect_download() as event:table().get_by_role('button',name=kind,exact=True).click()
  target=OUT/('browser-export.'+kind.lower());event.value.save_as(target);assert target.stat().st_size>20
  if kind=='XLSX':
   with zipfile.ZipFile(target) as z:assert z.testzip() is None;ET.fromstring(z.read('xl/worksheets/sheet1.xml'))
 case('real CSV download',lambda:export('CSV'));case('real XLSX download and XML validation',lambda:export('XLSX'))
 def picture(kind):
  with page.expect_download() as event:page.locator('.vie-component').first.get_by_role('button',name=kind,exact=True).click()
  target=OUT/('chart.'+kind.lower());event.value.save_as(target);data=target.read_bytes();assert data.startswith(b'\x89PNG') if kind=='PNG' else b'<svg' in data
 case('real SVG export',lambda:picture('SVG'));case('real PNG export',lambda:picture('PNG'))
 case('fullscreen stays in same page',lambda:(page.get_by_role('button',name='Expand',exact=True).click(),page.wait_for_selector('dialog[open]'),page.get_by_role('button',name='Exit expanded view').click()))
 def large():
  start=time.monotonic();page.evaluate('''()=>{const v=fixture(1);v.dataset.columns=v.dataset.columns.slice(0,2);v.dataset.rows=Array.from({length:10000},(_,i)=>({id:'r'+i,values:{name:'GPU '+i,price:i}}));mount(v);}''');assert page.locator('.vie-table tbody tr').count()==50;assert time.monotonic()-start<3
 case('10000-row pagination remains bounded',large)
 case('next page',lambda:(table().get_by_role('button',name='Next',exact=True).click(),page.wait_for_function("document.querySelector('.vie-table').vieState.page===1")))
 case('previous page',lambda:(table().get_by_role('button',name='Previous',exact=True).click(),page.wait_for_function("document.querySelector('.vie-table').vieState.page===0")))
 case('virtual rows bounded',lambda:(table().get_by_label('Table navigation mode').select_option('virtual'),page.wait_for_function("document.querySelectorAll('.vie-table tbody tr').length<80")))
 def scroll():
  table().locator('.vie-table-scroll').evaluate('(e)=>e.scrollTop=300000');page.wait_for_timeout(100);assert page.locator('.vie-table tbody tr').count()<80;assert 'GPU 0' not in page.locator('.vie-table tbody').inner_text()
 case('virtual scroll changes visible rows',scroll)
 case('large table search responsive',lambda:(table().get_by_label('Search table rows').fill('GPU 9999'),page.wait_for_function("document.querySelector('.vie-table').getExportData().rows.length===1",timeout=2000)))
 def copycell():
  page.locator('.vie-table tbody td[tabindex]').first.focus();page.keyboard.press('Control+c');page.wait_for_timeout(50);assert page.evaluate('navigator.clipboard.readText()').startswith('GPU 9999')
 case('Ctrl+C copies focused cell',copycell)
 case('selected row copying',lambda:(page.locator('.vie-table tbody input[type=checkbox]').first.check(),table().get_by_role('button',name='Copy selected rows',exact=True).click(),page.wait_for_timeout(50)))
 case('copy entire table',lambda:(table().get_by_role('button',name='Copy entire table',exact=True).click(),page.wait_for_timeout(50)))
 case('dark theme updates',lambda:(page.evaluate("document.body.classList.add('dark');document.documentElement.setAttribute('data-theme','dark')"),page.wait_for_timeout(250)))
 case('small viewport horizontal scrolling',lambda:(page.set_viewport_size({'width':400,'height':800}),page.wait_for_function("document.querySelector('.vie-table-scroll').scrollWidth>document.querySelector('.vie-table-scroll').clientWidth")))
 page.set_viewport_size({'width':1200,'height':900});page.evaluate("document.body.classList.remove('dark');document.documentElement.setAttribute('data-theme','light');const v=fixture(8);v.charts=[{chartType:'bar',x:'name',series:[{field:'price'}]}];mount(v)");page.wait_for_timeout(350);page.screenshot(path=str(OUT/'visual-light.png'),full_page=True)
 page.evaluate("document.body.classList.add('dark');document.documentElement.setAttribute('data-theme','dark')");page.wait_for_timeout(250);page.screenshot(path=str(OUT/'visual-dark.png'),full_page=True)
 browser.close()
server.shutdown();server.server_close();(OUT/'browser.json').write_text(json.dumps(results,indent=2),encoding='utf8');print(json.dumps({'executed':len(results),'passed':sum(r['status']=='passed' for r in results),'failed':[r for r in results if r['status']!='passed']}));raise SystemExit(any(r['status']!='passed' for r in results))
