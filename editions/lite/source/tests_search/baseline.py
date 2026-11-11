import types,subprocess,sys,importlib.util
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
old=types.ModuleType('intelligence.baseline');old.__package__='intelligence';exec(subprocess.check_output(['git','show','checkpoint/search-audit-20261111:intelligence/automatic_web.py'],text=True,encoding='utf8'),old.__dict__)
spec=importlib.util.spec_from_file_location('scenario_harness','tests_search/run_scenarios.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.Research=old.Research
sys.argv=['run_scenarios.py','--output','docs/search-results/baseline-corrected'];sys.exit(module.main())
