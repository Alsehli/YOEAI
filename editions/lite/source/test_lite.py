import base64,json,os,time,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).parents[2];OUT=ROOT/'lite-development';HTTP=urllib.request.build_opener(urllib.request.ProxyHandler({}));results=[]
UI_PORT=int(os.environ.get('ALSEHLI_LITE_TEST_UI_PORT','8087'))
def call(prompt,image=None,stream=False):
 content=prompt if image is None else [dict(type='text',text=prompt),dict(type='image_url',image_url=dict(url='data:image/png;base64,'+base64.b64encode(image.read_bytes()).decode()))]
 payload=json.dumps(dict(model='alsehli-lite',messages=[dict(role='user',content=content)],temperature=0,max_tokens=128,stream=stream,stream_options=dict(include_usage=True))).encode();start=time.perf_counter()
 with HTTP.open(urllib.request.Request(f'http://127.0.0.1:{UI_PORT}/v1/chat/completions',payload,{'Content-Type':'application/json'}),timeout=180) as r:
  if not stream:return json.load(r)
  text='';first=None;timings=None
  for line in r:
   if line.startswith(b'data: ') and b'[DONE]' not in line:
    e=json.loads(line[6:]);delta=(e.get('choices') or [{}])[0].get('delta',{}).get('content') or ''
    if delta and first is None:first=time.perf_counter()-start
    text+=delta
    if 'timings' in e:timings=e['timings']
  return dict(text=text,firstTokenSeconds=first,wallSeconds=time.perf_counter()-start,timings=timings)
def run(name,fn):
 try:results.append(dict(test=name,status='PASS',evidence=fn()))
 except Exception as e:results.append(dict(test=name,status='FAIL',error=str(e)))
 (OUT/'functional-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8');print(name,results[-1]['status'],flush=True)
def english():
 r=call('Reply with exactly LITE_OK');assert 'LITE_OK' in r['choices'][0]['message']['content'];return r
def arabic():
 r=call('ما عاصمة البحرين؟ أجب بالعربية.');assert 'المنامة' in r['choices'][0]['message']['content'];return r
def vision():
 r=call('Transcribe all printed text and identify the colored shape.',ROOT/'customer-installer/output/vision-test.png');text=r['choices'][0]['message']['content'];assert '7429' in text and 'red' in text.lower(),text;return r
def security():
 out=[]
 for header in [{'Origin':'https://untrusted.invalid'},{'Host':'untrusted.invalid'}]:
  try:HTTP.open(urllib.request.Request(f'http://127.0.0.1:{UI_PORT}/status',headers=header));raise AssertionError('Untrusted request accepted')
  except urllib.error.HTTPError as e:assert e.code==403;out.append(dict(headers=header,status=e.code))
 return out
def stability():
 out=[]
 for i in range(10):
  r=call(f'Reply with exactly LITE_{i}');assert f'LITE_{i}' in r['choices'][0]['message']['content'];out.append(r['timings'])
 return out
for name,fn in [('English',english),('Arabic',arabic),('Vision_OCR',vision),('Streaming',lambda:call('Explain local AI privacy in forty words.',stream=True)),('Origin_Host_security',security),('Ten_request_stability',stability)]:run(name,fn)
state=json.loads((Path(os.environ['LOCALAPPDATA'])/'AlsehliAILite/engine-state.json').read_text());(OUT/'engine-test-state.json').write_text(json.dumps(state,indent=2))
original_before=json.loads((OUT/'original-server-state-before.json').read_text(encoding='utf-8-sig'));original_after=json.loads(Path('C:/AI/llama.cpp/server-state.json').read_text(encoding='utf-8-sig'));assert original_before==original_after,'Original state changed';print('Original server unchanged')
