"""Assemble untested release artifacts only. Never launch app, installer or inference."""
import argparse
import hashlib
import json
import os
import shutil
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

IMMUTABLE_WEIGHTS = {'.safetensors', '.gguf', '.onnx', '.bin', '.ckpt'}


def extended(path):
    path = Path(path).resolve()
    text = str(path)
    if os.name == 'nt' and not text.startswith('\\\\?\\'):
        return Path('\\\\?\\UNC\\' + text[2:] if text.startswith('\\\\') else '\\\\?\\' + text)
    return path


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def copy_file(source, destination):
    source, destination = extended(source), extended(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.suffix.lower() in IMMUTABLE_WEIGHTS:
        try:
            os.link(source, destination)
            return
        except OSError:
            pass
    shutil.copy2(source, destination)


def copy_tree(source, destination):
    shutil.copytree(extended(source), extended(destination), copy_function=copy_file, ignore=shutil.ignore_patterns('.git', '__pycache__', '*.pyc', '*.part', '.pytest_cache'))


def stage_video(workspace, payload):
    backend = workspace / 'VideoGeneration/Kandinsky'
    metadata = backend / 'model-assets.json'
    dependencies = backend / 'dependencies.json'
    if not metadata.is_file() or not dependencies.is_file():
        raise ValueError('Finish pinned model download and dependency installation before packaging.')
    target = payload / 'VideoGeneration/Kandinsky'
    for name in ('Models', 'Bin', 'Licenses', 'Source'):
        copy_tree(backend / name, target / name)
    python_name = 'cpython-3.13.18-windows-x86_64-none'
    copy_tree(backend / 'Python' / python_name, target / 'Python' / python_name)
    for name in ('model-assets.json', 'dependencies.json', 'requirements-lock.txt', 'source-provenance.json'):
        copy_file(backend / name, target / name)
    cfg = json.loads((workspace / 'VideoGeneration/config.json').read_text(encoding='utf8'))
    cfg.update(worker='../Source/kandinsky_worker.py', testingAuthorized=False, verified=False, preparedOnly=True)
    (payload / 'VideoGeneration/config.json').write_text(json.dumps(cfg, indent=2), encoding='utf8')


def archive_asset(payload, artifacts, name, kind, roots):
    target = artifacts / (name + '.zip'); expanded = 0
    with zipfile.ZipFile(target, 'w', allowZip64=True) as package:
        for root in roots:
            root = extended(root)
            paths = [root] if root.is_file() else sorted(root.rglob('*'))
            for path in paths:
                if not path.is_file():
                    continue
                relative = path.relative_to(extended(payload)).as_posix()
                if relative.startswith('VideoGeneration/Kandinsky/Models/'):
                    continue
                if relative.startswith('ImageGeneration/PH3/Models/'):
                    continue
                if relative == 'ObjectGeneration/TripoSR/Models/model.ckpt':
                    continue
                if name.startswith('yoeai-image-') and (relative.startswith('ImageGeneration/PH3/') or relative == 'ImageGeneration/ph3-config.json'):
                    continue
                expanded += path.stat().st_size
                compression = zipfile.ZIP_STORED if path.suffix.lower() in IMMUTABLE_WEIGHTS else zipfile.ZIP_DEFLATED
                package.write(path, relative, compress_type=compression, compresslevel=1 if compression == zipfile.ZIP_DEFLATED else None)
    return {'id': name, 'kind': kind, 'version': '3.0.0-preparation', 'format': 'zip', 'path': 'app', 'bytes': target.stat().st_size, 'sha256': sha256(target), 'unpackedBytes': expanded, 'url': 'https://downloads.yoeai.online/3.0/packages/' + target.name, 'offlinePath': target.relative_to(payload).as_posix(), 'published': False}


def stage_ph3(workspace, payload):
    backend = workspace / 'ImageGeneration/PH3'
    if not (backend / 'model-assets.json').is_file():
        raise ValueError('Finish verified P-H3 downloads before assembling this release.')
    copy_tree(backend, payload / 'ImageGeneration/PH3')
    cfg = json.loads((workspace / 'ImageGeneration/ph3-config.json').read_text())
    cfg.update(worker='../Source/ph3_worker.py', enabled=False)
    (payload / 'ImageGeneration/ph3-config.json').write_text(json.dumps(cfg, indent=2))


def ph3_assets(payload):
    assets = [archive_asset(payload, payload / 'Artifacts', 'yoeai-ph3-runtime-3.0-preparation', 'image', [payload / 'ImageGeneration/PH3', payload / 'ImageGeneration/ph3-config.json'])]
    models = json.loads((payload / 'ImageGeneration/PH3/model-assets.json').read_text())
    for index, model in enumerate(models['files']):
        path = 'ImageGeneration/PH3/Models/' + model['path']
        assets.append({'id': 'ph3-model-' + str(index), 'kind': 'image', 'version': models['revision'], 'format': 'file', 'path': 'app/' + path, 'bytes': model['bytes'], 'sha256': model['sha256'], 'url': model['url'], 'offlinePath': path, 'upstreamPublished': True})
    return assets


def stage_objects(workspace, payload):
    copy_tree(workspace / 'ObjectGeneration/TripoSR', payload / 'ObjectGeneration/TripoSR')
    cfg = json.loads((workspace / 'ObjectGeneration/config.json').read_text())
    cfg.update(enabled=False, worker='../Source/object_worker.py')
    (payload / 'ObjectGeneration/config.json').write_text(json.dumps(cfg, indent=2))


def object_assets(payload):
    assets = [archive_asset(payload, payload / 'Artifacts', 'yoeai-triposr-runtime-3.0-preparation', 'support', [payload / 'ObjectGeneration'])]
    models = json.loads((payload / 'ObjectGeneration/TripoSR/model-assets.json').read_text())
    model = next(item for item in models['files'] if item['path'] == 'model.ckpt')
    path = 'ObjectGeneration/TripoSR/Models/model.ckpt'
    assets.append({'id':'triposr-model', 'kind':'support', 'version':models['revision'], 'format':'file', 'path':'app/'+path, 'bytes':model['bytes'], 'sha256':model['sha256'], 'url':model['url'], 'offlinePath':path, 'upstreamPublished':True})
    return assets


def prepare(workspace, output, base_payload):
    workspace, output, base_payload = Path(workspace).resolve(), Path(output).resolve(), Path(base_payload).resolve()
    source = workspace / 'Lite/Source'
    app = workspace / 'Lite/Candidate-App/YOEAILite'
    backend = workspace / 'VideoGeneration/Kandinsky'
    requirements = [app / 'YOEAILite.exe', backend / 'model-assets.json', backend / 'dependencies.json', workspace / 'Preparation-Installers/YOEAI-3.0-Offline-Preparation.exe', workspace / 'Preparation-Installers/YOEAI-3.0-Online-Preparation.exe']
    for required in requirements:
        if not required.is_file():
            raise ValueError('Preparation input missing: ' + str(required))
    if output.exists():
        raise ValueError('Use a new preparation output directory. Existing releases are never overwritten.')
    output.mkdir(parents=True); payload = output / 'Payload'; payload.mkdir()
    status = {'product': 'YOEAI', 'version': '3.0.0-preparation', 'backend': 'Kandinsky 6.0 Lite Distill', 'preparedOnly': True, 'verified': False, 'testsRun': False, 'inferenceRun': False, 'applicationStarted': False, 'installerExecuted': False, 'productionDownloadsEnabled': False, 'buildPurpose': 'packaging only', 'completed': False}
    (output / 'preparation.json').write_text(json.dumps(status, indent=2), encoding='utf8')
    for folder in ('Models', 'ImageGeneration', 'NativeEngine', 'NativeRuntime', 'Speech', 'RuntimeSupport', 'Documents', 'Licenses', 'Settings', 'SearchRuntime', 'Vendor', 'SandboxRuntime'):
        copy_tree(base_payload / folder, payload / folder)
    # Qualification is specific to the installing machine, not redistributable.
    (payload / 'SandboxRuntime/qualification.json').unlink(missing_ok=True)
    for path in app.iterdir():
        if path.is_dir():
            copy_tree(path, payload / path.name)
        else:
            copy_file(path, payload / path.name)
    copy_tree(source, payload / 'Source')
    copy_file(workspace / 'Settings/web-research.json', payload / 'Settings/web-research.json')
    copy_file(workspace / 'Settings/vision.json', payload / 'Settings/vision.json')
    copy_tree(workspace / 'SpeechInput', payload / 'SpeechInput')
    stage_video(workspace, payload)
    stage_ph3(workspace, payload)
    stage_objects(workspace, payload)
    for name in ('LICENSE', 'NOTICE'):
        copy_file(base_payload / name, payload / name)
    (payload / 'candidate.json').write_text(json.dumps({'edition': 'Lite', 'version': '3.0.0-preparation', 'isolatedProfile': True, 'preparedOnly': True}), encoding='utf8')
    (payload / 'PREPARATION-ONLY.txt').write_text('YOEAI 3.0 — Kandinsky preparation only.\nNo tests, application startup, inference, generated samples or installer execution were performed.\nKandinsky generation and production downloads remain disabled.\nThis payload and its unsigned manifest are not production-ready.\nDo not install or enable generation until explicitly authorized.\n', encoding='utf8')
    artifacts = payload / 'Artifacts'; artifacts.mkdir()
    separate = {'Models', 'ImageGeneration', 'Speech', 'SpeechInput', 'VideoGeneration', 'ObjectGeneration', 'Artifacts'}
    assets = [archive_asset(payload, artifacts, 'yoeai-app-support-3.0-preparation', 'application', [p for p in payload.iterdir() if p.name not in separate])]
    for name, kind, folder in [('yoeai-text-models', 'text', 'Models'), ('yoeai-image', 'image', 'ImageGeneration'), ('yoeai-speech', 'speechSynthesis', 'Speech'), ('yoeai-speech-input', 'speechRecognition', 'SpeechInput'), ('yoeai-kandinsky-runtime', 'video', 'VideoGeneration')]:
        assets.append(archive_asset(payload, artifacts, name + '-3.0-preparation', kind, [payload / folder]))
    models = json.loads((backend / 'model-assets.json').read_text(encoding='utf8'))
    for index, model in enumerate(models['files']):
        path = 'VideoGeneration/Kandinsky/Models/' + model['path']
        assets.append({'id': 'kandinsky-model-' + str(index), 'kind': 'video', 'version': models['revision'], 'format': 'file', 'path': 'app/' + path, 'bytes': model['bytes'], 'sha256': model['sha256'], 'url': model['url'], 'offlinePath': path, 'upstreamPublished': True})
    now = datetime.now(timezone.utc)
    assets.extend(ph3_assets(payload))
    assets.extend(object_assets(payload))
    signed = {'schemaVersion': 1, 'product': 'YOEAI', 'channel': 'stable', 'version': '3.0.0-preparation', 'issuedAt': now.isoformat(), 'expiresAt': (now + timedelta(days=30)).isoformat(), 'entrypoint': 'app/YOEAILite.exe', 'assets': assets, 'preparedOnly': True, 'verified': False, 'published': False, 'requiredDiskBytes': sum(a.get('unpackedBytes', a['bytes']) for a in assets), 'backend': 'Kandinsky 6.0 Lite Distill'}
    envelope = {'keyId': 'UNSIGNED-PREPARATION', 'signed': signed, 'signature': None}
    (payload / 'manifest.json').write_text(json.dumps(envelope, indent=2), encoding='utf8')
    (output / 'manifest.local.json').write_text(json.dumps(envelope, indent=2), encoding='utf8')
    for kind in ('Offline', 'Online'):
        name = 'YOEAI-3.0-' + kind + '-Preparation.exe'
        copy_file(workspace / 'Preparation-Installers' / name, output / name)
    copy_file(source / 'installer/release-config.json', output / 'release-config.json')
    status.update(completed=True, modelBytes=models['totalBytes'], packageDownloadBytes=sum(a['bytes'] for a in assets), expandedApplicationBytes=signed['requiredDiskBytes'], assets=len(assets), releaseSigned=False)
    (output / 'preparation.json').write_text(json.dumps(status, indent=2), encoding='utf8')
    print(json.dumps(status), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument('--output', type=Path)
    parser.add_argument('--base-payload', type=Path)
    args = parser.parse_args()
    output = args.output or args.workspace / 'Preparation-Release'
    base = args.base_payload or args.workspace.parents[1] / 'outputs/YOEAI-Intelligent-Upgrade/Candidates/YOEAI-Lite-2.1.0-RC3-Offline/Payload'
    prepare(args.workspace, output, base)


if __name__ == '__main__':
    main()
