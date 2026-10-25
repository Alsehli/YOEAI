import unittest,time,json
from windows_spelling import check,languages
class InstantSpelling(unittest.TestCase):
 def test_english_arabic_and_suggestions(self):
  result=check('There is an eror. هاذا كتاب.');self.assertIn('en-US',result['languages']);self.assertIn('ar-SA',result['languages']);edits={x['original']:x for x in result['edits']};self.assertIn('error',edits['eror']['suggestions']);self.assertIn('هذا',edits['هاذا']['suggestions'])
 def test_repeated_words_and_utf16_offsets(self):
  text='😀 eror eror';edits=check(text)['edits'];self.assertEqual([x['start'] for x in edits if x['original']=='eror'],[3,8]);raw=text.encode('utf-16-le')
  for x in edits:self.assertEqual(raw[x['start']*2:x['end']*2].decode('utf-16-le'),x['original'])
 def test_literals_and_brand_are_not_spellchecked(self):
  result=check('YOEAI https://example.com/eror eror.py `eror` me@eror.com C:\\Tests\\eror.py');self.assertEqual(result['edits'],[]);self.assertEqual(check('```eror```')['edits'],[])
 def test_input_bounds(self):self.assertRaises(ValueError,check,'x'*8001);self.assertRaises(ValueError,check,None)
if __name__=='__main__':unittest.main()
