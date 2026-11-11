"""Edition-neutral tool adapters; all host authority comes from explicit UI consent."""
import os,json,time,uuid,hashlib,threading,re,ast
from pathlib import Path
from .registry import Registry,Tool,Context,obj,TEXT,RESULT,PermissionDenied
from .store import Store
from .documents import Documents,SUPPORTED,MAX_BYTES
from .retrieval import Embeddings,Knowledge,terms
from .research import Web
from .orchestrator import Assistant
from .process import run

STRING={'type':'string','minLength':1,'maxLength':1000}
ID={'type':'string','minLength':8,'maxLength':100}
PATH={'type':'string','maxLength':3000}
def output(*keys):return {'type':'object','required':list(keys)}

class Service:
    def __init__(self,home,root,model,edition='Lite'):
        self.root=Path(root);self.edition=edition;self.store=Store(home);self.model=model;self.progresses={};self.lock=threading.RLock();self.approved={}
        self.embeddings=Embeddings(self.root/'Models/multilingual-minilm')
        self.documents=Documents(self.store,lambda path,ctx:run('extract',{'path':path},ctx,25),self.embeddings,8000 if edition=='Lite' else 20000)
        self.knowledge=Knowledge(self.store,self.documents,self.embeddings);self.web=Web(self.root,self.store,model)
        self.registry=Registry(self.propose);self.install_tools();self.assistant=Assistant(self.registry,model,self.progress)
    def snapshot(self,tool,args,ctx):
        if tool=='windows.action' and args['tool'].startswith('files_'):
            self.windows_scope(args);state={}
            for key in ('path','destination'):
                relative=args['params'].get(key)
                if not relative:continue
                path=self.store.resolve(args['scope'],relative,False)
                value={'exists':path.exists(),'directory':path.is_dir()}
                if path.is_file():
                    value.update(size=path.stat().st_size,modified=path.stat().st_mtime_ns)
                    if value['size']<=MAX_BYTES:
                        _,raw=self.store.read_bytes(args['scope'],relative,MAX_BYTES);value['sha256']=hashlib.sha256(raw).hexdigest()
                state[key]=value
            return state
        if tool=='code.execute':return [{'id':ident,'stamp':self.documents.read(ident,ctx)['stamp']} for ident in ctx.documents[:4]]
        return None
    def propose(self,tool,args,ctx):return self.store.propose(tool,args,ctx,self.snapshot(tool.name,args,ctx))
    def progress(self,ident,text):
        with self.lock:
            self.progresses[ident]={'message':text,'updated':time.time()}
            if len(self.progresses)>40:self.progresses.pop(next(iter(self.progresses)))
    def install_tools(self):
        r=self.registry
        r.add(Tool('web.research','Search current public facts, read pages and assess evidence. The trusted host derives public queries from the user request, never private tool evidence.',obj({}),output('sources','pages','limitations'),self.web.research,permission='public_network',timeout=110,network=True))
        r.add(Tool('web.photos','Retrieve actual public photographs with original-page and license metadata, using the existing Wikimedia photo tool. For generated artwork use the existing image generation capability instead.',obj({}),output('photos','sources'),self.photos,permission='public_network',timeout=35,network=True))
        r.add(Tool('files.find','Find matching filenames only inside user-authorized scopes. Omit scope to search authorized folders. This does not read file contents.',obj({'query':STRING,'scope':ID},['query']),output('files'),self.find_files,permission='authorized_files',private=True))
        r.add(Tool('documents.index','Read and index a supported file inside an authorized scope. Use scope/path returned by files.find. Original files are unchanged.',obj({'scope':ID,'path':PATH},['scope','path']),output('id','name'),self.index_document,permission='authorized_files',timeout=100,private=True))
        r.add(Tool('documents.search','Read already indexed documents. Use mode overview to summarize selected documents; use relevant for focused questions. Omit document to use selected documents, or search all authorized indexed documents when none are selected.',obj({'query':STRING,'document':ID,'mode':{'enum':['relevant','overview']}},['query']),output('passages','method'),self.search_documents,permission='authorized_files',timeout=45,private=True))
        r.add(Tool('memory.recall','Recall only relevant user-approved long-term preferences or facts. Conversation history is already provided separately.',obj({'query':STRING},['query']),output('memories'),lambda a,c:self.knowledge.recall(a['query'],c),permission='consented_memory',timeout=45,private=True))
        r.add(Tool('memory.remember','Offer to save a useful user preference. The user must approve the exact text. Never save passwords or secrets.',obj({'text':{'type':'string','minLength':1,'maxLength':2000}},['text']),output('id','saved'),lambda a,c:self.store.remember(a['text']),permission='memory_write',approval=True,modifies=True,private=True))
        r.add(Tool('system.info','Read measured local hardware, RAM, GPU or storage diagnostics. No settings are changed.',obj({'topic':{'enum':['overview','storage','processes']}},['topic']),RESULT,self.system_info,permission='read_diagnostics',private=True))
        actions=['files_mkdir','files_write','files_copy','files_move','files_rename','files_recycle']
        r.add(Tool('windows.action','Propose a bounded existing Windows YOE operation. Requires an authorized folder for files and explicit approval of exact arguments. Existing policy, no-overwrite rules and Recycle Bin apply.',obj({'tool':{'enum':actions},'params':{'type':'object'},'scope':ID},['tool','params']),RESULT,self.windows_action,permission='approved_windows_action',timeout=40,approval=True,modifies=True,private=True))
        r.add(Tool('apps.launch','Offer to launch a supported installed application through existing Windows YOE policy. Browsers may access their home page; exact application requires approval. No arbitrary executable or command line.',obj({'app':{'enum':['notepad','explorer','edge','chrome','word','excel','settings','taskmanager']}},['app']),RESULT,lambda a,c:self.windows_action({'tool':'app_launch','params':{'app':a['app']}},c),permission='approved_launch',timeout=40,approval=True,network=True,modifies=True,private=True))
        r.add(Tool('code.draft','Create a downloadable Python script in assistant-owned artifact storage. This does not execute code or modify the user files.',obj({'code':{'type':'string','minLength':1,'maxLength':20000},'name':{'type':'string','pattern':'^[A-Za-z0-9_-]{1,60}\\.py$'}},['code','name']),output('url','name','executed'),self.code_draft,permission='owned_artifact',modifies=True,private=True))
        if self.sandbox_ready():
            r.add(Tool('code.execute','Run approved Python code only in the qualified Windows AppContainer, with no network capabilities, one process, 512 MiB and a timeout. Standard library only; selected text inputs are supplied in INPUTS.',obj({'code':{'type':'string','minLength':1,'maxLength':20000},'seconds':{'type':'integer','minimum':1,'maximum':30}},['code']),RESULT,self.code_execute,permission='isolated_execution',timeout=75,approval=True,modifies=True,private=True))
    def find_files(self,args,ctx):
        words=terms(args['query']);scopes=[s for s in self.store.scopes() if not args.get('scope') or s['id']==args['scope']];found=[];visited=0
        if not scopes:return {'files':[],'permissionNeeded':'Choose a specific folder or attach a document in this conversation.'}
        for scope in scopes:
            root=Path(scope['folder'])
            candidates=[root/scope['selection']] if scope.get('selection') else None
            if candidates is None:
                candidates=[]
                for parent,dirs,files in os.walk(root,followlinks=False):
                    ctx.check();visited+=1
                    dirs[:]=[d for d in dirs if not d.startswith('.') and not (Path(parent)/d).is_symlink() and not (getattr((Path(parent)/d).lstat(),'st_file_attributes',0)&0x400)]
                    if len(Path(parent).relative_to(root).parts)>=5 or visited>1000:dirs[:]=[]
                    for name in files:
                        if Path(name).suffix.lower() in SUPPORTED:candidates.append(Path(parent)/name)
                    if len(candidates)>3000 or visited>1000:break
            for p in candidates:
                if p.suffix.lower() not in SUPPORTED:continue
                score=sum(w in p.stem.casefold() for w in words)
                if words and not score:continue
                relative=str(p.relative_to(root))
                try:self.store.resolve(scope['id'],relative)
                except (ValueError,OSError):continue
                found.append({'scope':scope['id'],'path':relative,'name':p.name,'score':score})
        return {'files':sorted(found,key=lambda x:-x['score'])[:30],'filenameSearch':True,'indexedContentIsSeparate':True}
    def photos(self,args,ctx):
        from .automatic_web import public_query
        from web_search import clean_query
        import web_photos
        photos=web_photos.search(clean_query(public_query(ctx.question)),self.store.home.parent)[:2]
        return {'photos':photos,'sources':[{'title':p['title'],'url':p['pageUrl']} for p in photos],'provider':'Wikimedia Commons','untrusted':True}
    def windows_scope(self,args):
        scope=next((s for s in self.store.scopes() if s['id']==args.get('scope')),None)
        if args['tool'].startswith('files_') and (not scope or scope.get('selection')):raise PermissionDenied('Authorize a specific folder before modifying files; selecting one attachment does not grant folder-wide write access.')
        from windows_policy import make_scope
        return make_scope({'folder':scope['folder'] if scope else None,'mode':'ASSISTED','apps':[args['params']['app']] if args['tool']=='app_launch' else [],'origins':[],'maxActions':1,'maxSeconds':60,'maxRetries':0})
    def windows_action(self,args,ctx):
        scope=self.windows_scope(args)
        return run('windows',{'action':{'tool':args['tool'],'params':args['params']},'scope':scope,'context':{'home':str(self.store.home)}},ctx,35)
    def system_info(self,args,ctx):
        from windows_policy import make_scope
        scope=make_scope({'mode':'ADVISOR','apps':[],'origins':[],'maxActions':1,'maxSeconds':60})
        return run('windows',{'action':{'tool':'system_info','params':{'topic':args['topic']}},'scope':scope,'context':{'home':str(self.store.home)}},ctx,20)
    def code_draft(self,args,ctx):
        ast.parse(args['code']);artifact=self.store.artifact(args['name'],args['code'].encode('utf8'))
        return {**artifact,'executed':False,'syntaxChecked':True,'sources':[{'title':args['name'],'url':artifact['url']}]}
    def sandbox_ready(self):
        try:
            value=json.loads((self.root/'SandboxRuntime/qualification.json').read_text())
            from .qualification import owner
            if value.get('owner')!=owner():return False
            actual=hashlib.sha256((self.root/'SandboxRuntime/runtime-manifest.json').read_bytes()).hexdigest()
            return value.get('passed') is True and value.get('runtimeManifestSHA256')==actual
        except Exception:return False
    def code_execute(self,args,ctx):
        if not self.sandbox_ready():raise PermissionDenied('The genuine sandbox is not qualified on this installation. The script can be downloaded, but will not run on the host.')
        runtime=self.root/'SandboxRuntime';manifest=runtime/'runtime-manifest.json'
        if hashlib.sha256(manifest.read_bytes()).hexdigest()!='3a95f73e4d0e435cb1c59a8c105f44cc4803cd93ada41815b70d970c7256ec0c':raise PermissionDenied('Sandbox interpreter manifest is not trusted.')
        for record in json.loads(manifest.read_text())['files']:
            path=(runtime/record['path']).resolve()
            if not path.is_relative_to(runtime.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest()!=record['sha256']:raise PermissionDenied('Sandbox interpreter integrity check failed.')
        ast.parse(args['code']);inputs={}
        selected_names=[self.documents.read(ident,ctx)['name'] for ident in ctx.documents[:4]]
        if len(set(selected_names))!=len(selected_names):raise ValueError('Selected documents have duplicate filenames. Select unique filenames so code inputs are unambiguous.')
        for ident in ctx.documents[:4]:
            doc=self.documents.read(ident,ctx)
            if Path(doc['name']).suffix.lower() in ('.csv','.txt','.md'):
                from .documents import text_decode
                scope=next(s for s in self.store.scopes() if s['id']==doc['scope']);relative=str(Path(doc['path']).relative_to(Path(scope['folder'])));_,raw=self.store.read_bytes(doc['scope'],relative,160000);inputs[doc['name']]=text_decode(raw)
            else:
                with self.store.db() as db:parts=db.execute('SELECT text FROM chunks WHERE document=? ORDER BY ordinal LIMIT 8',(ident,)).fetchall()
                inputs[doc['name']]='DOCUMENT EXCERPTS (may overlap):\n'+'\n'.join(r[0] for r in parts)[:20000]
        if len(json.dumps(inputs,ensure_ascii=False).encode('utf8'))>160000:raise ValueError('Selected inputs exceed the isolated execution input budget.')
        source='INPUTS = '+repr(inputs)+'\n'+args['code']
        jobs=self.store.home/'SandboxJobs'/uuid.uuid4().hex
        try:return self._run_code(args,ctx,source,jobs)
        finally:
            if jobs.exists() and jobs.parent==self.store.home/'SandboxJobs' and re.fullmatch('[a-f0-9]{32}',jobs.name):
                import shutil
                shutil.rmtree(jobs)
    def _run_code(self,args,ctx,source,jobs):
        result=run('sandbox',{'home':str(jobs),'runtime':str(self.root/'SandboxRuntime'),'files':{'test_main.py':source},'timeout':args.get('seconds',20)},ctx,70)
        jobdir=Path(result.pop('jobDirectory')).resolve();artifacts=[]
        try:
            if not jobdir.is_relative_to(jobs.resolve()) or not re.fullmatch('[a-f0-9]{32}',jobdir.name):raise ValueError('Unexpected sandbox output directory.')
            if result['status']=='PASSED':
                for file in (jobdir/'output').iterdir():
                    if file.name=='run.log' or not file.is_file() or file.is_symlink() or getattr(file.lstat(),'st_file_attributes',0)&0x400:continue
                    if file.suffix.lower() not in ('.txt','.csv','.json','.png','.jpg','.jpeg','.pdf'):continue
                    if file.stat().st_size<=4*1024**2:artifacts.append(self.store.artifact(file.name,file.read_bytes()))
            value=result.get('output','');result['output']=value[:16000];result['outputTruncated']=len(value)>16000
            result['artifacts']=artifacts;result['sources']=[{'title':a['name'],'url':a['url']} for a in artifacts]
            return result
        finally:
            if jobdir.is_relative_to(jobs.resolve()) and re.fullmatch('[a-f0-9]{32}',jobdir.name):
                import shutil
                shutil.rmtree(jobdir)
    def index_document(self,args,ctx):
        result=self.documents.index(args['scope'],args['path'],ctx)
        with self.lock:
            if result['id'] not in ctx.documents:ctx.documents=(ctx.documents+[result['id']])[-4:]
            details=[d for d in getattr(ctx,'document_details',[]) if d['id']!=result['id']]
            ctx.document_details=(details+[{'id':result['id'],'name':result['name'],'indexed':True}])[-4:]
        return result
    def search_documents(self,args,ctx):
        selected=[args['document']] if args.get('document') else ctx.documents
        if args.get('mode')=='overview':return self.knowledge.overview(ctx,selected)
        return self.knowledge.search(args['query'],ctx,selected)
    def prepare(self,body,cancel):
        session=body['session'];saved=self.store.session(session);documents=body['documents'] if 'documents' in body else ([saved['document']] if saved.get('document') else [])
        history=body.get('history',[])
        if not history and not documents:history=json.loads(saved['public_context'])[-4:]
        ctx=Context(session,body['requestId'],body['query'],history,documents,cancel,deadline=time.monotonic()+180)
        ctx.scopes=[{'id':s['id'],'name':Path(s['folder']).name,'selectedFileOnly':s.get('selection')} for s in self.store.scopes()]
        ctx.document_details=[{'id':d['id'],'name':d['name'],'indexed':True} for d in self.documents.list() if d['id'] in documents]
        with self.lock:completed=self.approved.pop(session,[])
        return self.assistant.prepare(ctx,completed)
    def approve(self,body,cancel=None):
        tool,args,snapshot=self.store.consume(body['id'],body['session'],body['fingerprint']);saved=self.store.session(body['session']);docs=[r['id'] for r in (snapshot or [])] if tool=='code.execute' else ([saved['document']] if saved.get('document') else [])
        ctx=Context(body['session'],body.get('requestId',uuid.uuid4().hex),'Approved operation',documents=docs,cancel=cancel or threading.Event(),deadline=time.monotonic()+100,approved=True,private_seen=True)
        if self.snapshot(tool,args,ctx)!=snapshot:raise PermissionDenied('The selected files changed after the preview. Review a fresh proposal before applying it.')
        result=self.registry.execute(tool,args,ctx)
        with self.lock:self.approved.setdefault(body['session'],[]).append({'tool':tool,'arguments':args,'result':result,'untrusted':True})
        return {'tool':tool,'result':result,'completed':True}
