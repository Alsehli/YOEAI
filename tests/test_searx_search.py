import sys,unittest,json,urllib.error
from unittest.mock import patch
sys.path[:0]=['F:/YOEAI-Autonomy/Source','F:/YOEAI-2.0/Web-Search/Dependencies']
import searx_search as s
import web_search as w
class Tests(unittest.TestCase):
 def test_freshness(self):
  self.assertEqual(s.options('latest local AI models')['time_range'],'month');self.assertEqual(s.options('news today')['time_range'],'day');self.assertEqual(s.options('latest news in 2020')['time_range'],'');self.assertEqual(s.options('Bahrain history')['time_range'],'')
 def test_arabic(self):
  self.assertEqual(s.options('أحدث أخبار البحرين اليوم')['language'],'ar');self.assertEqual(s.options('أحدث أخبار البحرين اليوم')['time_range'],'day')
 def test_relevance_and_dedup(self):
  rows=[{'title':'Cat food','url':'https://a.com','content':'cats'}, {'title':'llama.cpp releases','url':'https://github.com/a','content':'Latest llama.cpp release'}, {'title':'llama.cpp releases','url':'https://github.com/a#test','content':'release'}]
  r=s.rank(rows,'latest llama.cpp releases');self.assertEqual(len(r),1);self.assertEqual(r[0]['url'],'https://github.com/a')
 def test_bad_urls(self):
  self.assertFalse(s.rank([{'title':'test','url':'http://127.0.0.1','content':'test'}, {'title':'test','url':'javascript:alert(1)'},None],'test'))
 def test_dates(self):
  r=s.rank([{'title':'test','url':'https://example.com','publishedDate':'2099-01-01'},{'title':'test old','url':'https://example.org','publishedDate':'2020-01-01T00:00:00Z'}],'test');self.assertIsNone(r[0]['date']);self.assertEqual(r[1]['date'],'2020-01-01T00:00:00Z')
 def test_source_diversity(self):
  self.assertEqual(len(s.rank([{'title':'topic','url':'https://same.org/'+str(i)} for i in range(10)],'topic')),2)
 def test_engine_failure_not_fabricated(self):
  with patch.object(s,'ensure'),patch.object(s,'get',return_value={'results':[]}):
   with self.assertRaisesRegex(RuntimeError,'No relevant'):s.search('a topic')
 def test_undated_release_resource(self):
  first={'results':[{'title':'Project release blog','url':'https://blog.example.org','content':'llama.cpp release'}]}
  second={'results':[{'title':'Releases llama.cpp','url':'https://github.com/ggml-org/llama.cpp/releases','content':'llama.cpp releases'}]}
  with patch.object(s,'ensure'),patch.object(s,'get',side_effect=[first,second]) as fetch:
   r=s.search('latest llama.cpp release');self.assertTrue(r['broadenedSearch']);self.assertIn('github.com',r['results'][0]['url']);self.assertEqual(fetch.call_count,2);self.assertNotIn('time_range=',fetch.call_args.args[0])
 def test_arabic_subject_not_generic_words(self):
  rows=[{'title':'أخبار العالم اليوم','url':'https://unrelated.org','content':'أخبار عامة اليوم'}, {'title':'أخبار البحرين','url':'https://bahrain.example.org','content':'البحرين اليوم'}]
  r=s.rank(rows,'أحدث أخبار البحرين اليوم');self.assertEqual(len(r),1);self.assertIn('bahrain.example.org',r[0]['url'])
 def test_no_silent_fallback(self):
  w.CACHE.clear()
  with patch.object(s,'search',side_effect=RuntimeError('offline')):
   with self.assertRaisesRegex(RuntimeError,'offline'):w.search('test missing provider')
if __name__=='__main__':unittest.main()
