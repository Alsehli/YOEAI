"""Keep candidate processes, child workers, profiles and UI ports separate."""
import json
import os
import re
from pathlib import Path


def configure(root):
    root = Path(root).resolve()
    meta = json.loads((root / 'source-candidate.json').read_text(encoding='utf8'))
    edition, version = meta['edition'], meta['version']
    if edition not in ('Lite', 'Normal') or not re.fullmatch(r'candidate-[A-Za-z0-9][A-Za-z0-9._-]{0,79}', version):
        raise ValueError('Invalid source candidate identity.')
    original = os.environ.setdefault('YOEAI_SOURCE_ORIGINAL_APPDATA', os.environ['LOCALAPPDATA'])
    isolated = Path(original) / 'YOEAI-SourceCandidateData' / edition / version
    os.environ['LOCALAPPDATA'] = str(isolated)
    home = isolated / ('YOEAILite' if edition == 'Lite' else 'AlsehliAI-Preview')
    home.mkdir(parents=True, exist_ok=True)
    profile = home / ('profile.json' if edition == 'Lite' else 'config.json')
    bits = 'Q4_K_M' if edition == 'Lite' else 'Q6_K'
    value = {'model': str(root / ('Models/DeepSeek-V4-Pro-Qwen3.5-9B-MTP-' + bits + '.gguf')),
             'projector': str(root / 'Models/mmproj-F32.gguf'), 'context': 8192,
             'apiPort': 19236 if edition == 'Lite' else 19246,
             'uiPort': 19237 if edition == 'Lite' else 19247,
             'loadOnDemand': True, 'inferenceEngine': 'native', 'externalBackend': False, 'gpuLayers': 99}
    try:
        with profile.open('x', encoding='utf8') as stream:
            json.dump(value, stream, indent=2)
    except FileExistsError:
        pass
    return home
