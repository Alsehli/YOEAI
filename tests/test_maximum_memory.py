import unittest
from agent_memory import fit_recall,memory_text,RECALL_TASKS
from memory_controls import refresh,change
from unittest.mock import Mock,patch
class MaximumRecall(unittest.TestCase):
 def test_no_old_8192_cap(self):
  rows=[dict(id='old',objective='Remember the larger report',result='A'*9000)]
  result=fit_recall(rows,len,11000)
  self.assertEqual(result[0]['result'],rows[0]['result']);self.assertGreater(len(memory_text(result)),8192)
 def test_current_context_budget_is_never_exceeded(self):
  rows=[dict(id=str(n),objective='old task',result='B'*15000) for n in range(100)]
  for budget in [0,512,2048,8192,12000]:self.assertLessEqual(len(memory_text(fit_recall(rows,len,budget))),budget)
 def test_normal_refresh_considers_100_lite_stays_4(self):
  self.assertEqual(RECALL_TASKS,100);e=Mock();e.memory.return_value={'preferences':''};t={'agent':'research'}
  with patch('memory_controls.notes',return_value=[]),patch('memory_controls.rows',return_value=[]) as rows:
   refresh(e,t);rows.assert_called_with(e,t,100);refresh(e,t,lite=True);rows.assert_called_with(e,t,4)
