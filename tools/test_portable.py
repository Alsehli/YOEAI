"""Small Windows CI subset. Full GPU/installed-tool qualification is separate."""
import os,sys,tempfile,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(R/'source'));sys.path.insert(0,str(R/'tests'))
MODULES=['test_interactive_voice','test_chat_reliability','test_memory_index','test_maximum_memory','test_language_understanding']
with tempfile.TemporaryDirectory(prefix='yoeai-ci-') as profile:
 os.environ['LOCALAPPDATA']=profile
 suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(n) for n in MODULES)
 result=unittest.TextTestRunner(verbosity=2).run(suite)
 sys.exit(0 if result.wasSuccessful() else 1)
