"""Stage the exact existing b11784 ABI from pinned upstream inputs; no model downloads."""
import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import re
import shutil
import stat
import tempfile
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
COMMIT = '493253fe5a5af7e800b3c92a2452b5684a99e961'
BASE = 'https://github.com/ggml-org/llama.cpp/releases/download/b11784/'
INPUTS = (
    ('llama-b11784-bin-win-cuda-13.4-x64.zip', 159660562,
     '28cc853ad9ffbaf801d09ef7435364bdf814c9dad831ba08c1c49c194e5cb29a'),
    ('cudart-llama-bin-win-cuda-13.4-x64.zip', 423535356,
     '738f8c251ac22b70c3ae6f83a10cf222725df0395246a2cf58f32bdb85fbe668'),
)
LICENSE = ('llama-b11784-LICENSE.txt', 1078,
           '94f29bbed6a22c35b992c5c6ebf0e7c92f13b836b90f36f461c9cf2f0f1d010d')
DLL_PATTERN = re.compile(r'(?:llama|mtmd|ggml|ggml-base|ggml-cuda|ggml-cpu-[a-z0-9]+|libomp|cudart64_13|cublas64_13|cublasLt64_13)\.dll')
CRT = ('msvcp140.dll', 'msvcp140_1.dll', 'msvcp140_2.dll', 'vcruntime140.dll', 'vcruntime140_1.dll')


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


class UpstreamRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, url):
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != 'https' or not (parsed.hostname == 'github.com' or (parsed.hostname or '').endswith('.githubusercontent.com')):
            raise ValueError('Runtime download redirected outside the upstream HTTPS hosts.')
        return super().redirect_request(request, fp, code, message, headers, url)


def obtain(cache, name, size, expected, url):
    cache.mkdir(parents=True, exist_ok=True)
    destination = cache / name
    if destination.is_symlink():
        raise ValueError('Runtime cache must not contain symbolic links.')
    if destination.exists():
        if destination.stat().st_size != size or digest(destination) != expected:
            raise ValueError('Cached upstream input failed integrity: ' + name)
        return destination
    # Unique cache-owned temporary file; failed transfers never alter an existing input.
    with tempfile.NamedTemporaryFile(prefix='.native-input-', dir=cache, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            opener = urllib.request.build_opener(UpstreamRedirect())
            with opener.open(url, timeout=60) as response:
                total = 0
                while chunk := response.read(8 * 1024 * 1024):
                    total += len(chunk)
                    if total > size:
                        raise ValueError('Upstream input exceeds its pinned size.')
                    stream.write(chunk)
            stream.flush()
            if total != size:
                raise ValueError('Incomplete upstream input.')
        except Exception:
            stream.close()
            temporary.unlink(missing_ok=True)
            raise
    try:
        if digest(temporary) != expected:
            raise ValueError('Upstream input checksum failed: ' + name)
        if destination.exists():
            raise ValueError('Runtime cache changed during download.')
        temporary.rename(destination)
        return destination
    finally:
        temporary.unlink(missing_ok=True)


def extract_libraries(path, stage):
    """Fixed flat DLL allowlist; no executable, server, RPC backend or archive path escapes."""
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        if len(entries) > 1000 or sum(item.file_size for item in entries) > 2 * 1024**3:
            raise ValueError('Upstream archive exceeds its extraction budget.')
        for item in entries:
            name = item.orig_filename
            relative = PurePosixPath(name)
            if relative.is_absolute() or '..' in relative.parts or '\\' in name or ':' in name or stat.S_ISLNK(item.external_attr >> 16):
                raise ValueError('Unsafe upstream archive entry.')
            leaf = relative.name
            if item.is_dir() or not (DLL_PATTERN.fullmatch(leaf) or leaf == 'LICENSE-LLVM-OpenMP'):
                continue
            target = stage / leaf
            if target.exists() or not target.resolve().is_relative_to(stage.resolve()):
                raise ValueError('Duplicate or unsafe runtime library.')
            with archive.open(item) as source, target.open('xb') as output:
                shutil.copyfileobj(source, output, 8 * 1024 * 1024)


def provision(output, cache):
    output, cache = Path(output).resolve(), Path(cache).resolve()
    if output.exists():
        raise ValueError('Runtime destination already exists and was preserved.')
    paths = [obtain(cache, name, size, expected, BASE + name) for name, size, expected in INPUTS]
    license_path = obtain(cache, *LICENSE, f'https://raw.githubusercontent.com/ggml-org/llama.cpp/{COMMIT}/LICENSE')
    spec = importlib.util.find_spec('PySide6')
    if not spec or importlib.metadata.version('PySide6') != '6.12.0':
        raise ValueError('Install the pinned PySide6 6.12.0 build input for its app-local Microsoft CRT files.')
    carrier = Path(next(iter(spec.submodule_search_locations)))
    if any(not (carrier / name).is_file() for name in CRT):
        raise ValueError('Pinned Microsoft CRT carrier is incomplete.')
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.native-stage-', dir=output.parent))
    try:
        for path in paths:
            extract_libraries(path, stage)
        shutil.copy2(license_path, stage / 'LICENSE-llama.cpp.txt')
        for name in CRT:
            shutil.copy2(carrier / name, stage / name)
        required = {'llama.dll', 'ggml.dll', 'ggml-base.dll', 'mtmd.dll', 'ggml-cuda.dll',
                    'cudart64_13.dll', 'cublas64_13.dll', 'cublasLt64_13.dll', 'libomp.dll'}
        if not required.issubset({p.name for p in stage.iterdir()}):
            raise ValueError('Pinned runtime libraries are incomplete.')
        provenance = {'abi': 'llama.cpp-b11784-win-x64', 'sourceCommit': COMMIT,
                      'sourceUrl': f'https://github.com/ggml-org/llama.cpp/tree/{COMMIT}',
                      'archives': [{'name': n, 'bytes': size, 'sha256': sha, 'url': BASE + n} for n, size, sha in INPUTS],
                      'microsoftCrtCarrier': {'package': 'PySide6', 'version': '6.12.0', 'files': list(CRT)},
                      'modelWeightsIncluded': False, 'gpuFunctionallyQualified': False}
        (stage / 'input-provenance.json').write_text(json.dumps(provenance, indent=2), encoding='utf8')
        files = {p.name: digest(p) for p in sorted(stage.iterdir()) if p.is_file()}
        (stage / 'runtime-manifest.json').write_text(json.dumps({'abi': provenance['abi'], 'files': files}, indent=2), encoding='utf8')
        stage.rename(output)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return {'runtime': str(output), 'files': len(files), 'upstreamHashesVerified': True,
            'gpuFunctionallyQualified': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cache', type=Path, required=True)
    options = parser.parse_args()
    print(json.dumps(provision(options.output, options.cache)))
