import sys,json,time,tempfile,argparse
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from local_model_client import Client
from intelligence.service import Service
from intelligence.registry import Context
parser=argparse.ArgumentParser();parser.add_argument('label');args=parser.parse_args();out=Path('docs/search-results/speed');out.mkdir(parents=True,exist_ok=True)
python=json.loads(Path('docs/search-results/end-to-end/result.json').read_text(encoding='utf8'))['prepared']['evidence'][0]['result']
apple=json.loads(Path(r'C:\Users\developer\Documents\Codex\2026-11-10\files-pasted-by-the-user-codex\outputs\YOEAI-Search-Testing\Desktop-iPhone-repair.json').read_text(encoding='utf8'))['response']['evidence'][0]['result']
rows=[]
for i,(question,fixture) in enumerate([('What is the latest stable Python version? Use official sources.',python),('What is the newest iPhone model? Use official Apple sources.',apple)]):
 client=Client();start=time.perf_counter();queries=[];reads=[]
 with tempfile.TemporaryDirectory(dir='tests_search') as home:
  service=Service(home,Path('../..'),client)
  def search(q,language,cancel):queries.append(q);return fixture['results']
  def read(url,cancel):
   reads.append(url)
   for page in fixture['pages']:
    if page['url']==url:return page
   raise ValueError('Page not in captured fixture')
  service.web.provider.search=search;service.web.provider.read=read
  try:
   result=service.assistant.prepare(Context('speed-session'+str(i),'speed-request'+str(i),question,deadline=time.monotonic()+240));status='passed' if result['sources'] and result['toolCalls']==1 else 'failed'
   row={'id':'SPEED'+str(i+1),'prompt':question,'status':status,'seconds':time.perf_counter()-start,'queries':queries,'pagesRead':len(reads),'sources':result['sources'],'modelCalls':client.events,'result':result}
  except Exception as e:row={'id':'SPEED'+str(i+1),'status':'failed','error':str(e),'modelCalls':client.events,'seconds':time.perf_counter()-start}
  finally:service.web.provider.close()
 rows.append(row);(out/(args.label+'.json')).write_text(json.dumps(rows,indent=2,ensure_ascii=False),encoding='utf8');print(row['id'],row['status'],round(row['seconds'],2),flush=True)
