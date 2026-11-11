import json,time,threading,subprocess,psutil,urllib.request
from pathlib import Path
from local_model_client import Client,BASE
samples=[];stop=threading.Event()
def sample():
 while not stop.is_set():
  try:
   with urllib.request.urlopen(BASE+'/status',timeout=5) as r:status=json.load(r)
   state=json.loads(Path(r'C:\Users\developer\AppData\Local\YOEAILite\engine-state.json').read_text(encoding='utf8'));p=psutil.Process(state['pid'])
   samples.append({'time':time.time(),'gpuUsedMiB':status['used'],'gpuUtilPercent':status['util'],'workerPid':p.pid,'workerRssBytes':p.memory_info().rss,'workerCpuTimes':p.cpu_times()._asdict(),'selectedModel':status['model'],'activeModel':status['activeModel'],'context':status['context']})
  except Exception as e:samples.append({'error':str(e)})
  stop.wait(.5)
thread=threading.Thread(target=sample,daemon=True);thread.start();client=Client()
try:client('Return only JSON with a public query for the question. Example {"queries":["Python latest release"]}.','What is the latest Python version?',100)
finally:stop.set();thread.join(timeout=7)
out=Path('docs/search-results/performance');(out/'resources.json').write_text(json.dumps({'scope':'sampled during one search-planning inference, not peak profiling','samples':samples,'modelCalls':client.events},indent=2),encoding='utf8');print('Recorded samples:',len(samples))
