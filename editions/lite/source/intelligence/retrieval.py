"""CPU-only local embeddings and SQLite hybrid retrieval with source references."""
import json,re,threading,time
from pathlib import Path

STOP=set('the and is are was were this that those these of to in on for with what which who how my me it please a an be do does من في على إلى هذا هذه ما هو هي عن مع هل'.split())
def terms(text):return list(dict.fromkeys(x for x in re.findall(r'[^\W_]{2,}',text.casefold()) if x not in STOP))[:18]
class Embeddings:
    def __init__(self,folder):self.folder=Path(folder);self.lock=threading.Lock()
    def available(self):return (self.folder/'model.onnx').is_file() and (self.folder/'tokenizer.json').is_file()
    def encode(self,texts,ctx):
        if not self.available():raise ValueError('The local embedding asset is not installed.')
        if len(texts)>700 or any(not isinstance(t,str) or len(t)>6000 for t in texts):raise ValueError('Embedding batch exceeds its budget.')
        import numpy as np,onnxruntime as ort
        from tokenizers import Tokenizer
        with self.lock:
            ctx.check();tokenizer=Tokenizer.from_file(str(self.folder/'tokenizer.json'));tokenizer.enable_truncation(max_length=192);tokenizer.enable_padding()
            options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1;options.enable_cpu_mem_arena=False
            session=ort.InferenceSession(str(self.folder/'model.onnx'),sess_options=options,providers=['CPUExecutionProvider']);rows=[]
            try:
                names={x.name for x in session.get_inputs()}
                for at in range(0,len(texts),12):
                    ctx.check();encoded=tokenizer.encode_batch(texts[at:at+12]);ids=np.asarray([x.ids for x in encoded],dtype=np.int64);mask=np.asarray([x.attention_mask for x in encoded],dtype=np.int64)
                    feed={'input_ids':ids,'attention_mask':mask,'token_type_ids':np.asarray([x.type_ids for x in encoded],dtype=np.int64)}
                    values=session.run(None,{k:v for k,v in feed.items() if k in names})[0]
                    vectors=values if values.ndim==2 else (values*mask[:,:,None]).sum(axis=1)/np.maximum(mask.sum(axis=1)[:,None],1)
                    vectors=vectors/np.maximum(np.linalg.norm(vectors,axis=1,keepdims=True),1e-9);rows.extend(vectors.astype(np.float32))
                return np.asarray(rows,dtype=np.float32)
            finally:del session  # No embedding model or GPU allocation persists between tool calls.

class Knowledge:
    def __init__(self,store,documents,embedder):self.store=store;self.documents=documents;self.embedder=embedder
    def overview(self,ctx,documents,limit=6):
        if not documents:raise ValueError('Select an indexed document to summarize.')
        selected=list(dict.fromkeys(documents))[:4];passages=[];total=0
        for index,ident in enumerate(selected):
            doc=self.documents.read(ident,ctx);ctx.check()
            with self.store.db() as db:rows=db.execute('SELECT * FROM chunks WHERE document=? ORDER BY ordinal',(ident,)).fetchall()
            total+=len(rows);budget=min(len(rows),limit//len(selected)+(index<limit%len(selected)))
            positions=sorted({round(i*(len(rows)-1)/(budget-1)) for i in range(budget)}) if budget>1 else ([0] if budget else [])
            for position in positions:
                row=rows[position];passages.append({'id':row['id'],'document':ident,'name':doc['name'],'label':row['label'],'text':row['text'],'url':'/assistant/source/'+ident+'?chunk='+str(row['ordinal']),'untrusted':True})
        return {'passages':passages,'method':'bounded overview of selected indexed documents','coverage':{'totalChunks':total,'returnedChunks':len(passages),'complete':total==len(passages)}}
    def encode(self,texts,ctx):
        if not self.embedder.available():return None
        try:return self.embedder.encode(texts,ctx)
        except Exception:
            ctx.check();return None
    def search(self,query,ctx,document=None,limit=6):
        if not 1<=len(query)<=1000:raise ValueError('Use a bounded retrieval query.')
        selected=([document] if isinstance(document,str) else document) or []
        for ident in selected:self.documents.read(ident,ctx)
        tokens=terms(query);keyword=[];semantic=[];records={}
        with self.store.db() as db:
            where=' AND c.document IN ('+','.join('?' for _ in selected)+')' if selected else '';args=selected
            if tokens:
                expression=' OR '.join('"'+t.replace('"','""')+'"' for t in tokens)
                rows=db.execute('SELECT c.*,d.name FROM chunk_fts f JOIN chunks c ON c.id=f.id JOIN documents d ON d.id=c.document WHERE chunk_fts MATCH ?'+where+' ORDER BY bm25(chunk_fts) LIMIT 40',[expression,*args]).fetchall()
                keyword=[r['id'] for r in rows];records.update({r['id']:dict(r) for r in rows})
            encoded=self.encode([query],ctx)
            if encoded is not None:
                import numpy as np
                q=encoded[0]
                rows=db.execute('SELECT c.*,d.name FROM chunks c JOIN documents d ON d.id=c.document WHERE c.vector IS NOT NULL'+where+' LIMIT 20000',args).fetchall()
                if rows:
                    matrix=np.vstack([np.frombuffer(r['vector'],dtype=np.float32) for r in rows]);scores=matrix@q;order=np.argsort(scores)[::-1][:40]
                    semantic=[rows[i]['id'] for i in order if scores[i]>.20];records.update({rows[i]['id']:dict(rows[i]) for i in order})
        scores={}
        for ranking in (keyword,semantic):
            for rank,ident in enumerate(ranking,1):scores[ident]=scores.get(ident,0)+1/(60+rank)
        chosen=[];checked=set()
        for ident in sorted(scores,key=scores.get,reverse=True):
            row=records[ident]
            if row['document'] not in checked:self.documents.read(row['document'],ctx);checked.add(row['document'])
            chosen.append({'id':row['id'],'document':row['document'],'name':row['name'],'label':row['label'],'text':row['text'],'url':'/assistant/source/'+row['document']+'?chunk='+str(row['ordinal']),'untrusted':True})
            if len(chosen)>=limit:break
        if chosen:self.store.session(ctx.session,document=chosen[0]['document'])
        return {'passages':chosen,'method':'reciprocal-rank fusion of local keyword and CPU semantic search' if semantic else 'local keyword search','semanticAvailable':self.embedder.available()}
    def recall(self,query,ctx):
        rows=self.store.memories();tokens=set(terms(query));ranked=[]
        vectors=self.encode([query]+[r['text'] for r in rows],ctx) if rows else None
        if vectors is not None:
            import numpy as np
            scores=vectors[1:]@vectors[0]
            ranked=[(float(scores[i]),r) for i,r in enumerate(rows) if scores[i]>.30]
        else:ranked=[(len(tokens&set(terms(r['text']))),r) for r in rows if tokens&set(terms(r['text']))]
        return {'memories':[{'id':r['id'],'text':r['text'],'untrusted':True} for score,r in sorted(ranked,key=lambda x:x[0],reverse=True)[:4]]}
