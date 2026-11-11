from pathlib import Path
import json,os,threading,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from intelligence.search_backend import Backend
root=Path('../..').resolve();home=root/'Lite/Search-UI-QA/no-git-check';home.mkdir(parents=True,exist_ok=True)
os.environ['PATH']=str(Path(os.environ['SystemRoot'])/'System32')
b=Backend(root,home)
try:
 b._ensure(threading.Event());result={'status':'passed','gitOnPath':False,'backendStarted':True,'searchQueries':0}
except Exception as e:result={'status':'failed','error':str(e)}
finally:b.close(force=True)
Path('docs/search-results/ui/no-git-startup.json').write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(result))

