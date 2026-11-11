"""Planning uses the existing selected model, shared gate and private pipe client."""
import json,sys,time
from pathlib import Path
from .registry import Cancelled

def ensure_model(vision=False):
    app=sys.modules.get('app') or sys.modules.get('__main__')
    if app and hasattr(app,'CONFIG') and hasattr(app,'start'):
        import lite_native
        from builtin_vision import activate
        activate(app.APP,app.DATA,app.config,vision=vision)
    else:
        from model_modes import ensure_selected
        ensure_selected()

def call(system,user,limit,ctx):
    from mini_agents import GATE
    from native_ai.client import Connection
    if not GATE.acquire(blocking=False):raise ValueError('The shared local model is busy. Wait for its current task.')
    conn=None
    try:
        ctx.check()
        ensure_model()
        from native_ai.manager import INSTANCE
        def count(text):return len(list(INSTANCE.request('tokenize',text=text,timeout=15))[-1]['native_result']['tokens'])
        budget=int(INSTANCE.state.get('context',8192))-limit-192
        if count(system+'\n'+user)>budget:
            value=json.loads(user)
            if isinstance(value.get('tools'),list):value['tools']=[{k:t[k] for k in ('name','description','inputSchema','approvalRequired') if k in t} for t in value['tools']]
            def clip(v,n,key=''):
                if isinstance(v,str):return v if key in ('tool','name','url','query','question','pattern','type') else v[:n]
                if isinstance(v,list):return [clip(x,n,key) for x in v[-6:] if x is not None] if key=='history' else [clip(x,n,key) for x in v]
                if isinstance(v,dict):return {k:clip(x,n,k) for k,x in v.items()}
                return v
            for n in (1200,600,250):
                user=json.dumps(clip(value,n),ensure_ascii=False)
                if count(system+'\n'+user)<=budget:break
            else:raise ValueError('The selected context is too small for this tool request. Reduce the request or choose a larger supported context.')
        ctx.check();conn=Connection(timeout=max(1,min(60,ctx.deadline-time.monotonic())));conn.cancel=ctx.cancel
        conn.request('POST','/v1/chat/completions',json.dumps({'messages':[{'role':'system','content':system},{'role':'user','content':user}],'max_tokens':limit,'stream':True,'temperature':0,'response_format':{'type':'json_object'},'chat_template_kwargs':{'enable_thinking':False}}),{})
        response=conn.getresponse();pieces=[]
        while True:
            ctx.check();line=response.readline()
            if not line:break
            if not line.startswith(b'data:'):continue
            raw=line[5:].strip()
            if raw==b'[DONE]':break
            event=json.loads(raw)
            if event.get('error'):raise ValueError(str(event['error']))
            pieces.append((event.get('choices') or [{}])[0].get('delta',{}).get('content','') or '')
        return ''.join(pieces)
    finally:
        if conn:conn.close()
        GATE.release()

def prepare_images(messages,vision):
    working=json.loads(json.dumps(messages));omitted=0
    if vision:return working,omitted
    last_user=max((i for i,m in enumerate(working) if m['role']=='user'),default=-1)
    for i,message in enumerate(working):
        content=message['content']
        if not isinstance(content,list):continue
        images=sum(p.get('type')=='image_url' for p in content)
        if images and i==last_user:raise ValueError('This model is text only. Choose a model with a matching vision projector for the attached image.')
        message['content']='\n'.join(p.get('text','') for p in content if p.get('type')=='text')
        if images:message['content']+='\n[Earlier image omitted because the current model is text only. Its pixels are unavailable; do not claim to inspect them.]'
        omitted+=images
    return working,omitted

def fit(messages,max_tokens=1024):
    """Use the actual local tokenizer; reserve conservative chat/vision overhead."""
    from mini_agents import GATE
    from native_ai.manager import INSTANCE
    if not isinstance(messages,list) or not messages or len(messages)>500:raise ValueError('Choose a shorter active conversation.')
    for m in messages:
        if not isinstance(m,dict) or m.get('role') not in ('system','user','assistant') or not isinstance(m.get('content'),(str,list)):raise ValueError('Invalid generation messages.')
    if not GATE.acquire(blocking=False):raise ValueError('The local model is busy.')
    try:
        from builtin_vision import has_current_image
        ensure_model(vision=has_current_image(messages))
        working,omitted=prepare_images(messages,bool(INSTANCE.state.get('vision')));removed=0;excerpted=False;capacity=int(INSTANCE.state['context'])
        def usage():
            texts=[];images=0
            for message in working:
                if isinstance(message['content'],str):texts.append(message['content'])
                else:
                    for p in message['content']:
                        if p.get('type')=='text':texts.append(p.get('text',''))
                        elif p.get('type')=='image_url':images+=1
            tokens=list(INSTANCE.request('tokenize',text='\n'.join(texts),timeout=15))[-1]['native_result']['tokens']
            return len(tokens)+64*len(working)+images*1200+max_tokens+128
        while usage()>capacity:
            conversational=[i for i,m in enumerate(working) if m['role']!='system']
            if len(conversational)>1:
                first=conversational[0];role=working[first]['role'];working.pop(first);removed+=1
                if role=='user' and first<len(working)-1 and working[first]['role']=='assistant':working.pop(first);removed+=1
                continue
            last=working[-1];content=last['content']
            if isinstance(content,list):parts=[p for p in content if p.get('type')=='text'];part=parts[-1] if parts else None;text=part.get('text','') if part else ''
            else:part=None;text=content
            marker='\n\nUNTRUSTED_TOOL_EVIDENCE:\n'
            if marker not in text or excerpted:raise ValueError('This message and its evidence exceed the selected context. Attach a document for passage retrieval or shorten the message.')
            prefix,raw=text.split(marker,1);data=json.loads(raw)
            def clip(v,key=''):
                if isinstance(v,str):return v if key in ('url','id','document') or len(v)<=500 else v[:500]+' [excerpt]'
                if isinstance(v,list):return [clip(x,key) for x in v[:6]]
                if isinstance(v,dict):return {k:clip(x,k) for k,x in v.items()}
                return v
            value=prefix+marker+json.dumps(clip(data),ensure_ascii=False)
            if part is not None:part['text']=value
            else:last['content']=value
            excerpted=True
        return {'messages':working,'trimmedMessages':removed,'evidenceExcerpted':excerpted,'omittedHistoryImages':omitted,'tokenizerChecked':True,'context':capacity}
    finally:GATE.release()
