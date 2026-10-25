import unittest,tempfile,sqlite3,threading,contextlib,json
from pathlib import Path
import memory_controls as m
from unittest.mock import patch

class Engine:
 def __init__(self,path):
  self.db=path;self.db_lock=threading.RLock();self.data=[]
  with self.connect() as db:db.execute('CREATE TABLE IF NOT EXISTS memory(agent TEXT PRIMARY KEY,data TEXT NOT NULL)')
 @contextlib.contextmanager
 def connect(self):
  db=sqlite3.connect(self.db)
  try:
   with db:yield db
  finally:db.close()
 def memory(self,a):
  if a not in ['research','code','windows']:raise ValueError('agent')
  with self.connect() as db:r=db.execute('SELECT data FROM memory WHERE agent=?',(a,)).fetchone()
  return json.loads(r[0]) if r else {'preferences':'','maxTokens':768,'recallEnabled':True}
 def tasks(self):return self.data
 def get(self,i):return next(t for t in self.data if t['id']==i)

class MemoryTests(unittest.TestCase):
 def setUp(self):
  self.history_patch=patch.object(m,'history',lambda e,a:[t for t in e.data if t['agent']==a and t['status']=='COMPLETED']);self.history_patch.start()
  self.tmp=tempfile.TemporaryDirectory();self.e=Engine(str(Path(self.tmp.name)/'test.db'))
  self.t={'id':'current','agent':'research','objective':'Python report','project':None}
  self.e.data=[{'id':'unrelated','agent':'research','objective':'Shopping list','status':'COMPLETED','result':'Bananas'}, {'id':'related','agent':'research','objective':'Python report','status':'COMPLETED','result':'Python details'}, {'id':'other','agent':'code','objective':'Python report','status':'COMPLETED','result':'private code'}]
 def tearDown(self):self.history_patch.stop();self.tmp.cleanup()
 def test_scope_and_relevance(self):self.assertEqual([x['id'] for x in m.rows(self.e,self.t)],['related','unrelated'])
 def test_preference_persistence_and_forget(self):
  m.change(self.e,{'agent':'research','action':'remember','text':'Keep it short','approve':True});other=Engine(self.e.db);self.assertEqual(m.notes(other,'research')[0]['text'],'Keep it short');self.assertEqual(m.notes(other,'code'),[])
  note=m.notes(other,'research')[0];m.change(other,{'agent':'code','action':'forget-note','id':note['id'],'approve':True});self.assertEqual(len(m.notes(other,'research')),1)
  m.change(other,{'agent':'research','action':'forget-note','id':note['id'],'approve':True});self.assertEqual(m.notes(other,'research'),[])
 def test_forgotten_task_excluded_preserves_history(self):
  m.change(self.e,{'agent':'research','action':'forget-task','id':'related','approve':True});self.assertNotIn('related',[r['id'] for r in m.rows(self.e,self.t)]);self.assertEqual(self.e.get('related')['result'],'Python details')
  self.assertRaises(ValueError,m.change,self.e,{'agent':'code','action':'forget-task','id':'related','approve':True})
 def test_refresh_prevents_stale_snapshot(self):
  self.t['memory']={'preferences':'stale'};self.t['recall']=[{'id':'related'}];m.change(self.e,{'agent':'research','action':'forget-task','id':'related','approve':True});m.refresh(self.e,self.t);self.assertEqual(self.t['memory']['preferences'],'');self.assertNotIn('related',[x['id'] for x in self.t['recall']])
 def test_secrets_approval_and_budget(self):
  for text in ['password=secret','api_key=secret','sk-private']:
   self.assertRaises(ValueError,m.change,self.e,{'agent':'research','action':'remember','text':text,'approve':True})
  self.assertRaises(ValueError,m.change,self.e,{'agent':'research','action':'remember','text':'short'})
  result=m.fit(m.rows(self.e,self.t),len,500);self.assertLessEqual(len(m.text(result)),500)
 def test_project_separation(self):
  self.t.update(agent='code',project='projectA');self.e.data[2]['project']='projectB';self.assertEqual(m.rows(self.e,self.t),[])
