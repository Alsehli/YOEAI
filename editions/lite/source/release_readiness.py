"""Read-only offline payload audit. File presence is not functional qualification."""
import argparse
import json
from pathlib import Path

MODEL = 'DeepSeek-V4-Pro-Qwen3.5-9B-MTP-Q4_K_M.gguf'


def audit(root):
    root = Path(root).resolve()
    checks = {}

    def files(name, paths):
        missing = [str(p) for p in paths if not (root / p).is_file() or not (root / p).stat().st_size]
        checks[name] = {'assetsPresent': not missing, 'missing': missing, 'functionallyVerified': False}

    def configured(name, relative, keys):
        config = root / relative
        try:
            value = json.loads(config.read_text(encoding='utf-8-sig'))
            paths = []
            for key in keys:
                raw = value.get(key)
                if not isinstance(raw, str) or not raw.strip():
                    raise ValueError('Missing configuration key: ' + key)
                path = Path(raw)
                if path.is_absolute():
                    raise ValueError('Offline payload contains a machine-specific path: ' + key)
                target = (config.parent / path).resolve()
                if not target.is_relative_to(root):
                    raise ValueError('Offline component escapes payload: ' + key)
                paths.append(target.relative_to(root))
            files(name, paths)
        except (OSError, ValueError, TypeError) as error:
            checks[name] = {'assetsPresent': False, 'error': str(error), 'functionallyVerified': False}

    files('text', [f'Models/{MODEL}', 'NativeRuntime/b11784/llama.dll', 'NativeEngine/YOEAI-Inference.exe'])
    configured('image', 'ImageGeneration/config.json', ('executable', 'diffusion', 'encoder', 'vae'))
    configured('video', 'VideoGeneration/config.json', ('python', 'worker', 'ffmpeg', 'license'))
    checks['video'].update(model='Kandinsky 6.0 Lite Distill', preparationOnly=True, inferenceRun=False)
    files('videoWeights', ['VideoGeneration/Kandinsky/model-assets.json', 'VideoGeneration/Kandinsky/Models/transformer/diffusion_pytorch_model.safetensors', 'VideoGeneration/Kandinsky/Models/audio_vae/diffusion_pytorch_model.safetensors', 'VideoGeneration/Kandinsky/Models/vocoder/diffusion_pytorch_model.safetensors'])
    files('speechSynthesis', ['Speech/Runtime/YOEAI-Speech.exe', 'Speech/Models/kokoro-v1.0.onnx', 'Speech/Models/voices-v1.0.bin', 'Speech/eSpeak/libespeak-ng.dll', 'Speech/eSpeak/espeak-ng-data/phontab'])
    files('speechRecognition', ['SpeechInput/Runtime/Release/whisper-cli.exe', 'SpeechInput/Models/ggml-tiny.bin', 'SpeechInput/Licenses/whisper.cpp-MIT.txt', 'SpeechInput/Licenses/Whisper-MIT.txt'])
    checks['speechRecognition']['implemented'] = True
    files('research', ['SearchRuntime/Python/python.exe', 'Settings/search.yml', 'Vendor/searxng-ai-kit/pyproject.toml'])
    files('semanticRetrieval', ['Models/multilingual-minilm/asset-manifest.json'])
    files('sandbox', ['SandboxRuntime/runtime-manifest.json'])
    checks['sandbox']['note'] = 'AppContainer must qualify separately on the installed machine.'
    return {'root': str(root), 'checks': checks, 'allRequiredAssetsPresent': all(c['assetsPresent'] for c in checks.values()), 'offlineReleaseReady': False, 'limitations': ['Asset presence does not verify inference, licenses, clean-PC installation, upgrades or uninstallation.', 'Complete offline release requires end-to-end qualification of every bundled capability.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('payload', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = audit(args.payload)
    encoded = json.dumps(result, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding='utf8')
    print(encoded)
    raise SystemExit(0 if result['offlineReleaseReady'] else 1)
