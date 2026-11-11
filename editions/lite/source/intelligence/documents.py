"""Bounded local extraction; document text is evidence, never instructions."""
import csv,io,re,zipfile,json,hashlib,time,uuid
from pathlib import Path
from html.parser import HTMLParser
from defusedxml import ElementTree as ET

SUPPORTED={'.pdf','.docx','.xlsx','.pptx','.txt','.md','.html','.htm','.rtf','.odt','.csv'}
MAX_BYTES=32*1024**2;MAX_TEXT=600000
def text_decode(raw):
    for encoding in ('utf-8-sig','utf-16','cp1256','cp1252'):
        try:return raw.decode(encoding)
        except UnicodeError:pass
    raise ValueError('The text encoding could not be read.')
def archive(path):
    z=zipfile.ZipFile(path);items=z.infolist()
    if len(items)>2500 or sum(x.file_size for x in items)>100*1024**2 or any(x.file_size>40*1024**2 or x.file_size>max(1,x.compress_size)*250 for x in items):z.close();raise ValueError('Document archive exceeds extraction limits.')
    return z
def xml_text(node):return ' '.join(x.text or '' for x in node.iter() if x.tag.rsplit('}',1)[-1] in ('t','p','span','h'))
def extract(path):
    path=Path(path)
    if not path.is_file() or path.suffix.lower() not in SUPPORTED:raise ValueError('Choose a supported document.')
    if path.stat().st_size>MAX_BYTES:raise ValueError('Document exceeds the 32 MiB extraction limit.')
    ext=path.suffix.lower();sections=[];warnings=[]
    def add(label,text):
        text=re.sub(r'[\t ]+',' ',text).strip()
        if text:sections.append({'label':label,'text':text[:MAX_TEXT]})
        if sum(len(x['text']) for x in sections)>MAX_TEXT:raise ValueError('Document has too much text; select a smaller document or split it into parts.')
    if ext=='.pdf':
        from pypdf import PdfReader
        pdf=PdfReader(path,strict=False)
        if pdf.is_encrypted and not pdf.decrypt(''):raise ValueError('Password-protected PDFs must be unlocked by the user first.')
        if len(pdf.pages)>200:raise ValueError('PDF exceeds the 200-page extraction limit.')
        for index,page in enumerate(pdf.pages):
            value=page.extract_text() or '';add('page '+str(index+1),value)
            if not value.strip():warnings.append('Page '+str(index+1)+' has no extractable text; OCR is not installed.')
    elif ext in ('.txt','.md'):
        value=text_decode(path.read_bytes());lines=value.splitlines()
        for at in range(0,len(lines),40):add('lines '+str(at+1)+'–'+str(min(at+40,len(lines))),'\n'.join(lines[at:at+40]))
    elif ext=='.csv':
        value=text_decode(path.read_bytes());rows=csv.reader(io.StringIO(value))
        batch=[];start=1
        for index,row in enumerate(rows,1):
            if index>15000:raise ValueError('CSV exceeds the 15,000-row limit.')
            batch.append(' | '.join(row[:64]))
            if len(batch)==30:add('rows '+str(start)+'–'+str(index),'\n'.join(batch));batch=[];start=index+1
        if batch:add('rows '+str(start)+'–'+str(index),'\n'.join(batch))
    elif ext=='.rtf':
        from striprtf.striprtf import rtf_to_text
        add('document',rtf_to_text(text_decode(path.read_bytes())))
    elif ext in ('.html','.htm'):
        class Plain(HTMLParser):
            def __init__(self):super().__init__();self.skip=0;self.text=[]
            def handle_starttag(self,tag,attrs):
                if tag in ('script','style'):self.skip+=1
            def handle_endtag(self,tag):
                if tag in ('script','style'):self.skip=max(0,self.skip-1)
            def handle_data(self,value):
                if not self.skip:self.text.append(value)
        parser=Plain();parser.feed(text_decode(path.read_bytes()));add('document','\n'.join(parser.text))
    elif ext=='.xlsx':
        # Reject oversized OOXML expansion before openpyxl reads it.
        with archive(path):pass
        import openpyxl
        book=openpyxl.load_workbook(path,read_only=True,data_only=True,keep_links=False)
        try:
            if len(book.worksheets)>30:raise ValueError('Workbook has too many sheets.')
            for sheet in book:
                batch=[];start=1
                for index,row in enumerate(sheet.iter_rows(max_col=64,values_only=True),1):
                    if index>10000:raise ValueError('Worksheet exceeds the 10,000-row limit.')
                    batch.append(' | '.join('' if v is None else str(v) for v in row))
                    if len(batch)==30:add(sheet.title+' rows '+str(start)+'–'+str(index),'\n'.join(batch));batch=[];start=index+1
                if batch:add(sheet.title+' rows '+str(start)+'–'+str(index),'\n'.join(batch))
        finally:book.close()
        warnings.append('Values are cached cell values; formulas and macros were not executed.')
    else:
        with archive(path) as z:
            if ext=='.docx':
                node=ET.fromstring(z.read('word/document.xml'));paras=[x for x in node.iter() if x.tag.endswith('}p')]
                for at in range(0,len(paras),25):add('paragraphs '+str(at+1)+'–'+str(min(at+25,len(paras))),'\n'.join(xml_text(p) for p in paras[at:at+25]))
            elif ext=='.pptx':
                slides=sorted((n for n in z.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml',n)),key=lambda n:int(re.search(r'(\d+)\.xml',n)[1]))
                if len(slides)>300:raise ValueError('Presentation has too many slides.')
                for index,name in enumerate(slides,1):add('slide '+str(index),xml_text(ET.fromstring(z.read(name))))
            elif ext=='.odt':
                node=ET.fromstring(z.read('content.xml'));add('document','\n'.join(''.join(x.itertext()) for x in node.iter() if x.tag.rsplit('}',1)[-1] in ('p','h')))
    if not sections:raise ValueError('No readable text was found. This document may need OCR or another supported extractor.')
    return {'name':path.name,'sections':sections,'warnings':warnings[:20],'characters':sum(len(s['text']) for s in sections),'untrusted':True,'method':'local format-specific extraction'}

def chunks(sections,size=1300,overlap=180):
    result=[]
    for section in sections:
        value=section['text']
        for at in range(0,len(value),size-overlap):
            part=value[at:at+size]
            if part.strip():result.append({'ordinal':len(result),'label':section['label'],'text':part})
            if len(result)>650:raise ValueError('Document exceeds the chunk budget.')
    return result

class Documents:
    def __init__(self,store,extractor,embedder=None,max_chunks=8000):self.store=store;self.extractor=extractor;self.embedder=embedder;self.max_chunks=max_chunks
    def index(self,scope,relative,ctx):
        path=self.store.resolve(scope,relative);ctx.check()
        if path.suffix.lower() not in SUPPORTED:raise ValueError('This file format is not supported.')
        path,raw=self.store.read_bytes(scope,relative,MAX_BYTES);stamp=hashlib.sha256(raw).hexdigest()
        with self.store.db() as db:
            old=db.execute('SELECT * FROM documents WHERE path=?',(str(path),)).fetchone()
        if old and old['stamp']==stamp:
            self.store.session(ctx.session,document=old['id']);return {'id':old['id'],'name':old['name'],'reused':True}
        snapshot=self.store.home/('extract-'+uuid.uuid4().hex+path.suffix.lower());snapshot.write_bytes(raw)
        try:result=self.extractor(str(snapshot),ctx)
        finally:snapshot.unlink(missing_ok=True)
        parts=chunks(result['sections']);ctx.check()
        with self.store.db() as db:
            total=db.execute('SELECT count(*) FROM chunks').fetchone()[0]
            replacing=db.execute('SELECT count(*) FROM chunks WHERE document=?',(old['id'],)).fetchone()[0] if old else 0
            if total-replacing+len(parts)>self.max_chunks or not old and db.execute('SELECT count(*) FROM documents').fetchone()[0]>=1000:raise ValueError('Local knowledge storage reached its collection limit. Remove old documents before indexing more.')
        vectors=[None]*len(parts)
        if self.embedder and self.embedder.available():
            try:vectors=self.embedder.encode([p['text'] for p in parts],ctx)
            except Exception:
                ctx.check();result['warnings'].append('Semantic indexing is unavailable for this document; keyword retrieval remains available.')
        ident=old['id'] if old else uuid.uuid4().hex
        with self.store.lock,self.store.db() as db:
            total=db.execute('SELECT count(*) FROM chunks').fetchone()[0];replacing=db.execute('SELECT count(*) FROM chunks WHERE document=?',(ident,)).fetchone()[0]
            if total-replacing+len(parts)>self.max_chunks:raise ValueError('The knowledge collection reached its chunk limit during indexing.')
            if old:
                self.store._remove_document(db,ident);db.execute('DELETE FROM tombstones WHERE id=?',(ident,))
            db.execute('INSERT INTO documents VALUES(?,?,?,?,?,?)',(ident,scope,str(path),path.name,stamp,time.time()))
            for p,v in zip(parts,vectors):
                cid=ident+':'+str(p['ordinal']);db.execute('INSERT INTO chunks VALUES(?,?,?,?,?,?)',(cid,ident,p['ordinal'],p['label'],p['text'],v.tobytes() if v is not None else None));db.execute('INSERT INTO chunk_fts VALUES(?,?)',(cid,p['text']))
        self.store.session(ctx.session,document=ident)
        return {'id':ident,'name':path.name,'chunks':len(parts),'warnings':result['warnings'],'semanticIndexed':bool(len(vectors) and vectors[0] is not None)}
    def list(self):
        with self.store.db() as db:return [dict(r) for r in db.execute('SELECT id,name,scope,created FROM documents ORDER BY created DESC LIMIT 1000')]
    def read(self,ident,ctx):
        with self.store.db() as db:doc=db.execute('SELECT * FROM documents WHERE id=?',(ident,)).fetchone()
        if not doc:raise ValueError('This document is not indexed or has been forgotten.')
        path=self.store.resolve(doc['scope'],str(Path(doc['path']).relative_to(next(Path(s['folder']) for s in self.store.scopes() if s['id']==doc['scope']))))
        relative=str(path.relative_to(next(Path(s['folder']) for s in self.store.scopes() if s['id']==doc['scope'])))
        _,raw=self.store.read_bytes(doc['scope'],relative,MAX_BYTES)
        if hashlib.sha256(raw).hexdigest()!=doc['stamp']:raise ValueError('The document changed. Select it again to update its index.')
        return doc
