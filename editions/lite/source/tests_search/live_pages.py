import sys,json,time,threading
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from intelligence.public_reader import read
out=Path('docs/search-results/live');results=[]
for url in ['https://www.python.org/downloads/','https://github.com/ggml-org/llama.cpp/releases']:
 start=time.perf_counter()
 try:
  page=read(url);results.append({'url':url,'status':'passed' if page['text'].strip() else 'failed','seconds':time.perf_counter()-start,'page':page})
 except Exception as e:results.append({'url':url,'status':'blocked','seconds':time.perf_counter()-start,'error':str(e)})
 print(results[-1]['url'],results[-1]['status'],flush=True)
(out/'pages.json').write_text(json.dumps(results,indent=2),encoding='utf8')
