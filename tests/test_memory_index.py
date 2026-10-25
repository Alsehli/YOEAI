import contextlib,sqlite3,tempfile,threading,unittest,json,time
from pathlib import Path
import memory_controls as m
import memory_index as ix

class Engine:
 def __init__(self,path):
  self.db=Path(path);self.db_lock=threading.RLock()
  with self.connect() as db:
   db.executescript('CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,agent TEXT,data TEXT);CREATE TABLE IF NOT EXISTS memory(agent TEXT PRIMARY KEY,data TEXT);')
 @contextlib.contextmanager
 def connect(self):
  db=sqlite3.connect(self.db)
  try:
   with db:yield db
  finally:db.close()
 def memory(self,a):return {'preferences':'','maxTokens':1024,'recallEnabled':True}
 def get(self,i):
  with self.connect() as db:return json.loads(db.execute('SELECT data FROM tasks WHERE id=?',(i,)).fetchone()[0])
 def save(self,i,objective,result='Useful answer',agent='research',project=None,status='COMPLETED'):
  t=dict(id=i,agent=agent,objective=objective,result=result,project=project,status=status)
  with self.connect() as db:db.execute('INSERT OR REPLACE INTO tasks VALUES(?,?,?)',(i,agent,json.dumps(t)))

class MemoryIndexTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.e=Engine(Path(self.tmp.name)/'a.db');self.t=dict(id='current',agent='research',objective='Python performance',project=None)
 def tearDown(self):self.tmp.cleanup()
 def test_backfill_existing_history_and_backup(self):
  self.e.save('a','Python performance');self.assertEqual(m.rows(self.e,self.t)[0]['id'],'a');self.assertTrue(Path(str(self.e.db)+'.before-memory-fts5').is_file());self.assertEqual(self.e.get('a')['result'],'Useful answer')
 def test_matches_over_recent_noise(self):
  self.e.save('old','Python performance');[self.e.save(str(i),'Shopping bananas') for i in range(110)]
  self.assertEqual([r['id'] for r in m.rows(self.e,self.t)],['old'])
 def test_completed_insert_update_and_delete(self):
  m.setup(self.e);ix.ensure(self.e);self.e.save('a','Python performance',status='RUNNING');self.assertEqual(m.rows(self.e,self.t),[])
  self.e.save('a','Python performance');self.assertEqual(len(m.rows(self.e,self.t)),1)
  self.e.save('a','Shopping');self.assertEqual(m.rows(self.e,self.t),[])
  self.e.save('a','Python');self.assertEqual(len(m.rows(self.e,self.t)),1)
  with self.e.connect() as db:db.execute("DELETE FROM tasks WHERE id='a'")
  self.assertEqual(m.rows(self.e,self.t),[])
 def test_forget_removes_index_keeps_history(self):
  self.e.save('a','Python');m.rows(self.e,self.t);m.change(self.e,{'agent':'research','action':'forget-task','id':'a','approve':True});self.assertEqual(m.rows(self.e,self.t),[]);self.assertEqual(self.e.get('a')['objective'],'Python')
  self.e.save('a','Python');self.assertEqual(m.rows(self.e,self.t),[])
 def test_agent_and_project_namespaces(self):
  self.e.save('a','Python',agent='code',project='A');self.e.save('b','Python',agent='code',project='B');self.e.save('r','Python')
  self.assertEqual([r['id'] for r in m.rows(self.e,dict(self.t,agent='code',project='A'))],['a'])
  self.assertEqual([r['id'] for r in m.rows(self.e,self.t)],['r'])
 def test_arabic_and_mixed_language(self):
  self.e.save('a','تحسين ذاكرة Python','تقرير مفيد');self.assertEqual(m.rows(self.e,dict(self.t,objective='ذاكرة'))[0]['id'],'a')
 def test_fts_syntax_is_not_executed(self):
  self.e.save('a','Python');self.assertEqual(m.rows(self.e,dict(self.t,objective='" OR * NEAR( ] - Python'))[0]['id'],'a')
 def test_compact_cap_and_followup(self):
  for i in range(12):self.e.save(str(i),'Python performance','X'*12000)
  rows=m.rows(self.e,self.t,100);self.assertEqual(len(rows),8);self.assertTrue(all(len(r['result'])<=1500 for r in rows))
  self.assertEqual(len(m.rows(self.e,dict(self.t,objective='continue'))),2)
 def test_restart_does_not_duplicate_and_disable_preserved(self):
  self.e.save('a','Python');m.rows(self.e,self.t);other=Engine(self.e.db);self.assertEqual(len(m.rows(other,self.t)),1)
  other.memory=lambda a:{'recallEnabled':False};self.assertEqual(m.rows(other,self.t),[])
