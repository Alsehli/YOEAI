"""Local FTS5 recall. Extractive summaries, no embeddings, inference or authority."""
import re,sqlite3
from pathlib import Path

LIMIT=8
SUMMARY_CHARS=1500
STOP=set('the and that this with from have your about please what when where how can could would should you are for into then than just continue it is to of in on a an my me we do be as at or'.split())
STOP.update('من في على إلى هذا هذه انا أنا هل ما هو هي عن مع ان أن ثم و'.split())

def ensure(e):
 if hasattr(e,'_memory_fts_ready'):return e._memory_fts_ready
 with e.db_lock:
  if hasattr(e,'_memory_fts_ready'):return e._memory_fts_ready
  try:
   with e.connect() as db:
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name='tasks'").fetchone():return False
    # Probe availability without altering history or the application's schema version.
    db.execute('CREATE VIRTUAL TABLE IF NOT EXISTS temp.memory_fts_probe USING fts5(text)')
    exists=db.execute("SELECT 1 FROM sqlite_master WHERE name='agent_task_fts'").fetchone()
    if not exists:
     path=Path(e.db);backup=path.with_name(path.name+'.before-memory-fts5')
     if not backup.exists():
      destination=sqlite3.connect(backup)
      try:db.backup(destination)
      finally:destination.close()
    db.executescript('''
CREATE VIRTUAL TABLE IF NOT EXISTS agent_task_fts USING fts5(task UNINDEXED,agent UNINDEXED,project UNINDEXED,objective,summary,tokenize='unicode61 remove_diacritics 2');
CREATE TRIGGER IF NOT EXISTS memory_fts_insert AFTER INSERT ON tasks
WHEN json_extract(new.data,'$.status')='COMPLETED' BEGIN
DELETE FROM agent_task_fts WHERE task=new.id;
INSERT INTO agent_task_fts SELECT new.id,new.agent,coalesce(json_extract(new.data,'$.project'),''),substr(json_extract(new.data,'$.objective'),1,1000),substr(coalesce(json_extract(new.data,'$.result'),''),1,1500)
WHERE NOT EXISTS(SELECT 1 FROM agent_forgotten WHERE agent=new.agent AND task=new.id); END;
CREATE TRIGGER IF NOT EXISTS memory_fts_update AFTER UPDATE ON tasks
WHEN json_extract(old.data,'$.status')='COMPLETED' OR json_extract(new.data,'$.status')='COMPLETED' BEGIN
DELETE FROM agent_task_fts WHERE task=new.id;
INSERT INTO agent_task_fts SELECT new.id,new.agent,coalesce(json_extract(new.data,'$.project'),''),substr(json_extract(new.data,'$.objective'),1,1000),substr(coalesce(json_extract(new.data,'$.result'),''),1,1500)
WHERE json_extract(new.data,'$.status')='COMPLETED' AND NOT EXISTS(SELECT 1 FROM agent_forgotten WHERE agent=new.agent AND task=new.id); END;
CREATE TRIGGER IF NOT EXISTS memory_fts_delete AFTER DELETE ON tasks BEGIN DELETE FROM agent_task_fts WHERE task=old.id; END;
CREATE TRIGGER IF NOT EXISTS memory_fts_forget AFTER INSERT ON agent_forgotten BEGIN DELETE FROM agent_task_fts WHERE task=new.task AND agent=new.agent; END;
''')
    if not exists:
     db.execute('''INSERT INTO agent_task_fts SELECT id,agent,coalesce(json_extract(data,'$.project'),''),substr(json_extract(data,'$.objective'),1,1000),substr(coalesce(json_extract(data,'$.result'),''),1,1500) FROM tasks
WHERE json_extract(data,'$.status')='COMPLETED' AND NOT EXISTS(SELECT 1 FROM agent_forgotten f WHERE f.agent=tasks.agent AND f.task=tasks.id)''')
   e._memory_fts_ready=True;e._memory_fts_error=''
  except sqlite3.Error as error:
   e._memory_fts_ready=False;e._memory_fts_error=str(error)[:200]
 return e._memory_fts_ready

def terms(value):
 return list(dict.fromkeys(t for t in re.findall(r'[^\W_]{2,}',str(value).casefold(),re.UNICODE) if t not in STOP))[:12]

def query(e,t,limit=LIMIT):
 if not ensure(e):return None
 limit=max(1,min(LIMIT,int(limit)));tokens=terms(t['objective']);condition='agent=? AND task!=?';args=[t['agent'],t['id']]
 if t['agent'] in {'code','update','reverse','game'}:
  condition+=' AND project=?';args.append(t.get('project') or '')
 condition+=' AND NOT EXISTS(SELECT 1 FROM agent_forgotten f WHERE f.task=agent_task_fts.task AND f.agent=agent_task_fts.agent)'
 with e.connect() as db:
  if tokens:
   expression=' OR '.join('"'+token+'"' for token in tokens)
   found=db.execute('SELECT task,objective,summary FROM agent_task_fts WHERE agent_task_fts MATCH ? AND '+condition+' ORDER BY bm25(agent_task_fts,0,0,0,3,1) LIMIT ?',[expression,*args,limit]).fetchall()
  else:
   # Short follow-ups have no search terms: only the two most recent scoped tasks.
   found=db.execute('SELECT task,objective,summary FROM agent_task_fts WHERE '+condition+' ORDER BY rowid DESC LIMIT ?',[*args,min(2,limit)]).fetchall()
 return [{'id':r[0],'objective':r[1],'result':re.sub(r'\s+',' ',r[2]).strip()[:SUMMARY_CHARS],'summaryKind':'extractive excerpt; open task history for full result'} for r in found if r[2]]
