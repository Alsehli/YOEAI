import json,sys,time,threading,subprocess,types,statistics
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from intelligence.automatic_web import Research
from intelligence.registry import Cancelled
old=types.ModuleType('intelligence.baseline');old.__package__='intelligence';exec(subprocess.check_output(['git','show','checkpoint/search-audit-20261111:intelligence/automatic_web.py'],text=True,encoding='utf8'),old.__dict__)
def model(s,u,n):return '{"search":true,"queries":["query a","query b","query c"],"language":"en"}' if 'Decide' in s else '{"needsMore":false}'
def provider(q,*a):time.sleep(.04);return [{'url':'https://example.org/'+q[-1],'title':q,'content':'fact'}]
def reader(url,event):time.sleep(.04);return {'url':url,'text':'fact'}
results={}
for name,cls in [('before',old.Research),('after',Research)]:
 durations=[]
 for _ in range(5):
  start=time.perf_counter();cls(model,provider,reader).run('compare current facts');durations.append((time.perf_counter()-start)*1000)
 event=threading.Event();entered=threading.Event()
 def slow(url,cancel):entered.set();time.sleep(.35);return {'url':url,'text':'fact'}
 threading.Thread(target=lambda:(entered.wait(1),event.set()),daemon=True).start();start=time.perf_counter()
 try:cls(model,provider,slow).run('compare current facts',cancel=event)
 except Cancelled:pass
 results[name]={'fixtureNetworkMs':durations,'medianMs':statistics.median(durations),'cancelReturnMs':(time.perf_counter()-start)*1000}
results['scope']='Controlled fixture delays only: three independent 40ms searches, three 40ms reads; cancellation during a 350ms reader. Not live internet or GPU throughput.'
out=Path('docs/search-results/performance');out.mkdir(parents=True,exist_ok=True);(out/'comparison.json').write_text(json.dumps(results,indent=2),encoding='utf8');print(json.dumps(results))
