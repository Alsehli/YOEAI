"""Isolated core regression runner: no live generation, installer execution or user-profile writes."""
import os,sys,unittest,json,tempfile,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
profile=Path('../System-Audit/Profile').resolve();profile.mkdir(parents=True,exist_ok=True);os.environ['LOCALAPPDATA']=str(profile)
sys.path.insert(0,str(Path('../System-Audit/Dependencies').resolve()))
from tests_search.regressions import Capture
names=['test_first_launch','test_resources','test_native_migration','test_security','test_downloads','test_release_readiness','test_native_setup','installer.test_releases']
suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in names)
result=unittest.TextTestRunner(verbosity=1,resultclass=Capture).run(suite)
out=Path('docs/system-audit');out.mkdir(parents=True,exist_ok=True);(out/'core-final.json').write_text(json.dumps(result.rows,indent=2),encoding='utf8')
print(json.dumps({'executed':result.testsRun,'failed':len(result.failures)+len(result.errors)}),flush=True)
# Shut down only managers created inside this isolated test process.
import lite_agents_bridge
lite_agents_bridge.shutdown()
sys.exit(not result.wasSuccessful())
