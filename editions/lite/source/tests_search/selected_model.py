"""Selected Qwen model via existing local application; captured live search, no repeated internet queries."""
import json,sys,time,urllib.request,traceback,re,argparse
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from intelligence.orchestrator import Assistant
from intelligence.automatic_web import Research
from intelligence.registry import Registry,Tool,Context,obj
parser=argparse.ArgumentParser();parser.add_argument('--limit',type=int,default=10);parser.add_argument('--output',default='docs/search-results/selected-model');args=parser.parse_args();out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
base='http://127.0.0.1:8087';network=json.loads(Path('docs/search-results/live/backend.json').read_text(encoding='utf8'))
results=[];events=[]
def model(system,user,limit,*ctx):
 start=time.perf_counter();first=None;parts=[]
 request=urllib.request.Request(base+'/v1/chat/completions',json.dumps({'messages':[{'role':'system','content':system},{'role':'user','content':user}],'max_tokens':limit,'stream':True,'temperature':0,'response_format':{'type':'json_object'},'chat_template_kwargs':{'enable_thinking':False}}).encode(),{'Content-Type':'application/json','Origin':base})
 with urllib.request.urlopen(request,timeout=100) as response:
  for line in response:
   if not line.startswith(b'data:') or line[5:].strip()==b'[DONE]':continue
   value=json.loads(line[5:]);delta=(value.get('choices')or[{}])[0].get('delta',{}).get('content','')or''
   if delta and first is None:first=time.perf_counter()-start
   parts.append(delta)
 raw=''.join(parts);events.append({'system':system,'user':user,'response':raw,'seconds':time.perf_counter()-start,'firstModelTokenSeconds':first});return raw
cases=[('R01','What is the latest Python version?',True,[]),('R02','Find the newest llama.cpp release.',True,[]),('R03','ما أحدث إصدار بايثون؟',True,[]),('R04','What changed in its latest release?',True,[{'role':'user','content':'Find the newest llama.cpp release.'},{'role':'assistant','content':'We are discussing llama.cpp.'}]),('R05','Explain what prefill means.',False,[]),('R06','Calculate 23 times 7.',False,[]),('R07','Write a short poem about the moon.',False,[]),('R08','Create an image of a red car.',False,[]),('R09','Search for reference images of a GPU.',True,[]),('R10','GPU?',False,[])]
for ident,question,expected,history in cases[:args.limit]:
 start=time.perf_counter();called=[];progress=[];before=len(events)
 registry=Registry(lambda *a:None)
 def research(args,ctx):
  def provider(q,language,cancel):
   called.append(q);return network[1 if 'llama' in (q+question).lower() else 0].get('results',[])
  def reader(url,cancel):
   # Captured search snippets deliberately remain snippets; no invented full article.
   raise ValueError('No captured page available in this selected-model route fixture')
  result=Research(model,provider,reader).run(ctx.question,ctx.history,ctx.cancel)
  return dict(result,sources=[{'title':r['title'],'url':r['url']} for r in result.get('results',[])])
 registry.add(Tool('web.research','Search current public facts, read webpages and assess evidence.',obj({}),{'type':'object'},research,network=True))
 registry.add(Tool('web.photos','Find public reference photographs. Never generate artwork.',obj({}),{'type':'object'},lambda a,c:called.append('photos') or {'sources':[],'photos':[]},network=True))
 try:
  result=Assistant(registry,model,lambda *p:progress.append({'seconds':time.perf_counter()-start,'message':p[-1]})).prepare(Context('real-model-test',ident,question,history=history,deadline=time.monotonic()+240))
  actual=bool(called);status='passed' if actual==expected else 'failed';row={'id':ident,'prompt':question,'expectedSearch':expected,'actualSearch':actual,'status':status,'queries':called,'result':result,'progress':progress,'modelCalls':events[before:]}
 except Exception as e:row={'id':ident,'prompt':question,'status':'failed','error':str(e),'traceback':traceback.format_exc(),'modelCalls':events[before:]}
 row['seconds']=time.perf_counter()-start;results.append(row);(out/'results.json').write_text(json.dumps(results,indent=2,ensure_ascii=False),encoding='utf8');print(ident,row['status'],round(row['seconds'],2),flush=True)
