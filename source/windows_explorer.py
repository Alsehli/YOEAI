"""Bounded local file explorer/storage jobs. UI actions never grant model tools."""
import os,json,time,uuid,threading,sqlite3,hashlib,heapq,shutil,mimetypes,re,contextlib
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from windows_policy import root_folder,scoped_path,relative_path,PROTECTED,PRIVATE_NAME,redact
from windows_file_safety import cleanup_allowed,available

CATEGORIES={'Documents':'.pdf .doc .docx .xls .xlsx .ppt .pptx .txt .md .csv .odt .rtf','Images':'.jpg .jpeg .png .webp .bmp .tif .tiff .gif .heic','Videos':'.mp4 .mov .mkv .avi .webm .m4v','Audio':'.mp3 .wav .flac .aac .ogg .m4a','Applications':'.exe .msi .msix .appx','Archives':'.zip .rar .7z .tar .gz .bz2','AI Models':'.gguf .safetensors .onnx .ckpt','Programming':'.py .js .ts .tsx .jsx .cpp .c .h .cs .java .rs .go .html .css .sql .sh .ps1','Games':'','Temporary Files':'','Other':''}
EXTENSIONS={x:category for category,extensions in CATEGORIES.items() for x in extensions.split()}
TEXT={'.txt','.md','.csv','.json','.py','.js','.ts','.css','.log','.yaml','.yml','.ini','.xml'}
OPENABLE={'.pdf','.txt','.md','.csv','.docx','.xlsx','.pptx','.odt','.rtf','.png','.jpg','.jpeg','.webp','.bmp','.tif','.tiff','.gif','.mp4','.mov','.mkv','.webm','.mp3','.wav','.flac'}
PROTECTED_DELETE={'.gguf','.safetensors','.onnx','.ckpt','.dll','.sys','.pyd','.db','.sqlite3','.vhd','.vhdx'}

def category(path):
 p=Path(path)
 # A Steam manifest is a verifiable installation marker, not an age heuristic.
 if any(part.lower()=='steamapps' for part in p.parts) and (p.suffix.lower()=='.acf' or 'common' in [part.lower() for part in p.parts]):return 'Games'
 return EXTENSIONS.get(p.suffix.lower(),'Other')

def signature(path):
 if not path.is_file():return None
 with path.open('rb') as file:head=file.read(16)
 for magic,label in [(b'%PDF-','PDF'),(b'\x89PNG\r\n\x1a\n','PNG'),(b'\xff\xd8\xff','JPEG'),(b'GGUF','GGUF'),(b'PK\x03\x04','ZIP container'),(b'II*\x00','TIFF'),(b'MM\x00*','TIFF'),(b'BM','BMP'),(b'\x1aE\xdf\xa3','Matroska/WebM')]:
  if head.startswith(magic):return label
 if head.startswith(b'RIFF') and head[8:12]==b'WEBP':return 'WebP'
 return 'Not identified from the bounded header; extension is only a hint'

def pdf_preview(path,page=None):
 from PySide6.QtCore import QCoreApplication,QSize,QBuffer,QIODevice
 from PySide6.QtPdf import QPdfDocument
 if QCoreApplication.instance() is None:raise ValueError('PDF preview requires the YOEAI desktop window.')
 if path.stat().st_size>200*1024**2:raise ValueError('PDF preview is limited to 200 MiB. Use approved Open for larger documents.')
 doc=QPdfDocument()
 try:
  error=doc.load(str(path))
  if error!=QPdfDocument.Error.None_:raise ValueError('PDF could not be opened. It may be encrypted or damaged.')
  count=doc.pageCount()
  if page is None:return {'pages':count}
  if not 0<=page<count:raise ValueError('Choose an existing PDF page.')
  points=doc.pagePointSize(page)
  if points.width()<=0 or points.height()<=0:raise ValueError('Invalid PDF page dimensions.')
  scale=min(1600/points.width(),2000/points.height(),2)
  image=doc.render(page,QSize(max(1,int(points.width()*scale)),max(1,int(points.height()*scale))))
  if image.isNull():raise ValueError('PDF page rendering failed.')
  buffer=QBuffer();buffer.open(QIODevice.OpenModeFlag.WriteOnly);image.save(buffer,'PNG');return bytes(buffer.data())
 finally:doc.close()

def stamp(path):
 s=path.stat();return {'size':s.st_size,'mtimeNs':s.st_mtime_ns,'inode':s.st_ino,'directory':path.is_dir()}
def hidden(entry):return entry.name.startswith('.') or bool(getattr(entry.stat(follow_symlinks=False),'st_file_attributes',0)&2)
def safe_name(value):
 if not isinstance(value,str) or not value.strip() or len(value)>160 or any(c in value for c in '/\\:*?"<>|') or value.endswith((' ','.')) or value in {'.','..'} or value.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]}:raise ValueError('Use one ordinary Windows file/folder name.')
 return value

class Explorer:
 def __init__(self,e):
  self.e=e;self.home=e.home/'FileExplorer';self.home.mkdir(exist_ok=True);self.db=self.home/'catalog.sqlite3';self.roots={};self.jobs={};self.pending={};self.lock=threading.RLock()
  with self.connect() as db:
   db.executescript('''CREATE TABLE IF NOT EXISTS entries(job TEXT,path TEXT,name TEXT,size INTEGER,modified REAL,created REAL,kind TEXT,category TEXT,extension TEXT,parent TEXT,PRIMARY KEY(job,path));CREATE INDEX IF NOT EXISTS entry_name ON entries(job,name COLLATE NOCASE);CREATE INDEX IF NOT EXISTS entry_size ON entries(job,size);CREATE INDEX IF NOT EXISTS entry_date ON entries(job,modified);CREATE TABLE IF NOT EXISTS folders(job TEXT,path TEXT,size INTEGER,PRIMARY KEY(job,path));CREATE TABLE IF NOT EXISTS categories(key TEXT PRIMARY KEY,category TEXT);CREATE TABLE IF NOT EXISTS audit(time REAL,action TEXT,detail TEXT);DELETE FROM entries;DELETE FROM folders;''')
   db.executescript('CREATE TABLE IF NOT EXISTS transactions(id TEXT PRIMARY KEY,data TEXT);CREATE TABLE IF NOT EXISTS scans(id TEXT PRIMARY KEY,data TEXT);')
   self.recovered=0
   for table in ['transactions','scans']:
    for ident,raw in db.execute("SELECT id,data FROM "+table+" WHERE json_extract(data,'$.status')='RUNNING'").fetchall():
     value=json.loads(raw)
     if value.get('status')=='RUNNING':value.update(status='INTERRUPTED',notice='Application restarted. Work was not automatically repeated. Inspect originals and destinations before retrying.');db.execute('UPDATE '+table+' SET data=? WHERE id=?',(json.dumps(value),ident));self.recovered+=1
 @contextlib.contextmanager
 def connect(self):
  db=sqlite3.connect(self.db,timeout=15)
  try:
   with db:yield db
  finally:db.close()
 def audit(self,action,value):
  with self.connect() as db:db.execute('INSERT INTO audit VALUES(?,?,?)',(time.time(),action,json.dumps(value,ensure_ascii=False)))
 def scan_record(self,j):
  value=self.state(j['id']);value['folder']=str(self.roots.get(j['scope'],'Revoked scope'))
  with self.connect() as db:db.execute('INSERT OR REPLACE INTO scans VALUES(?,?)',(j['id'],json.dumps(value)))
 def journal(self,plan,j):
  value={'id':j['id'],'status':j['status'],'plan':plan,'job':self.state(j['id'])}
  with self.connect() as db:db.execute('INSERT OR REPLACE INTO transactions VALUES(?,?)',(j['id'],json.dumps(value)))
 def history(self):
  with self.connect() as db:
   actions=[json.loads(r[0]) for r in db.execute('SELECT data FROM transactions ORDER BY rowid DESC LIMIT 20')]
   scans=[json.loads(r[0]) for r in db.execute('SELECT data FROM scans ORDER BY rowid DESC LIMIT 10')]
  return {'actions':actions,'scans':scans,'recovered':self.recovered}
 def grant(self,path):
  root=root_folder(path)
  if root is None:raise ValueError('Choose a specific folder.')
  if len(self.roots)>=8:raise ValueError('Revoke an old folder scope first (8 maximum).')
  sid=uuid.uuid4().hex;self.roots[sid]=root;self.audit('read_scope',{'scope':sid,'folder':str(root)});return {'id':sid,'folder':str(root),'name':root.name}
 def root(self,sid):
  if sid not in self.roots:raise ValueError('Folder access is missing or revoked. Choose and approve the folder again.')
  return root_folder(self.roots[sid])
 def path(self,sid,relative='',exists=True):return scoped_path(self.root(sid),relative,exists)
 def revoke(self,sid):
  for job in self.jobs.values():
   if job['scope']==sid:job['cancel'].set()
  self.roots.pop(sid,None)
 def drives(self):
  import psutil
  out=[]
  for part in psutil.disk_partitions():
   try:
    if os.name=='nt':
     import ctypes
     if ctypes.windll.kernel32.GetDriveTypeW(part.mountpoint)==4:continue
    usage=psutil.disk_usage(part.mountpoint);out.append({'path':part.mountpoint,'device':part.device,'type':part.fstype,'total':usage.total,'used':usage.used,'free':usage.free})
   except OSError:pass
  return out
 def start(self,sid,relative='',recursive=False,show_hidden=False):
  path=self.path(sid,relative)
  if not path.is_dir():raise ValueError('Choose a folder to browse.')
  with self.lock:
   if sum(j['status']=='RUNNING' for j in self.jobs.values())>=2:raise ValueError('Stop a scan before starting another (2 active jobs maximum).')
   # Cached metadata only; never delete user files during cache eviction.
   done=[j for j in self.jobs.values() if j['status']!='RUNNING']
   for old in sorted(done,key=lambda j:j['created'])[:-5]:
    with self.connect() as db:db.execute('DELETE FROM entries WHERE job=?',(old['id'],));db.execute('DELETE FROM folders WHERE job=?',(old['id'],))
    self.jobs.pop(old['id'],None)
   job={'id':uuid.uuid4().hex,'scope':sid,'path':relative,'folderStamp':stamp(path),'recursive':recursive,'hidden':show_hidden,'status':'RUNNING','created':time.time(),'count':0,'bytes':0,'skipped':0,'cancel':threading.Event(),'partial':False,'error':None};self.jobs[job['id']]=job
  threading.Thread(target=self.scan,args=(job,),daemon=True,name='YOE-files-scan').start();return self.state(job['id'])
 def state(self,jid):
  if jid not in self.jobs:raise ValueError('This scan expired. Refresh the folder.')
  value={k:v for k,v in self.jobs[jid].items() if k!='cancel'};value['partial']=value.get('partial',False) or value.get('skipped',0)>0;return value
 def inventory(self,sid,relative):
  root=self.path(sid,relative);stack=[root];out=[]
  while stack:
   folder=stack.pop()
   with os.scandir(folder) as entries:
    for ent in entries:
     rel=relative_path(Path(folder)/ent.name,self.root(sid)).as_posix();p=self.path(sid,rel)
     if len(out)>=500:raise ValueError('Folder actions are limited to 500 descendants. Select a smaller folder.')
     value={'relative':relative_path(p,root).as_posix(),'snapshot':stamp(p)};out.append(value)
     if p.is_dir():stack.append(p)
  return sorted(out,key=lambda v:v['relative'])
 def verify_duplicates(self,sid,paths):
  if not isinstance(paths,list) or not 2<=len(paths)<=50:raise ValueError('Select 2–50 files to verify.')
  files=[];seen=set()
  for relative in paths:
   p=self.path(sid,relative)
   if not p.is_file():raise ValueError('Duplicate verification accepts files only.')
   identity=str(p).casefold()
   if identity in seen:raise ValueError('Select distinct file paths.')
   seen.add(identity);files.append((relative,stamp(p)))
  if sum(s['size'] for _,s in files)>10*1024**3:raise ValueError('Verify at most 10 GiB per batch.')
  if sum(j['status']=='RUNNING' for j in self.jobs.values())>=2:raise ValueError('Stop another disk job first.')
  j={'id':uuid.uuid4().hex,'scope':sid,'path':'','operation':'verify duplicates','status':'RUNNING','created':time.time(),'count':0,'bytes':0,'cancel':threading.Event(),'partial':False,'error':None,'results':[]};self.jobs[j['id']]=j
  def work():
   groups={};deadline=time.monotonic()+180;counts={s['size']:sum(x['size']==s['size'] for _,x in files) for _,s in files}
   def check():
    self.root(sid)
    if j['cancel'].is_set() or self.e.closed:raise InterruptedError('Duplicate verification cancelled.')
    if time.monotonic()>deadline:raise InterruptedError('Verification time limit reached. Try fewer/smaller files.')
   try:
    for relative,snapshot in files:
     check()
     if counts[snapshot['size']]<2:continue
     p=self.path(sid,relative);h=hashlib.sha256()
     with p.open('rb') as file:
      while True:
       check();block=file.read(1024*1024)
       if not block:break
       h.update(block);j['bytes']+=len(block)
     if stamp(p)!=snapshot:raise ValueError('A file changed during verification. No duplicates were confirmed.')
     groups.setdefault((snapshot['size'],h.hexdigest()),[]).append((relative,snapshot));j['count']+=1
    confirmed=[]
    for (length,digest),matches in groups.items():
     if len(matches)<2:continue
     first=self.path(sid,matches[0][0])
     for relative,snapshot in matches[1:]:
      check()
      with first.open('rb') as a,self.path(sid,relative).open('rb') as b:
       while True:
        check();left=a.read(1024*1024);right=b.read(1024*1024);j['bytes']+=len(left)+len(right)
        if left!=right:raise ValueError('Byte comparison differed despite matching hashes. Nothing is marked duplicate.')
        if not left:break
     if any(stamp(self.path(sid,p))!=snap for p,snap in matches):raise ValueError('A file changed before confirmation.')
     identities={s['inode'] for _,s in matches};confirmed.append({'paths':[p for p,_ in matches],'bytesEach':length,'sha256':digest,'contentVerified':True,'samePhysicalFile':len(identities)==1,'notice':'Hard links to the same file; deleting a path may reclaim no data.' if len(identities)==1 else 'Choose which copy to retain. No deletion is automatic.'})
    j.update(results=confirmed,status='COMPLETED')
   except Exception as ex:j.update(status='CANCELLED' if isinstance(ex,InterruptedError) else 'FAILED',error=redact(str(ex)))
   finally:j['finished']=time.time();self.audit('duplicate_verification',self.state(j['id']))
  threading.Thread(target=work,daemon=True,name='YOE-duplicate-verification').start();return self.state(j['id'])
 def scan(self,j):
  buffer=[];sizes={};deadline=time.monotonic()+180
  self.scan_record(j)
  def flush():
   with self.connect() as db:
    db.executemany('INSERT OR REPLACE INTO entries VALUES(?,?,?,?,?,?,?,?,?,?)',buffer)
    db.executemany('INSERT INTO folders VALUES(?,?,?) ON CONFLICT(job,path) DO UPDATE SET size=size+excluded.size',[(j['id'],p,size) for p,size in sizes.items()])
   buffer.clear();sizes.clear()
   self.scan_record(j)
  try:
   root=self.root(j['scope']);stack=[j['path']]
   with self.connect() as db:overrides=dict(db.execute('SELECT key,category FROM categories LIMIT 5000').fetchall())
   while stack:
    relative=stack.pop();folder=self.path(j['scope'],relative)
    try:
     with os.scandir(folder) as entries:
      for ent in entries:
       if j['cancel'].is_set() or self.e.closed:j['status']='CANCELLED';break
       if j['count']>=200000 or time.monotonic()>deadline:j['partial']=True;break
       try:
        s=ent.stat(follow_symlinks=False)
        if ent.is_symlink() or getattr(s,'st_file_attributes',0)&0x400 or ent.name.lower() in PROTECTED or PRIVATE_NAME.search(ent.name) or (not j['hidden'] and hidden(ent)):j['skipped']+=1;continue
        # The containing folder was scope-validated above; entries are metadata only.
        rel=(Path(relative)/ent.name).as_posix();p=Path(folder)/ent.name;directory=ent.is_dir(follow_symlinks=False);kind='folder' if directory else 'file';size=0 if directory else s.st_size;cat=category(p)
        key=hashlib.sha256((str(root)+'\0'+rel).encode()).hexdigest()
        override=overrides.get(key)
        if override:cat=override
        buffer.append((j['id'],rel,ent.name,size,s.st_mtime,s.st_ctime,kind,cat,Path(ent.name).suffix.lower(),str(Path(rel).parent)))
        j['count']+=1;j['bytes']+=size
        if directory and j['recursive']:
         if len(Path(rel).parts)<40 and len(stack)<5000:stack.append(rel)
         else:j['partial']=True
        if not directory:
         for parent in Path(rel).parents:sizes[str(parent)]=sizes.get(str(parent),0)+size
        if len(buffer)>=200:flush()
       except (ValueError,OSError):j['skipped']+=1
     if j['cancel'].is_set() or j['partial']:break
    except OSError:j['skipped']+=1
   flush()
   if j['status']=='RUNNING':j['status']='COMPLETED'
  except Exception as error:j.update(status='FAILED',error=redact(str(error)));flush()
  finally:j['finished']=time.time();self.scan_record(j);self.audit('scan',self.state(j['id']))
 def listing(self,jid,offset=0,sort='name',descending=False,search='',cat=''):
  j=self.state(jid);self.root(j['scope']);offset=max(0,min(200000,int(offset)));column={'name':'name COLLATE NOCASE','size':'size','date':'modified','type':'extension'}.get(sort,'name COLLATE NOCASE');where='job=?';args=[jid]
  if search:where+=' AND instr(lower(name),lower(?))>0';args.append(str(search)[:200])
  if cat:
   if cat not in CATEGORIES:raise ValueError('Unknown category.')
   where+=' AND category=?';args.append(cat)
  with self.connect() as db:
   total=db.execute('SELECT count(*) FROM entries WHERE '+where,args).fetchone()[0]
   records=db.execute('SELECT path,name,size,modified,created,kind,category,extension FROM entries WHERE '+where+' ORDER BY '+column+(' DESC' if descending else ' ASC')+',path LIMIT 100 OFFSET ?',[*args,offset]).fetchall()
  stale=stamp(self.path(j['scope'],j['path']))!=j.get('folderStamp')
  keys=['path','name','size','modified','created','kind','category','extension'];return {'job':j,'stale':stale,'total':total,'offset':offset,'limit':100,'rows':[dict(zip(keys,r)) for r in records]}
 def dashboard(self,jid):
  j=self.state(jid);self.root(j['scope']);now=time.time()
  with self.connect() as db:
   categories=[{'name':r[0],'bytes':r[1],'files':r[2]} for r in db.execute("SELECT category,sum(size),count(*) FROM entries WHERE job=? AND kind='file' GROUP BY category ORDER BY sum(size) DESC",(jid,))]
   largest=[{'path':r[0],'bytes':r[1]} for r in db.execute('SELECT path,size FROM folders WHERE job=? AND path!=? ORDER BY size DESC LIMIT 20',(jid,'.'))]
   recent=[r[0] for r in db.execute("SELECT path FROM entries WHERE job=? AND kind='file' ORDER BY created DESC LIMIT 10",(jid,))]
   duplicates=[{'size':r[0],'count':r[1],'notice':'Same-size candidates, not verified duplicates'} for r in db.execute("SELECT size,count(*) FROM entries WHERE job=? AND kind='file' AND size>=1048576 GROUP BY size HAVING count(*)>1 ORDER BY size*count(*) DESC LIMIT 20",(jid,))]
   largest_files=[{'path':r[0],'bytes':r[1]} for r in db.execute("SELECT path,size FROM entries WHERE job=? AND kind='file' ORDER BY size DESC LIMIT 20",(jid,))]
   old=db.execute("SELECT path,size,extension FROM entries WHERE job=? AND kind='file' AND modified<? AND ((category='Archives' AND size>=104857600) OR extension IN ('.msi','.msix')) ORDER BY size DESC LIMIT 20",(jid,now-90*86400)).fetchall()
   old_downloads=db.execute("SELECT path,size FROM entries WHERE job=? AND kind='file' AND modified<? AND category IN ('Documents','Images','Videos','Audio','Archives') AND (lower(path) LIKE '%downloads/%' OR lower(path) LIKE '%downloads\\%' OR ?='downloads') ORDER BY size DESC LIMIT 10",(jid,now-90*86400,self.root(j['scope']).name.casefold())).fetchall()
  return {'job':j,'categories':categories,'largestFolders':largest,'largestFiles':largest_files,'recentlyCreated':recent,'duplicateCandidates':duplicates,'recommendations':[{'path':r[0],'bytes':r[1],'risk':'Medium · review required','reason':'Installer/archive last modified over 90 days ago; age does not prove it is unused or safe to remove.'} for r in old]+[{'path':r[0],'bytes':r[1],'risk':'High · user file','reason':'An older item in a Downloads-named location. Its modification date is not last use; keep it unless you know it is no longer needed.'} for r in old_downloads],'notice':'Logical file sizes, not allocated space. Categories use extensions or explicit corrections; they are not proof of format validity or safety. Hard links/sparse files can affect totals. Scan limits or inaccessible/hidden folders make results partial. Last modification is not last use. Scans are snapshots; Refresh after changes. No deletion is automatic.'}
 def video_preview(self,sid,relative):
  import subprocess
  from video_generation_adapter import generator
  source=self.path(sid,relative);suffix=source.suffix.lower()
  demux={'.mp4':'mov','.mov':'mov','.m4v':'mov','.webm':'matroska','.mkv':'matroska','.avi':'avi'}.get(suffix)
  if not demux or not source.is_file():raise ValueError('Choose an MP4, MOV, WebM, MKV or AVI file.')
  if sum(j['status']=='RUNNING' for j in self.jobs.values())>=2:raise ValueError('Stop another disk job first.')
  ffmpeg=Path(generator().config(require=False)['ffmpeg'])
  if not ffmpeg.is_file():raise ValueError('The existing local video preview component is unavailable. Use approved Open.')
  cache=self.home/'VideoPreviews';cache.mkdir(exist_ok=True)
  if cache.is_symlink():raise ValueError('Linked preview cache blocked.')
  for old in sorted(cache.glob('*.webm'),key=lambda p:p.stat().st_mtime)[:-2]:
   if re.fullmatch(r'[0-9a-f]{32}\.webm',old.name) and not old.is_symlink():old.unlink()
  j={'id':uuid.uuid4().hex,'scope':sid,'path':relative,'operation':'prepare video preview','status':'RUNNING','created':time.time(),'count':0,'bytes':0,'cancel':threading.Event(),'partial':False,'error':None,'results':[]};self.jobs[j['id']]=j;snapshot=stamp(source)
  def work():
   proc=None;target=cache/(j['id']+'.webm')
   try:
    args=[str(ffmpeg),'-hide_banner','-loglevel','error','-nostdin','-n','-threads','2','-protocol_whitelist','file,pipe','-f',demux]
    if demux=='mov':args+=['-enable_drefs','0','-use_absolute_path','0']
    args+=['-i',str(source),'-t','20','-map','0:v:0','-an','-vf',"scale='min(960,iw)':-2",'-c:v','libvpx-vp9','-threads','2','-deadline','realtime','-cpu-used','8','-crf','35','-b:v','0','-fs','50000000',str(target)]
    proc=subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));deadline=time.monotonic()+90
    while proc.poll() is None:
     self.root(sid)
     if self.e.closed or j['cancel'].wait(.1):raise InterruptedError('Video preview cancelled.')
     if time.monotonic()>deadline:raise InterruptedError('Video preview timed out. Use approved Open with your player.')
    if proc.returncode or not target.is_file() or target.stat().st_size<20:raise ValueError('This video could not be decoded. Use approved Open with your player.')
    if stamp(self.path(sid,relative))!=snapshot:raise ValueError('The source video changed. Refresh before previewing.')
    j.update(status='COMPLETED',count=1,bytes=target.stat().st_size,results=[{'previewJob':j['id'],'sourceSnapshot':snapshot,'notice':'Local compatibility preview: first 20 seconds, up to 960 px, silent. Original is unchanged.'}])
   except Exception as error:j.update(status='CANCELLED' if isinstance(error,InterruptedError) else 'FAILED',error=redact(str(error)))
   finally:
    if proc is not None and proc.poll() is None:proc.terminate();proc.wait(5)
    if j['status']!='COMPLETED' and target.exists():target.unlink()
    self.audit('video_preview',self.state(j['id']))
  threading.Thread(target=work,daemon=True,name='YOE-video-preview').start();return self.state(j['id'])
 def properties(self,sid,relative):
  p=self.path(sid,relative);s=p.stat();key=hashlib.sha256((str(self.root(sid))+'\0'+relative_path(p,self.root(sid)).as_posix()).encode()).hexdigest()
  with self.connect() as db:override=db.execute('SELECT category FROM categories WHERE key=?',(key,)).fetchone()
  return {'path':str(p),'name':p.name,'category':override[0] if override else category(p),'categorySource':'User correction' if override else 'File extension; not proof of format validity','bytes':None if p.is_dir() else s.st_size,'modified':s.st_mtime,'created':s.st_ctime,'folder':p.is_dir(),'signature':signature(p),'readOnly':not os.access(p,os.W_OK),'notice':'Folder content sizes require a storage scan.' if p.is_dir() else ''}
 def propose(self,b):
  sid=b.get('scope');operation=b.get('operation');paths=b.get('paths',[])
  if operation not in {'copy','move','rename','mkdir','recycle','open','organize'}:raise ValueError('Unsupported file action.')
  if not isinstance(paths,list) or not 1<=len(paths)<=200 or not all(isinstance(p,str) for p in paths):raise ValueError('Select 1–200 items.')
  if operation in {'rename','mkdir','open'} and len(paths)!=1:raise ValueError('Select one item for this action.')
  target_sid=(b.get('targetScope') or sid) if operation in {'copy','move'} else sid;self.root(sid);self.root(target_sid);items=[]
  self.pending={k:v for k,v in self.pending.items() if v['expires']>=time.time()}
  if len(self.pending)>=64:raise ValueError('Too many pending plans. Wait for old plans to expire.')
  for relative in paths:
   if operation=='mkdir':
    p=self.path(sid,relative);name=safe_name(b.get('name'));dest=self.path(sid,(Path(relative)/name).as_posix(),False);item={'source':relative,'snapshot':stamp(p),'destination':str(relative_path(dest,self.root(sid)))}
   else:
    p=self.path(sid,relative)
    if p==self.root(sid):raise ValueError('The approved root folder cannot be modified.')
    if p.is_dir() and operation not in {'rename','copy','move'}:raise ValueError('Select individual files for recycling, opening or organization.')
    if operation in {'recycle','organize'}:cleanup_allowed(p)
    if operation in {'move','rename','recycle','organize'}:available(p)
    item={'source':relative,'snapshot':stamp(p)}
    if p.is_dir() and operation in {'copy','move'}:item['inventory']=self.inventory(sid,relative)
    if operation=='rename':dest=self.path(sid,(Path(relative).parent/safe_name(b.get('name'))).as_posix(),False)
    elif operation in {'copy','move'}:
     folder=self.path(target_sid,b.get('destination',''))
     if not folder.is_dir():raise ValueError('Choose a destination folder.')
     dest=self.path(target_sid,relative_path(folder/p.name,self.root(target_sid)).as_posix(),False)
    elif operation=='organize':
     cat=self.properties(sid,relative)['category']
     if cat not in {'Documents','Images','Videos','Audio','Archives'}:raise ValueError('Automatic organization is limited to ordinary documents/media/archives. Other files require manual selection and review.')
     dest=self.path(sid,(Path(relative).parent/cat/p.name).as_posix(),False)
    else:dest=None
    if operation=='open' and p.suffix.lower() not in OPENABLE:raise ValueError('Executable/script/active-content files cannot be opened by this tool.')
    if dest is not None:item['destination']=str(relative_path(dest,self.root(target_sid)))
    if dest is not None and p.is_dir() and Path(str(dest).removeprefix('\\\\?\\')).is_relative_to(Path(str(p).removeprefix('\\\\?\\'))):raise ValueError('A folder cannot be copied/moved inside itself.')
   if 'destination' in item and self.path(target_sid,item['destination'],False).exists():raise ValueError('Destination already exists. Overwriting is blocked.')
   items.append(item)
  total=sum(i['snapshot']['size'] if not i['snapshot']['directory'] else sum(v['snapshot']['size'] for v in i.get('inventory',[]) if not v['snapshot']['directory']) for i in items)
  if total>100*1024**3:raise ValueError('Select at most 100 GiB per operation.')
  nonce=uuid.uuid4().hex;plan={'id':nonce,'scope':sid,'targetScope':target_sid,'sourceRoot':str(self.root(sid)),'targetRoot':str(self.root(target_sid)),'operation':operation,'items':items,'totalBytes':total,'expires':time.time()+120,'notice':'Approve these exact items once. No overwrite, elevation or permanent-delete fallback.'};self.pending[nonce]=plan;return plan
 def organize_plan(self,jid):
  j=self.state(jid);self.root(j['scope'])
  if j['status']=='RUNNING':raise ValueError('Wait for the listing/scan to finish before organizing.')
  with self.connect() as db:paths=[r[0] for r in db.execute("SELECT path FROM entries WHERE job=? AND parent=? AND kind='file' AND category IN ('Documents','Images','Videos','Audio','Archives') ORDER BY name LIMIT 200",(jid,str(Path(j['path'] or '.'))))]
  if not paths:raise ValueError('No eligible documents/media/archives found directly in this folder. Nothing will be moved.')
  eligible=[];conflicts=[]
  for path in paths:
   cat=self.properties(j['scope'],path)['category'];parent=Path(path).parent
   if parent.name==cat:continue
   target=(parent/cat/Path(path).name).as_posix();folder=self.path(j['scope'],(parent/cat).as_posix(),False)
   if self.path(j['scope'],target,False).exists() or folder.exists() and not folder.is_dir():conflicts.append({'source':path,'destination':target,'reason':'Destination/name already exists. It will not be overwritten.'})
   else:eligible.append(path)
  if not eligible:return {'blocked':True,'conflicts':conflicts,'notice':'No conflict-free files need organization. Existing names and files were preserved.'}
  plan=self.propose({'scope':j['scope'],'operation':'organize','paths':eligible});plan['conflicts']=conflicts;return plan
 def undo_plan(self,tid):
  with self.connect() as db:row=db.execute('SELECT data FROM transactions WHERE id=?',(tid,)).fetchone()
  if not row:raise ValueError('Recovery record is unavailable.')
  record=json.loads(row[0]);old=record['plan'];completed=record['job'].get('results',[])
  if old['operation'] not in {'move','rename','organize'} or not completed:raise ValueError('Automatic reversal is available for completed moves/renames/organization only. Recycle restoration uses the Windows Recycle Bin.')
  def find(root):
   return next((sid for sid,p in self.roots.items() if str(p).casefold()==str(root).casefold()),None)
  source=find(old['targetRoot']);target=find(old['sourceRoot'])
  if not source or not target:raise ValueError('Approve read access to both original and destination folders again before preparing recovery.')
  items=[]
  for result in completed:
   relative=result.get('destinationRelative');original=result.get('sourceRelative')
   if not relative or original is None:continue
   p=self.path(source,relative)
   if stamp(p)!=result.get('destinationSnapshot'):raise ValueError('A destination changed after the operation. Manual recovery is required; it will not be overwritten or moved automatically.')
   destination=self.path(target,original,False)
   if destination.exists():raise ValueError('The original path is now occupied. Recovery will not overwrite it.')
   item={'source':relative,'destination':original,'snapshot':stamp(p)}
   if p.is_dir():item['inventory']=self.inventory(source,relative)
   items.append(item)
  nonce=uuid.uuid4().hex;plan={'id':nonce,'scope':source,'targetScope':target,'sourceRoot':old['targetRoot'],'targetRoot':old['sourceRoot'],'operation':'move','items':items,'totalBytes':sum(x['snapshot']['size'] if not x['snapshot']['directory'] else sum(v['snapshot']['size'] for v in x.get('inventory',[]) if not v['snapshot']['directory']) for x in items),'expires':time.time()+120,'undoOf':tid,'notice':'Review the exact reverse moves. Empty organization folders are retained. No overwrite or automatic replay.'};self.pending[nonce]=plan;return plan
 def execute(self,nonce,approve):
  if approve is not True:raise ValueError('Explicit approval is required.')
  plan=self.pending.pop(nonce,None)
  if not plan or plan['expires']<time.time():raise ValueError('Approval expired or was already used. Review a new plan.')
  if not self.e.windows_enabled:raise ValueError('Enable Windows YOE for this session before changing or opening files.')
  # Revalidate every selected source before any side effect.
  for item in plan['items']:
   if stamp(self.path(plan['scope'],item['source']))!=item['snapshot']:raise ValueError('A selected item changed. Nothing was started; review a new plan.')
   if item.get('inventory') is not None and self.inventory(plan['scope'],item['source'])!=item['inventory']:raise ValueError('Folder contents changed. Review a new plan.')
   if plan['operation'] in {'move','rename','recycle','organize'}:available(self.path(plan['scope'],item['source']))
  if plan['operation'] in {'copy','move'}:
   destination=self.root(plan['targetScope']);same_volume=self.root(plan['scope']).stat().st_dev==destination.stat().st_dev
   needed=0 if plan['operation']=='move' and same_volume else plan['totalBytes']
   if shutil.disk_usage(destination).free<needed+16*1024**2:raise ValueError('Insufficient destination space. No files were changed.')
  if sum(j['status']=='RUNNING' for j in self.jobs.values())>=2:raise ValueError('Stop a current scan/action first. Review a new approval when ready.')
  jid=uuid.uuid4().hex;j={'id':jid,'scope':plan['scope'],'path':'','operation':plan['operation'],'status':'RUNNING','created':time.time(),'count':0,'bytes':0,'cancel':threading.Event(),'partial':False,'error':None,'results':[]};self.jobs[jid]=j
  self.journal(plan,j);threading.Thread(target=self.mutate,args=(plan,j),daemon=True,name='YOE-files-approved').start();return self.state(jid)
 def copy_file(self,plan,j,src_relative,dst_relative,snapshot):
  p=self.path(plan['scope'],src_relative);dest=self.path(plan['targetScope'],dst_relative,False);digest=hashlib.sha256()
  def cancel():return j['cancel'].is_set() or not self.e.windows_enabled or self.e.closed or time.time()-j['created']>900
  if os.name=='nt':
   from windows_file_safety import native_copy
   base=j['bytes'];native_copy(p,dest,cancel,lambda transferred:j.update(bytes=base+transferred))
   with p.open('rb') as src:
    while True:
     if cancel():raise InterruptedError('Verification stopped. Original and destination retained.')
     block=src.read(1024*1024)
     if not block:break
     digest.update(block)
  else:
   with p.open('rb') as src,dest.open('xb') as out:
    while True:
     if cancel():raise InterruptedError('Stopped or time limit reached. Original and partial destination retained.')
     block=src.read(1024*1024)
     if not block:break
     out.write(block);digest.update(block);j['bytes']+=len(block)
  if stamp(p)!=snapshot:raise ValueError('Source changed during copy; original and new copy were retained.')
  check=hashlib.sha256()
  with self.path(plan['targetScope'],dst_relative).open('rb') as verify:
   while True:
    if j['cancel'].is_set() or not self.e.windows_enabled:raise InterruptedError('Stopped during verification. Original and new copy retained.')
    block=verify.read(1024*1024)
    if not block:break
    check.update(block)
  actual=check.hexdigest()
  if actual!=digest.hexdigest():raise ValueError('Copy verification failed; original retained.')
  os.utime(dest,ns=(p.stat().st_atime_ns,snapshot['mtimeNs']))
  return actual
 def mutate(self,plan,j):
  try:
   for item in plan['items']:
    if j['cancel'].is_set() or not self.e.windows_enabled:raise InterruptedError('Stopped. Completed actions are listed; they are not automatically undone.')
    p=self.path(plan['scope'],item['source']);operation=plan['operation']
    if stamp(p)!=item['snapshot']:raise ValueError('Source changed after approval.')
    if operation=='recycle':
     from windows_tools import files_tool
     result=files_tool('files_recycle',{'path':item['source']},{'folder':str(self.root(plan['scope']))})
     if not result.get('verified'):raise ValueError('Windows did not verify recycling. Inspect the original file and Recycle Bin before retrying.')
    elif operation=='open':os.startfile(str(p));result={'opened':item['source'],'notice':'Default application launched; reading or successful playback is not verified.'}
    else:
     dest=self.path(plan['targetScope'],item['destination'],False)
     if dest.exists():raise ValueError('Destination appeared after approval; overwrite blocked.')
     if operation=='organize':self.path(plan['targetScope'],Path(item['destination']).parent.as_posix(),False).mkdir(exist_ok=True)
     if operation=='mkdir':dest.mkdir();result={'created':str(dest),'verified':dest.is_dir()}
     elif operation=='rename':
      os.rename(p,dest)
      if p.exists() or stamp(dest)!=item['snapshot']:raise ValueError('Rename verification failed. Inspect the recorded source and destination.')
      result={'renamed':str(dest),'verified':True}
     elif operation in {'move','organize'} and p.stat().st_dev==dest.parent.stat().st_dev:
      os.rename(p,dest)
      if p.exists() or stamp(dest)!=item['snapshot']:raise ValueError('Move state could not be verified. Inspect source and destination.')
      j['bytes']+=sum(v['snapshot']['size'] for v in item.get('inventory',[]) if not v['snapshot']['directory']) if item['snapshot']['directory'] else item['snapshot']['size'];result={'destination':str(dest),'verified':True,'atomic':True}
     elif item['snapshot']['directory']:
      dest.mkdir()
      for entry in sorted(item['inventory'],key=lambda v:(len(Path(v['relative']).parts),v['relative'])):
       if j['cancel'].is_set():raise InterruptedError('Folder copy stopped. Original and partial destination retained.')
       source=(Path(item['source'])/entry['relative']).as_posix();target=(Path(item['destination'])/entry['relative']).as_posix()
       if entry['snapshot']['directory']:self.path(plan['targetScope'],target,False).mkdir()
       else:self.copy_file(plan,j,source,target,entry['snapshot'])
      if self.inventory(plan['scope'],item['source'])!=item['inventory']:raise ValueError('Folder changed during copying. Original retained.')
      if operation=='move':
       for entry in sorted(item['inventory'],key=lambda v:len(Path(v['relative']).parts),reverse=True):
        if j['cancel'].is_set():raise InterruptedError('Move stopped during original cleanup; verified destination retained.')
        original=self.path(plan['scope'],(Path(item['source'])/entry['relative']).as_posix())
        if not entry['snapshot']['directory'] and stamp(original)!=entry['snapshot']:raise ValueError('Original changed before cleanup; remaining originals and destination retained.')
        original.rmdir() if entry['snapshot']['directory'] else original.unlink()
       self.path(plan['scope'],item['source']).rmdir()
      result={'destination':str(dest),'verified':True,'filesVerified':sum(not x['snapshot']['directory'] for x in item['inventory'])}
     else:
      actual=self.copy_file(plan,j,item['source'],item['destination'],item['snapshot'])
      if operation=='move':
       original=self.path(plan['scope'],item['source'])
       if stamp(original)!=item['snapshot']:raise ValueError('Original changed before move completion; both copies retained.')
       original.unlink()
      result={'destination':str(dest),'sha256':actual,'verified':True}
    result['sourceRelative']=item['source'];result['destinationRelative']=item.get('destination')
    if item.get('destination'):result['destinationSnapshot']=stamp(self.path(plan['targetScope'],item['destination']))
    j['results'].append(result);j['count']+=1;self.journal(plan,j)
   j['status']='COMPLETED'
  except Exception as error:j.update(status='CANCELLED' if isinstance(error,InterruptedError) else 'FAILED',error=redact(str(error)),partial=bool(j['results'] or j['bytes']))
  finally:j['finished']=time.time();self.journal(plan,j);self.audit('approved_'+plan['operation'],{'plan':plan,'result':self.state(j['id'])})

def service(e):
 with e.db_lock:
  if not hasattr(e,'file_explorer'):e.file_explorer=Explorer(e)
 return e.file_explorer

def route(handler,e,body,post):
 s=service(e);path=urlsplit(handler.path);action=path.path.removeprefix('/mini/windows/files/');q=parse_qs(path.query)
 try:
  if action=='drives' and not post:value={'drives':s.drives(),'scopes':[{'id':i,'folder':str(p),'name':p.name} for i,p in s.roots.items()],'recoveredJobs':s.recovered}
  elif action=='grant' and post:
   if body.get('approve') is not True:raise ValueError('Approve read access to this specific folder.')
   value=s.grant(body.get('folder'))
  elif action=='grant-task' and post:
   task=e.get(body.get('task'));w=task.get('windows',{})
   receipt=next((r for r in reversed(task.get('tools',[])) if r.get('name')=='files_explorer' and r.get('status')=='PASS' and r.get('result',{}).get('explorer')),None)
   if task.get('agent')!='windows' or not w.get('planApproved') or not receipt:raise ValueError('An approved Windows task and completed explorer-scope receipt are required.')
   value=s.grant(w['scope'].get('folder'));value['request']=receipt['result']['explorer']
  elif action=='revoke' and post:s.revoke(body.get('scope'));value={'revoked':True}
  elif action=='browse' and post:value=s.start(body.get('scope'),body.get('path',''),False,body.get('hidden') is True)
  elif action=='scan' and post:value=s.start(body.get('scope'),body.get('path',''),True,body.get('hidden') is True)
  elif action=='cancel' and post:s.jobs[body['job']]['cancel'].set();value=s.state(body['job'])
  elif action=='list' and post:value=s.listing(body.get('job'),body.get('offset',0),body.get('sort','name'),body.get('descending') is True,body.get('search',''),body.get('category',''))
  elif action=='dashboard' and post:value=s.dashboard(body.get('job'))
  elif action=='state' and post:value=s.state(body.get('job'))
  elif action=='video-preview' and post:value=s.video_preview(body.get('scope'),body.get('path'))
  elif action=='properties' and post:value=s.properties(body.get('scope'),body.get('path'))
  elif action=='duplicates' and post:value=s.verify_duplicates(body.get('scope'),body.get('paths'))
  elif action=='organize' and post:value=s.organize_plan(body.get('job'))
  elif action=='history' and not post:value=s.history()
  elif action=='undo' and post:value=s.undo_plan(body.get('id'))
  elif action=='preferences' and not post:
   from memory_controls import notes
   saved=[r for r in notes(e,'windows') if r['text'].startswith('File explorer preference: ')]
   value={'notes':saved}
  elif action=='remember-view' and post:
   if body.get('approve') is not True:raise ValueError('Approve remembering this file-view preference.')
   if body.get('sort') not in ['name','size','date','type'] or body.get('view') not in ['grid','list'] or type(body.get('descending'))!=bool:raise ValueError('Choose valid view preferences.')
   from memory_controls import change,notes
   folder=str(s.root(body.get('scope')));text='File explorer preference: '+json.dumps({'folder':folder,'sort':body['sort'],'view':body['view'],'descending':body['descending']},ensure_ascii=False)
   for old in notes(e,'windows'):
    if old['text'].startswith('File explorer preference: '):change(e,{'agent':'windows','action':'forget-note','id':old['id'],'approve':True})
   value=change(e,{'agent':'windows','action':'remember','text':text,'approve':True})
  elif action=='propose' and post:value=s.propose(body)
  elif action=='approve' and post:value=s.execute(body.get('id'),body.get('approve'))
  elif action=='category' and post:
   if body.get('category') not in CATEGORIES:raise ValueError('Choose a supported category.')
   p=s.path(body.get('scope'),body.get('path'));key=hashlib.sha256((str(s.root(body['scope']))+'\0'+relative_path(p,s.root(body['scope'])).as_posix()).encode()).hexdigest()
   with s.connect() as db:db.execute('INSERT OR REPLACE INTO categories VALUES(?,?)',(key,body['category']))
   value={'saved':True,'notice':'Refresh the listing/scan to apply the corrected category.'}
  elif action=='preview' and not post:
   sid=q.get('scope',[''])[0];p=s.path(sid,q.get('path',[''])[0]);suffix=p.suffix.lower()
   if not p.is_file():raise ValueError('Choose a file to preview.')
   if suffix in TEXT:
    with p.open('rb') as file:data=file.read(256000)
    handler.json(200,{'kind':'text','text':data.decode('utf8',errors='replace'),'truncated':p.stat().st_size>256000});return True
   if suffix in {'.png','.jpg','.jpeg','.webp','.bmp','.tif','.tiff','.gif'}:
    from PIL import Image,ImageOps
    import io
    with Image.open(p) as image:
     if image.width*image.height>40_000_000:raise ValueError('Image is too large to preview safely.')
     image=ImageOps.exif_transpose(image);image.thumbnail((1400,1000));out=io.BytesIO();image.convert('RGB').save(out,'JPEG',quality=88);data=out.getvalue()
    handler.send_response(200);handler.send_header('Content-Type','image/jpeg');handler.send_header('Content-Length',str(len(data)));handler.send_header('Cache-Control','no-store');handler.end_headers();handler.wfile.write(data);return True
   preview_job=q.get('previewJob',[''])[0]
   if preview_job:
    j=s.state(preview_job)
    if j['scope']!=sid or j['path']!=q.get('path',[''])[0] or j['status']!='COMPLETED' or j['operation']!='prepare video preview' or stamp(p)!=j['results'][0]['sourceSnapshot']:raise ValueError('Video preview scope expired or source changed.')
    p=s.home/'VideoPreviews'/(j['id']+'.webm');suffix='.webm'
   if suffix not in {'.pdf','.mp4','.webm','.mov','.mkv','.avi','.mp3','.wav'}:raise ValueError('Inline preview is not supported for this format. Use Properties or approved Open.')
   if suffix=='.pdf':
    page=q.get('page',[None])[0]
    if page is None:handler.json(200,pdf_preview(p));return True
    data=pdf_preview(p,int(page));handler.send_response(200);handler.send_header('Content-Type','image/png');handler.send_header('Content-Length',str(len(data)));handler.send_header('Cache-Control','no-store');handler.end_headers();handler.wfile.write(data);return True
   size=p.stat().st_size;start=0;end=size-1;status=200;header=handler.headers.get('Range')
   if suffix=='.pdf':
    with p.open('rb') as file:
     if file.read(5)!=b'%PDF-':raise ValueError('This file does not have a PDF signature.')
   if header:
    match=re.fullmatch(r'bytes=(\d+)-(\d*)',header)
    if not match:raise ValueError('Unsupported byte range.')
    start=int(match[1]);end=min(size-1,int(match[2]) if match[2] else size-1);status=206
    if not 0<=start<=end<size:raise ValueError('Invalid byte range.')
   handler.send_response(status);handler.send_header('Content-Type',mimetypes.guess_type(str(p))[0] or 'application/octet-stream');handler.send_header('Content-Length',str(end-start+1));handler.send_header('Accept-Ranges','bytes');handler.send_header('Content-Disposition','inline');handler.send_header('Cache-Control','no-store');handler.send_header('X-Content-Type-Options','nosniff')
   if status==206:handler.send_header('Content-Range',f'bytes {start}-{end}/{size}')
   handler.end_headers()
   with p.open('rb') as file:
    file.seek(start);remaining=end-start+1
    while remaining:
     if sid not in s.roots or e.closed:break
     data=file.read(min(1024*1024,remaining))
     if not data:break
     handler.wfile.write(data);remaining-=len(data)
   return True
  else:raise ValueError('Unsupported explorer request.')
  handler.json(200,value)
 except (BrokenPipeError,ConnectionResetError):return True
 except (ValueError,KeyError,TypeError,OSError,sqlite3.Error) as error:handler.json(400,{'error':redact(str(error))})
 return True
