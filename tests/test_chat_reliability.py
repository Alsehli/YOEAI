import json,subprocess,unittest
from pathlib import Path
class ChatReliability(unittest.TestCase):
 def test_stream_framing_and_local_history_recovery(self):
  base=Path(__file__).resolve().parent.parent
  p=subprocess.run([r'C:\Program Files\nodejs\node.exe',str(base/'tests/chat_reliability.cjs'),str(base/'Source/assets/chat-reliability.js')],capture_output=True,text=True,encoding='utf8',timeout=15)
  self.assertEqual(p.returncode,0,p.stdout+p.stderr)
  results=json.loads(p.stdout);self.assertEqual(len(results),20);self.assertTrue(all(t['passed'] for t in results))
if __name__=='__main__':unittest.main()
