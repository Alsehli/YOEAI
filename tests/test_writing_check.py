import unittest
from writing_check import validate
class Proofreading(unittest.TestCase):
 def test_exact_minimal_changes(self):
  self.assertEqual(len(validate('I has a apple.',[{'original':'I has','replacement':'I have','reason':'Agreement'},{'original':'a apple','replacement':'an apple','reason':'Article'}])),2)
 def test_ambiguous_and_overlapping(self):
  self.assertEqual(validate('bad bad',[{'original':'bad','replacement':'good','reason':'test'}]),[])
  self.assertEqual(len(validate('I has',[{'original':'I has','replacement':'I have','reason':'test'},{'original':'has','replacement':'have','reason':'test'}])),1)
 def test_protected_literals(self):
  for text,old,new in [('123.pdf','123.pdf','124.pdf'),('at 10:30','10:30','11:30'),('open my.py','my','new')]:self.assertEqual(validate(text,[{'original':old,'replacement':new,'reason':'test'}]),[])
 def test_untrusted_text_and_noop(self):
  self.assertEqual(validate('<script>alert(1)</script>',[{'original':'missing','replacement':'x','reason':'test'}]),[])
  self.assertEqual(validate('Fine.',[{'original':'Fine','replacement':'Fine','reason':'test'}]),[])
if __name__=='__main__':unittest.main()
