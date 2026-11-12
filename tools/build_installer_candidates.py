"""Build isolated Lite/Normal source installers from one exact clean Git tag."""
import argparse
import hashlib
import importlib.metadata
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args):
    subprocess.run([str(x) for x in args], cwd=ROOT, check=True)


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def copy_dependency_notices(payload):
    inventory = []
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata.get('Name', 'unknown')
        component = re.sub(r'[^A-Za-z0-9._-]', '_', name)
        copied = []
        for item in distribution.files or ():
            relative = Path(str(item))
            if relative.is_absolute() or '..' in relative.parts:
                continue
            if not any(word in str(item).lower() for word in ('license', 'copying', 'notice')):
                continue
            original = Path(distribution.locate_file(item))
            if not original.is_file() or original.suffix.lower() in ('.exe', '.dll', '.pyd', '.py', '.pyc'):
                continue
            target = payload / 'Licenses/Python' / component / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original, target)
            copied.append(target.relative_to(payload).as_posix())
        inventory.append({'name': name, 'version': distribution.version,
                          'license': distribution.metadata.get('License-Expression') or distribution.metadata.get('License'),
                          'notices': copied})
    (payload / 'python-component-notices.json').write_text(json.dumps(inventory, indent=2), encoding='utf8')


def smoke_candidate(payload, edition, tag):
    """Exercise the actual frozen entry point; never load a model or optional worker."""
    base = Path(os.environ.get('YOEAI_SOURCE_ORIGINAL_APPDATA', os.environ['LOCALAPPDATA']))
    isolated = base / 'YOEAI-SourceCandidateData' / edition / tag
    home = isolated / ('YOEAILite' if edition == 'Lite' else 'AlsehliAI-Preview')
    if edition == 'Normal':
        subprocess.run([str(payload / 'YOEAI.exe'), '--smoke-test'], cwd=ROOT, check=True, timeout=60)
        result = json.loads((home / 'text-image-shell-test.json').read_text(encoding='utf8'))
        if result.get('status') != 'PASS':
            raise ValueError('Normal frozen UI did not pass its disposable smoke check.')
        return {'passed': True, 'scope': 'Frozen Normal UI construction, no inference.'}
    process = subprocess.Popen([str(payload / 'YOEAILite.exe'), '--headless'], cwd=ROOT)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    url = 'http://127.0.0.1:19237'
    try:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise ValueError('Frozen Lite server exited during smoke check.')
            try:
                state = json.loads((home / 'ui-state.json').read_text(encoding='utf8'))
                if state.get('pid') != process.pid:
                    raise OSError('Waiting for this candidate process to acquire its UI port.')
                with opener.open(url + '/status', timeout=2) as response:
                    json.load(response)
                with opener.open(url + '/', timeout=2) as response:
                    if b'YOEAI' not in response.read():
                        raise ValueError('Candidate HTML is missing.')
                return {'passed': True, 'scope': 'Frozen Lite headless HTTP/HTML, no inference.'}
            except (OSError, json.JSONDecodeError):
                time.sleep(.2)
        raise TimeoutError('Frozen Lite server startup timed out.')
    finally:
        if process.poll() is None:
            try:
                state = json.loads((home / 'ui-state.json').read_text(encoding='utf8'))
                if state.get('pid') == process.pid:
                    request = urllib.request.Request(url + '/shutdown', json.dumps({'token': state['token']}).encode(),
                                                     {'Content-Type': 'application/json', 'Origin': url})
                    with opener.open(request, timeout=5) as response:
                        response.read()
                process.wait(timeout=15)
            except (OSError, ValueError, KeyError, subprocess.TimeoutExpired):
                process.kill()
                process.wait(timeout=10)


def build(edition, tag, commit, output, runtime=None):
    source = ROOT / ('editions/lite/source' if edition == 'Lite' else 'source')
    module = 'app' if edition == 'Lite' else 'customer'
    name = 'YOEAILite' if edition == 'Lite' else 'YOEAI'
    work = output / ('build-' + edition)
    work.mkdir()
    entry = work / 'entry.py'
    # Child tool workers inherit the original base, avoiding recursive profile nesting.
    entry.write_text("import sys,runpy\nfrom pathlib import Path\n"
                     "from source_candidate_environment import configure\n"
                     "configure(Path(sys.executable).parent)\n"
                     f"runpy.run_module('{module}',run_name='__main__')\n", encoding='utf8')
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--onedir', '--windowed',
               '--name', name, '--paths', source, '--paths', ROOT / 'tools', '--hidden-import', module,
               '--distpath', work / 'dist', '--workpath', work / 'pyi', '--specpath', work,
               '--add-data', str(source / 'ui.html') + ';.', '--add-data', str(source / 'assets') + ';assets',
               '--exclude-module', 'torch', '--exclude-module', 'faster_whisper', '--exclude-module', 'piper']
    if edition == 'Lite':
        command += ['--exclude-module', 'PySide6']
    for dependency in ('ddgs', 'pywinauto', 'comtypes'):
        command += ['--collect-submodules', dependency]
    for dependency in ('primp', 'lxml', 'playwright', 'psutil'):
        command += ['--collect-all', dependency]
    for dependency in ('ddgs', 'primp', 'lxml'):
        command += ['--copy-metadata', dependency]
    run(*command, entry)
    payload = work / 'dist' / name
    for file in ('ui.html', 'manifest.json', 'switch_context.ps1', 'stop_model.ps1', 'version.json'):
        if (source / file).is_file():
            shutil.copy2(source / file, payload / file)
    shutil.copytree(source / 'assets', payload / 'assets')
    shutil.copytree(source, payload / 'CorrespondingSource', ignore=shutil.ignore_patterns('__pycache__', '.git', '*.pyc'))
    support = payload / 'CorrespondingBuild'
    support.mkdir()
    shutil.copy2(entry, support / 'entry.py')
    for script in ('build_installer_candidates.py', 'candidate_installer.py', 'source_candidate_environment.py'):
        shutil.copy2(ROOT / 'tools' / script, support / script)
    for file in ('LICENSE', 'NOTICE', 'THIRD-PARTY.md'):
        shutil.copy2(ROOT / file, payload / file)
    copy_dependency_notices(payload)
    run(sys.executable, '-m', 'PyInstaller', '--noconfirm', '--console', '--onedir', '--name', 'YOEAI-Inference',
        '--paths', source, '--distpath', work / 'worker', '--workpath', work / 'worker-build', '--specpath', work,
        '--exclude-module', 'torch', '--exclude-module', 'PySide6', '--exclude-module', 'numpy', source / 'native_worker_entry.py')
    shutil.copytree(work / 'worker/YOEAI-Inference', payload / 'NativeEngine')
    if runtime:
        shutil.copytree(runtime, payload / 'NativeRuntime/b11784')
        shutil.copytree(ROOT / 'build-inputs/Native-Licenses', payload / 'NativeRuntime/Licenses')
    marker = {'edition': edition, 'version': tag, 'sourceCommit': commit, 'sourcePreviewOnly': True}
    (payload / 'source-candidate.json').write_text(json.dumps(marker), encoding='utf8')
    smoke = smoke_candidate(payload, edition, tag)
    print(json.dumps({'edition': edition, 'smoke': smoke}), flush=True)
    (payload / 'candidate-smoke.json').write_text(json.dumps(smoke, indent=2), encoding='utf8')
    dependencies = subprocess.check_output([sys.executable, '-m', 'pip', 'freeze', '--all'], text=True)
    (payload / 'build-dependencies.txt').write_text(dependencies, encoding='utf8')
    rows = [{'path': p.relative_to(payload).as_posix(), 'bytes': p.stat().st_size, 'sha256': digest(p)}
            for p in sorted(payload.rglob('*')) if p.is_file()]
    provenance = {**marker, 'sourceTag': tag, 'files': rows, 'nativeRuntimeIncluded': bool(runtime),
                  'python': sys.version, 'functionallyQualified': False, 'signed': False,
                  'limitations': ['No bundled models or optional voice/media runtimes.',
                                  'No clean-PC, inference, accessibility or GPU qualification is implied.']}
    (payload / 'candidate-provenance.json').write_text(json.dumps(provenance, indent=2), encoding='utf8')
    package = output / (edition + '-Payload.zip')
    with zipfile.ZipFile(package, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(payload.rglob('*')):
            if path.is_file():
                archive.write(path, path.relative_to(payload).as_posix())
    budget = sum(p.stat().st_size for p in payload.rglob('*') if p.is_file())
    setup = work / 'setup.py'
    setup.write_text('from candidate_installer import main\n' +
                     f'main({edition!r},{tag!r},{package.name!r},{digest(package)!r},{budget!r})\n', encoding='utf8')
    run(sys.executable, '-m', 'PyInstaller', '--noconfirm', '--onefile', '--console', '--name', edition + '-Setup',
        '--paths', ROOT / 'tools', '--distpath', output, '--workpath', work / 'setup-build', '--specpath', work, setup)
    run(output / (edition + '-Setup.exe'), '--verify')
    run(output / (edition + '-Setup.exe'), '--test-install', work / 'extraction-check')
    # Standalone matching inventories remain convenient without unpacking the ZIP.
    (output / (edition + '-provenance.json')).write_text(json.dumps(provenance, indent=2), encoding='utf8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--native-runtime', type=Path)
    args = parser.parse_args()
    if sys.platform != 'win32':
        parser.error('Windows x64 build environment required.')
    if not re.fullmatch(r'candidate-[A-Za-z0-9][A-Za-z0-9._-]{0,79}', args.tag):
        parser.error('Use a candidate-* tag, not an existing production release tag.')
    commit = git('rev-parse', 'HEAD')
    if git('rev-parse', '--verify', 'refs/tags/' + args.tag + '^{commit}') != commit or git('status', '--porcelain', '--untracked-files=no'):
        parser.error('Build must use the exact clean tagged commit.')
    if args.native_runtime:
        sys.path.insert(0, str(ROOT / 'source'))
        from native_ai.integrity import verify
        verify(args.native_runtime)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    for edition in ('Lite', 'Normal'):
        build(edition, args.tag, commit, output, args.native_runtime)
    files = sorted(p for p in output.iterdir() if p.is_file())
    (output / 'SHA256SUMS.txt').write_text(''.join(digest(p) + '  ' + p.name + '\n' for p in files), encoding='utf8')


if __name__ == '__main__':
    main()
