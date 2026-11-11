"""Per-Windows-profile consent, knowledge records and one-use approval proposals."""
import sqlite3,json,time,uuid,secrets,hashlib,os,re,threading
from contextlib import contextmanager,closing
from pathlib import Path
from .registry import PermissionDenied

SECRET=re.compile(r'PRIVATE KEY-----|\bsk-[A-Za-z0-9_-]{12,}|\bgh[pousr]_[A-Za-z0-9]{15,}|(?:password|api.?key|access.?token)\s*[:=]',re.I)
def no_secrets(value):
    if SECRET.search(value):raise PermissionDenied('Do not store credentials or secrets in assistant memory.')

class Store:
    def __init__(self,home):
        self.home=Path(home)/'Assistant';self.home.mkdir(parents=True,exist_ok=True);self.path=self.home/'knowledge.sqlite3';self.lock=threading.RLock()
        with self.db() as db:
            db.executescript('''
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS scopes(id TEXT PRIMARY KEY,path TEXT,created REAL,selection TEXT);
CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY,scope TEXT,path TEXT UNIQUE,name TEXT,stamp TEXT,created REAL);
CREATE TABLE IF NOT EXISTS chunks(id TEXT PRIMARY KEY,document TEXT,ordinal INTEGER,label TEXT,text TEXT,vector BLOB);
CREATE VIRTUAL TABLE IF NOT EXISTS chunk_fts USING fts5(id UNINDEXED,text,tokenize='unicode61 remove_diacritics 2');
CREATE TABLE IF NOT EXISTS memories(id TEXT PRIMARY KEY,value BLOB,created REAL);
CREATE TABLE IF NOT EXISTS artifacts(id TEXT PRIMARY KEY,name TEXT,created REAL);
CREATE TABLE IF NOT EXISTS tombstones(id TEXT PRIMARY KEY,kind TEXT,created REAL);
CREATE TABLE IF NOT EXISTS approvals(id TEXT PRIMARY KEY,session TEXT,tool TEXT,args TEXT,fingerprint TEXT,expires REAL,used INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS approval_state(id TEXT PRIMARY KEY,snapshot TEXT);
CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY,document TEXT,public_context TEXT,updated REAL);
''')
            db.execute("INSERT INTO chunk_fts(chunk_fts,rank) VALUES('secure-delete',1)")
    @contextmanager
    def db(self):
        db=sqlite3.connect(self.path,timeout=15);db.row_factory=sqlite3.Row;db.execute('PRAGMA foreign_keys=ON');db.execute('PRAGMA secure_delete=ON')
        try:
            with db:yield db
        finally:db.close()
    def authorize(self,path):
        from windows_policy import root_folder
        path=root_folder(path)
        if not path:raise ValueError('Select a specific local folder.')
        path=str(path)
        with self.lock,self.db() as db:
            row=db.execute('SELECT id FROM scopes WHERE path=? AND selection IS NULL',(path,)).fetchone()
            ident=row['id'] if row else uuid.uuid4().hex
            db.execute('INSERT OR IGNORE INTO scopes VALUES(?,?,?,NULL)',(ident,path,time.time()))
        return {'id':ident,'folder':path}
    def authorize_file(self,path):
        path=Path(path).resolve(strict=True)
        from windows_policy import root_folder,scoped_path
        parent=root_folder(path.parent);scoped_path(parent,path.name)
        with self.lock,self.db() as db:
            row=db.execute('SELECT id FROM scopes WHERE path=? AND selection=?',(str(parent),path.name)).fetchone();ident=row['id'] if row else uuid.uuid4().hex
            db.execute('INSERT OR IGNORE INTO scopes VALUES(?,?,?,?)',(ident,str(parent),time.time(),path.name))
        return {'id':ident,'folder':str(parent),'selection':path.name}
    def scopes(self):
        with self.db() as db:return [dict(x) for x in db.execute('SELECT id,path AS folder,selection FROM scopes')]
    def resolve(self,scope,relative,exists=True):
        with self.db() as db:row=db.execute('SELECT path,selection FROM scopes WHERE id=?',(scope,)).fetchone()
        if not row:raise PermissionDenied('Choose and authorize a folder in this conversation first.')
        if row['selection'] is not None and relative!=row['selection']:raise PermissionDenied('Only the selected file is authorized, not its containing folder.')
        from windows_policy import scoped_path
        return scoped_path(row['path'],relative,exists)
    def read_bytes(self,scope,relative,maximum):
        path=self.resolve(scope,relative)
        with path.open('rb') as stream:
            if os.name=='nt':
                import msvcrt,win32file
                actual=win32file.GetFinalPathNameByHandle(msvcrt.get_osfhandle(stream.fileno()),0)
                if actual.startswith('\\\\?\\UNC\\'):actual='\\\\'+actual[8:]
                elif actual.startswith('\\\\?\\'):actual=actual[4:]
                actual=Path(actual)
                if os.path.normcase(str(actual))!=os.path.normcase(str(path)):raise PermissionDenied('The selected file changed location while it was opened.')
            raw=stream.read(maximum+1)
        if len(raw)>maximum:raise ValueError('File exceeds the read budget.')
        return path,raw
    def revoke(self,ident):
        with self.lock,self.db() as db:
            docs=[r[0] for r in db.execute('SELECT id FROM documents WHERE scope=?',(ident,))]
            for doc in docs:self._remove_document(db,doc)
            db.execute('DELETE FROM scopes WHERE id=?',(ident,));db.execute('DELETE FROM approvals')
        self.compact()
        for doc in docs:self.purge_backups(doc,'document')
        return {'revoked':True,'documentsRemoved':len(docs)}
    def _remove_document(self,db,ident):
        db.execute('DELETE FROM chunk_fts WHERE id IN (SELECT id FROM chunks WHERE document=?)',(ident,))
        db.execute('DELETE FROM chunks WHERE document=?',(ident,));db.execute('DELETE FROM documents WHERE id=?',(ident,));db.execute('UPDATE sessions SET document=NULL WHERE document=?',(ident,))
        db.execute('INSERT OR REPLACE INTO tombstones VALUES(?,?,?)',(ident,'document',time.time()))
    def forget_document(self,ident):
        with self.lock,self.db() as db:self._remove_document(db,ident)
        self.compact();self.purge_backups(ident,'document');return {'removed':True}
    def remember(self,text):
        no_secrets(text)
        if not 1<=len(text)<=2000:raise ValueError('Use a memory between 1 and 2,000 characters.')
        import win32crypt
        value=win32crypt.CryptProtectData(text.encode('utf8'),'YOEAI consented memory',None,None,None,0);ident=uuid.uuid4().hex
        with self.lock,self.db() as db:
            if db.execute('SELECT count(*) FROM memories').fetchone()[0]>=200:raise ValueError('Review or remove old memories before adding more.')
            db.execute('INSERT INTO memories VALUES(?,?,?)',(ident,value,time.time()))
        return {'id':ident,'saved':True}
    def artifact(self,name,raw):
        if Path(name).name!=name or len(raw)>4*1024**2:raise ValueError('Artifact exceeds its file budget.')
        folder=self.home/'Artifacts';folder.mkdir(exist_ok=True)
        with self.lock,self.db() as db:
            if sum(p.stat().st_size for p in folder.glob('*') if p.is_file())+len(raw)>64*1024**2:raise ValueError('Generated file storage is full. Remove old generated files in Settings.')
            if db.execute('SELECT count(*) FROM artifacts').fetchone()[0]>=200:raise ValueError('Remove old generated files in Settings before creating another.')
            ident=uuid.uuid4().hex;(folder/(ident+'.data')).write_bytes(raw);db.execute('INSERT INTO artifacts VALUES(?,?,?)',(ident,name,time.time()))
        return {'id':ident,'name':name,'url':'/assistant/artifact/'+ident}
    def artifacts(self):
        with self.db() as db:return [dict(r) for r in db.execute('SELECT * FROM artifacts ORDER BY created DESC LIMIT 200')]
    def forget_artifact(self,ident):
        with self.lock,self.db() as db:db.execute('DELETE FROM artifacts WHERE id=?',(ident,))
        (self.home/'Artifacts'/(ident+'.data')).unlink(missing_ok=True);return {'removed':True}
    def memories(self):
        import win32crypt
        with self.db() as db:rows=db.execute('SELECT * FROM memories ORDER BY created DESC LIMIT 200').fetchall()
        return [{'id':r['id'],'text':win32crypt.CryptUnprotectData(r['value'],None,None,None,0)[1].decode('utf8'),'created':r['created']} for r in rows]
    def forget_memory(self,ident):
        with self.lock,self.db() as db:
            db.execute('DELETE FROM memories WHERE id=?',(ident,));db.execute('INSERT OR REPLACE INTO tombstones VALUES(?,?,?)',(ident,'memory',time.time()));db.execute('DELETE FROM approvals WHERE tool=?',('memory.remember',))
        self.compact();self.purge_backups(ident,'memory');return {'removed':True}
    def purge_backups(self,ident,kind):
        # Managed backups participate in deletion; tombstones also protect imported older copies.
        with self.lock:
            for row in self.backups():
                with closing(sqlite3.connect(self.home/row['name'])) as db,db:
                    db.execute('PRAGMA secure_delete=ON')
                    db.execute("INSERT INTO chunk_fts(chunk_fts,rank) VALUES('secure-delete',1)")
                    if kind=='document':self._remove_document(db,ident)
                    else:
                        db.execute('DELETE FROM memories WHERE id=?',(ident,))
                        db.execute('INSERT OR REPLACE INTO tombstones VALUES(?,?,?)',(ident,'memory',time.time()))
                    db.execute('DELETE FROM approvals');db.execute("INSERT INTO chunk_fts(chunk_fts) VALUES('optimize')")
                with closing(sqlite3.connect(self.home/row['name'])) as db:db.execute('PRAGMA wal_checkpoint(TRUNCATE)');db.execute('VACUUM');db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    def compact(self):
        with self.lock,self.db() as db:
            db.execute("INSERT INTO chunk_fts(chunk_fts) VALUES('optimize')");db.commit();db.execute('PRAGMA wal_checkpoint(TRUNCATE)');db.execute('VACUUM')
    def propose(self,tool,args,ctx,snapshot=None):
        ident=secrets.token_urlsafe(24);raw=json.dumps(args,sort_keys=True,separators=(',',':'));state=json.dumps(snapshot,sort_keys=True);digest=hashlib.sha256((tool.name+'\0'+raw+'\0'+state).encode()).hexdigest()
        with self.lock,self.db() as db:
            db.execute('DELETE FROM approvals WHERE expires<? OR used=1',(time.time(),))
            db.execute('DELETE FROM approval_state WHERE id NOT IN (SELECT id FROM approvals)')
            db.execute('INSERT INTO approvals(id,session,tool,args,fingerprint,expires) VALUES(?,?,?,?,?,?)',(ident,ctx.session,tool.name,raw,digest,time.time()+600))
            db.execute('INSERT INTO approval_state VALUES(?,?)',(ident,state))
        return {'id':ident,'tool':tool.name,'arguments':args,'fingerprint':digest,'expiresInSeconds':600,'description':tool.description,'fileState':snapshot}
    def consume(self,ident,session,fingerprint):
        with self.lock,self.db() as db:
            row=db.execute('SELECT * FROM approvals WHERE id=? AND session=? AND fingerprint=? AND used=0 AND expires>?',(ident,session,fingerprint,time.time())).fetchone()
            if not row:raise PermissionDenied('This approval expired, was already used, or does not match this conversation.')
            db.execute('UPDATE approvals SET used=1 WHERE id=?',(ident,))
            state=db.execute('SELECT snapshot FROM approval_state WHERE id=?',(ident,)).fetchone()
        return row['tool'],json.loads(row['args']),json.loads(state['snapshot']) if state else None
    def session(self,ident,**updates):
        with self.lock,self.db() as db:
            row=db.execute('SELECT * FROM sessions WHERE id=?',(ident,)).fetchone();value=dict(row) if row else {'id':ident,'document':None,'public_context':'[]','updated':time.time()}
            value.update(updates,updated=time.time());db.execute('INSERT OR REPLACE INTO sessions VALUES(?,?,?,?)',(ident,value['document'],value['public_context'],value['updated']));return value
    def backup(self):
        if len(list(self.home.glob('knowledge-backup-*.sqlite3')))>=10:raise ValueError('Remove an old backup before creating another.')
        path=self.home/('knowledge-backup-'+str(time.time_ns())+'.sqlite3')
        with self.lock,self.db() as db,closing(sqlite3.connect(path)) as target:db.backup(target)
        return {'name':path.name}
    def backups(self):return [{'name':p.name,'bytes':p.stat().st_size} for p in sorted(self.home.glob('knowledge-backup-*.sqlite3'),key=lambda p:p.stat().st_mtime,reverse=True)[:10] if p.is_file() and not p.is_symlink()]
    def remove_backup(self,name):
        if Path(name).name!=name or not re.fullmatch(r'knowledge-backup-\d+\.sqlite3',name):raise ValueError('Choose an assistant backup.')
        (self.home/name).unlink(missing_ok=True);return {'removed':True}
    def restore(self,name):
        if Path(name).name!=name or not name.startswith('knowledge-backup-') or not name.endswith('.sqlite3'):raise ValueError('Choose a local assistant backup.')
        path=self.home/name
        if path.is_symlink():raise ValueError('Linked backup files are not accepted.')
        with self.lock,self.db() as db:
            deleted=[tuple(r) for r in db.execute('SELECT * FROM tombstones')]
            consents=[tuple(r) for r in db.execute('SELECT * FROM scopes')]
            artifacts=[tuple(r) for r in db.execute('SELECT * FROM artifacts')]
        with closing(sqlite3.connect(path)) as source,self.db() as target:source.backup(target)
        with self.lock,self.db() as db:
            # A backup restores knowledge, never previously revoked filesystem authority.
            db.execute('CREATE TABLE IF NOT EXISTS artifacts(id TEXT PRIMARY KEY,name TEXT,created REAL)')
            current={(r[1],r[3]):r[0] for r in consents}
            for scope in db.execute('SELECT * FROM scopes').fetchall():
                mapped=current.get((scope['path'],scope['selection']))
                if mapped:db.execute('UPDATE documents SET scope=? WHERE scope=?',(mapped,scope['id']))
                else:
                    for doc in db.execute('SELECT id FROM documents WHERE scope=?',(scope['id'],)).fetchall():self._remove_document(db,doc['id'])
            db.execute('DELETE FROM scopes');db.executemany('INSERT INTO scopes VALUES(?,?,?,?)',consents)
            db.execute('DELETE FROM artifacts');db.executemany('INSERT INTO artifacts VALUES(?,?,?)',artifacts)
            for ident,kind,stamp in deleted:
                if kind=='document':self._remove_document(db,ident)
                else:db.execute('DELETE FROM memories WHERE id=?',(ident,))
                db.execute('INSERT OR REPLACE INTO tombstones VALUES(?,?,?)',(ident,kind,stamp))
            db.execute('DELETE FROM approvals')
        self.compact();return {'restored':True,'deletionsPreserved':len(deleted)}
