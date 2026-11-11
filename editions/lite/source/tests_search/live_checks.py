import json,time,threading,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from intelligence.search_backend import Backend
root=Path(__file__).resolve().parents[3];out=Path(__file__).resolve().parents[1]/'docs/search-results/live';out.mkdir(parents=True,exist_ok=True)
backend=Backend(root,out/'profile');results=[]
try:
 for query in ['Python latest release site:python.org','llama.cpp latest release site:github.com ggml-org','أحدث إصدار بايثون الموقع الرسمي']:
  start=time.perf_counter()
  try:
   rows=backend.search(query,'ar' if query.startswith('أ') else 'en',threading.Event());results.append({'query':query,'seconds':time.perf_counter()-start,'results':rows,'status':'passed' if rows else 'blocked','note':'availability only; relevance manually reviewed'})
  except Exception as e:results.append({'query':query,'seconds':time.perf_counter()-start,'status':'blocked','error':str(e)})
  print(json.dumps(results[-1],ensure_ascii=True),flush=True)
  time.sleep(1)
finally:
 backend.close(force=True);(out/'backend.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
