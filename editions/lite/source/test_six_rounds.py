"""Repeat the existing live functional suite without replacing prior evidence."""
import json, os, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).parents[2]
OUT = ROOT / 'lite-development' / ('six-rounds-' + time.strftime('%Y%m%d-%H%M%S'))
OUT.mkdir(parents=True)
os.environ['ALSEHLI_LITE_TEST_UI_PORT'] = '8090'
namespace = {'__file__': str(Path(__file__).with_name('test_lite.py'))}
source = Path(namespace['__file__']).read_text(encoding='utf8')
exec(compile(source.split('for name,fn in [(\'English\'')[0], namespace['__file__'], 'exec'), namespace)
original_path = Path('C:/AI/llama.cpp/server-state.json')
before = original_path.read_bytes()
namespace['OUT'] = OUT
all_rounds = []
for number in range(1, 7):
    namespace['results'] = []
    started = time.perf_counter()
    print(f'ROUND {number}/6', flush=True)
    for name in ['english', 'arabic', 'vision', 'security', 'stability']:
        namespace['run'](name, namespace[name])
    def streaming():
        result = namespace['call']('Reply with exactly STREAM_OK', stream=True)
        assert 'STREAM_OK' in result['text'], result
        assert result['firstTokenSeconds'] is not None
        return result
    namespace['run']('streaming', streaming)
    status = json.load(namespace['HTTP'].open('http://127.0.0.1:8090/status', timeout=10))
    unchanged = original_path.read_bytes() == before
    results = namespace['results']
    record = dict(round=number, elapsedSeconds=time.perf_counter()-started,
                  status='PASS' if all(r['status']=='PASS' for r in results) and unchanged else 'FAIL',
                  tests=results, gpuStatus=status, originalStateUnchanged=unchanged)
    all_rounds.append(record)
    (OUT/'six-round-results.json').write_text(json.dumps(all_rounds, ensure_ascii=False, indent=2), encoding='utf8')
    print(f"ROUND {number}: {record['status']} ({record['elapsedSeconds']:.1f}s)", flush=True)
print('EVIDENCE:', OUT, flush=True)
raise SystemExit(0 if all(r['status']=='PASS' for r in all_rounds) else 1)
