"""Search/retrieval IPC and the reused local-model evidence evaluator."""
import os,json,threading,time,subprocess
from pathlib import Path
from .automatic_web import Research,Cancelled,public_query

class Provider:
    def __init__(self,root,home):
        from .search_backend import Backend
        self.backend=Backend(root,home)
    def search(self,query,language,cancel):return self.backend.search(public_query(query),language,cancel)
    def read(self,url,cancel):
        from .public_reader import read
        return read(url,cancel)
    def close(self):self.backend.close(force=True)

class Web:
    def __init__(self,root,store,model):self.provider=Provider(root,store.home);self.store=store;self.model=model;self.cache={};self.lock=threading.Lock()
    def research(self,args,ctx):
        # Only the original public request and prior public research enter query
        # generation. Private tool results, memories and attachments never enter it.
        question=ctx.question
        if not isinstance(question,str) or not 1<=len(question)<=2000:raise ValueError('Use a public research question of at most 2,000 characters.')
        session=self.store.session(ctx.session);history=json.loads(session['public_context'])[-4:]
        key=json.dumps([question,history],ensure_ascii=False)
        with self.lock:cached=self.cache.get(key)
        if cached and time.monotonic()-cached[0]<90:return dict(cached[1],cacheAgeSeconds=round(time.monotonic()-cached[0],2))
        model=lambda system,user,limit:self.model(system,user,limit,ctx)
        result=Research(model,self.provider.search,self.provider.read).run(question,history,ctx.cancel)
        value={'sources':[{'title':r['title'],'url':r['url']} for r in result.get('results',[])],'results':result.get('results',[]),'pages':result.get('pages',[]),'limitations':result.get('limitations',''),'searched':result.get('searched',False),'retrievedAt':result.get('retrievedAt'),'coverage':result.get('coverage',{}),'claimChecks':result.get('claimChecks',[]),'queries':result.get('queries',[]),'errors':result.get('errors',[])}
        cache_keys=[key]
        if result.get('searched'):
            history.extend([{'role':'user','content':'Public queries: '+'; '.join(result.get('queries',[]))},{'role':'assistant','content':'Public research topics: '+'; '.join(result.get('queries',[]))+'; source titles: '+'; '.join(r['title'] for r in result.get('results',[])[:4])}]);self.store.session(ctx.session,public_context=json.dumps(history[-6:],ensure_ascii=False))
        if result.get('searched'):cache_keys.append(json.dumps([question,history[-4:]],ensure_ascii=False))
        # Cache only usable read evidence. Failed/empty searches must recover immediately.
        if value['pages'] and not value['errors']:
            with self.lock:
                if len(self.cache)>32:self.cache.clear()
                for cache_key in cache_keys:self.cache[cache_key]=(time.monotonic(),value)
        return value
