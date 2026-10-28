import unittest
from unittest.mock import patch,Mock
import mini_agents as m
class Priority(unittest.TestCase):
 def test_foreground_preempts_background_only(self):
  engine=Mock();engine.running_id='background';engine.get.return_value={'backgroundReview':True,'id':'background'};engine.cancel.side_effect=lambda tid:m.GATE.release();handler=Mock();handler.path='/v1/chat/completions';m.GATE.acquire()
  try:
   with patch.object(m,'INSTANCE',engine),m.shared_request(handler) as acquired:self.assertTrue(acquired)
   engine.cancel.assert_called_once_with('background');self.assertFalse(m.GATE.locked())
  finally:
   if m.GATE.locked():m.GATE.release()
 def test_foreground_does_not_cancel_interactive_agent(self):
  engine=Mock();engine.running_id='code';engine.get.return_value={'backgroundReview':False,'id':'code'};handler=Mock();handler.path='/v1/chat/completions';m.GATE.acquire()
  try:
   with patch.object(m,'INSTANCE',engine),m.shared_request(handler) as acquired:self.assertFalse(acquired)
   engine.cancel.assert_not_called()
  finally:m.GATE.release()
