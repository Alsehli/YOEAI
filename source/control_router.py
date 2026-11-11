from native_ai.client import Connection as NativeConnection
"""Capability routing, not execution or a grant of permissions."""
import json,re

def storage_request(text):
 if not isinstance(text,str):return None
 if re.match(r'[ \t]{0,100}(?:explain|describe|how[ \t]{1,20}(?:do|can|to)|اشرح|كيف)\b',text,re.I):return None
 if not re.search(r'largest|biggest|taking.{0,200}space|أكبر|اكبر',text,re.I) or not re.search(r'files?|folders?|ملفات|ملف|مساحة',text,re.I):return None
 patterns=[r'\b([a-z]):(?:[\\/])?',r'\b([a-z])\s+(?:drive|disk)\b',r'\b(?:drive|disk)\s+([a-z])\b',r'(?:قرص|القرص)\s+([a-z])\b']
 match=next((m for p in patterns if (m:=re.search(p,text,re.I))),None)
 if not match:return {'question':'Which drive should I scan? For example, F:.'}
 n=re.search(r'\b(\d{1,3})\b',text);limit=int(n[1]) if n else 10
 if not 1<=limit<=50:return {'question':'How many files should I show? Choose between 1 and 50.'}
 if re.search(r'\bfolders\b|مجلد',text,re.I):return {'question':'I can list the largest individual files here. Which drive should I scan for files? Folder totals remain available in Windows YOE’s Storage Manager.'}
 return {'drive':match[1].upper()+':\\','limit':limit}

def choose(e,body):
 text=body.get('text');history=body.get('history',[])
 if not isinstance(text,str) or not 1<=len(text)<=3000 or not isinstance(history,list):raise ValueError('Use a short request.')
 # Describing/generating code is not permission to operate the computer,
 # even when the requested code contains verbs such as open/click/delete.
 if re.search(r'\b(?:write|generate|show|create)\b.{0,60}\b(?:code|script|function|program)\b',text,re.I):return {'route':'chat'}
 storage=storage_request(text)
 if storage is not None:return {'route':'storage',**storage}
 from mini_agents import GATE
 if not GATE.acquire(blocking=False):return {'route':'chat','notice':'The selected model is busy; normal chat remains available.'}
 try:
  from language_understanding import context
  schema={'type':'object','properties':{'route':{'type':'string','enum':['chat','web','computer','storage','clarify']},'question':{'type':'string'},'query':{'type':'string'}},'required':['route','question','query'],'additionalProperties':False}
  instructions=('Choose the capability for ONE English/Arabic request, despite spelling mistakes. Return JSON only. '
   'chat: greetings, explanations, writing, coding, arithmetic, supplied-document questions. '
   'web: public factual lookup, who/where/which factual questions, current records, latest news, products, weather, explicit searching for information. "find me who is the tallest man on earth" is web, never a request to select an app. '
   'computer: requests to operate a browser/app, click, type, navigate, launch, or diagnose this PC. "why is my PC slow" is computer: start available read-only diagnostics, do not ask which app first. An explicit request to open Chrome and search is computer; a request for information is web. '
   'storage: inspect local files, find large files, inspect disk usage. Never reinterpret a drive letter as a website. '
   'clarify only when the objective itself is genuinely unclear, with one relevant short question. Never ask which app/website for a factual question or greeting. '
   'For web, query is a short public search query derived ONLY from the current request. Remove conversational filler; preserve exact entities/numbers. Disambiguate the intended subject from similarly named artists/products: a human height record needs current living human height Guinness records, not music. Prefer official sources. Never invent the answer or add a guessed person name. '
   'Examples: "who is the tallest man on earth" -> query="site:guinnessworldrecords.com tallest man living height"; "largest planet" -> query="site:nasa.gov largest planet solar system"; "latest NVIDIA driver" -> query="site:nvidia.com latest GeForce driver". Use site: for a clear authoritative source. Include subject-defining terms, not just the ambiguous original phrase. For non-web routes query is empty. '
   'Writing code that opens a file is chat/code generation, NOT a request to open the file. For non-clarify routes question must be empty. Do not answer or execute. This classification grants no permissions; file writes, submissions and sensitive actions keep their existing checks.')
  # Query planning never receives private conversation history. Normal chat
  # still retains its existing history; computer follow-ups retain scoped tasks.
  payload={'model':'deepseek-local','messages':[{'role':'system','content':instructions},{'role':'user','content':json.dumps({'request':text},ensure_ascii=False)}],'temperature':0,'stream':False,'max_tokens':160,'response_format':{'type':'json_object','schema':schema}}
  conn=NativeConnection(timeout=30)
  try:
   conn.request('POST','/v1/chat/completions',json.dumps(payload),{'Content-Type':'application/json'});r=conn.getresponse();raw=r.read(16000)
   if r.status!=200:raise ValueError('Local routing unavailable.')
   value=json.loads(json.loads(raw)['choices'][0]['message']['content'])
  finally:conn.close()
  if value.get('route') not in schema['properties']['route']['enum']:raise ValueError('Invalid capability decision.')
  query=str(value.get('query','')).strip()[:320]
  if re.search(r'[A-Za-z]:[\\/]|[\w.+-]{1,254}@[\w.-]{1,253}|password[ \t]{0,32}[:=]|api.?key[ \t]{0,32}[:=]',query+' '+text,re.I):return {'route':'clarify','question':'Please remove private paths, passwords or contact details before using public web search.'}
  return {'route':value['route'],'question':str(value.get('question',''))[:300],'query':query if value['route']=='web' else ''}
 except (ValueError,KeyError,TypeError,OSError):return {'route':'chat','notice':'Automatic routing unavailable; no computer action was started.'}
 finally:GATE.release()
