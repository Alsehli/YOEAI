"""Signed HTTPS manifests, resumable hash-verified assets and atomic installation."""
import base64
import contextlib
import hashlib
import json
import os
import re
import shutil
import ssl
import stat
import tempfile
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature

DEFAULT_CONFIG = Path(__file__).with_name('release-config.json')
MAX_MANIFEST = 1024 * 1024
MAX_ASSET = 1024 ** 4


class ReleaseError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf8')


def https(url):
    if not isinstance(url, str):
        raise ReleaseError('An HTTPS URL is required.')
    value = urllib.parse.urlsplit(url)
    if value.scheme != 'https' or not value.hostname or value.username or value.password or value.fragment:
        raise ReleaseError('Only HTTPS URLs without embedded credentials are allowed.')
    return url


class HTTPSRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        https(newurl)
        return super().redirect_request(request, fp, code, message, headers, newurl)


def client(context=None):
    # Every requested URL is checked; downgrade redirects are rejected explicitly.
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=context or ssl.create_default_context()), HTTPSRedirect())
    return opener


def relative(value):
    if not isinstance(value, str) or not value or '\\' in value or ':' in value or '\0' in value:
        raise ReleaseError('Unsafe installation path.')
    path = PurePosixPath(value)
    if path.is_absolute() or any(p in ('', '.', '..') for p in value.split('/')):
        raise ReleaseError('Installation path must be relative and normalized.')
    for part in path.parts:
        if part.endswith((' ', '.')) or re.search(r'[<>"|?*\x00-\x1f]', part) or part.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL', *('COM'+str(n) for n in range(1, 10)), *('LPT'+str(n) for n in range(1, 10))}:
            raise ReleaseError('Unsafe Windows installation path.')
    return path


def beneath(root, path):
    target = root.joinpath(*relative(path).parts).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ReleaseError('Installation path escapes its root.')
    # Standalone Python/PyTorch notices include paths beyond MAX_PATH. Use the
    # Windows extended-path API form without changing system policy/settings.
    text = str(target)
    if os.name == 'nt' and len(text) > 240 and not text.startswith('\\\\?\\'):
        target = Path('\\\\?\\UNC\\' + text[2:] if text.startswith('\\\\') else '\\\\?\\' + text)
    return target


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify_manifest(envelope, config, now=None):
    try:
        payload = envelope['signed']
        key = config['trustedKeys'][envelope['keyId']]
        public = Ed25519PublicKey.from_public_bytes(base64.b64decode(key, validate=True))
        public.verify(base64.b64decode(envelope['signature'], validate=True), canonical(payload))
    except (KeyError, TypeError, ValueError, InvalidSignature) as error:
        raise ReleaseError('Release signature is invalid or its signing key is not trusted.') from error
    if not isinstance(payload, dict) or payload.get('schemaVersion') != 1 or payload.get('product') != 'YOEAI' or payload.get('channel') != config.get('channel', 'stable'):
        raise ReleaseError('This manifest does not describe the requested YOEAI release.')
    if not re.fullmatch(r'3\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)(?:-[A-Za-z0-9.-]+)?', str(payload.get('version', ''))):
        raise ReleaseError('Only YOEAI 3.x packages are accepted; legacy packages are never substituted.')
    try:
        issued = datetime.fromisoformat(payload['issuedAt'].replace('Z', '+00:00'))
        expiry = datetime.fromisoformat(payload['expiresAt'].replace('Z', '+00:00'))
        clock = now or datetime.now(timezone.utc)
        if issued.tzinfo is None or expiry.tzinfo is None or not issued <= clock < expiry:
            raise ValueError()
    except (KeyError, TypeError, ValueError) as error:
        raise ReleaseError('Release metadata is expired or not yet valid.') from error
    entrypoint = relative(payload.get('entrypoint'))
    if entrypoint.suffix.lower() != '.exe':
        raise ReleaseError('The Windows release must specify an executable entry point.')
    assets = payload.get('assets')
    if not isinstance(assets, list) or not 1 <= len(assets) <= 20000:
        raise ReleaseError('Invalid release asset list.')
    ids, destinations, kinds = set(), set(), set()
    for asset in assets:
        if not isinstance(asset, dict) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}', str(asset.get('id', ''))) or asset['id'] in ids:
            raise ReleaseError('Asset identifiers must be unique.')
        ids.add(asset['id'])
        if asset.get('kind') not in {'application', 'text', 'image', 'video', 'speechRecognition', 'speechSynthesis', 'support'}:
            raise ReleaseError('Unknown release component.')
        kinds.add(asset['kind'])
        if not isinstance(asset.get('version'), str) or not asset['version'] or len(asset['version']) > 100:
            raise ReleaseError('Each component needs its own pinned version.')
        https(asset.get('url'))
        if type(asset.get('bytes')) is not int or not 0 < asset['bytes'] <= MAX_ASSET or not re.fullmatch('[0-9a-f]{64}', str(asset.get('sha256', ''))):
            raise ReleaseError('Asset size and SHA-256 must be pinned.')
        if asset.get('format') not in ('file', 'zip'):
            raise ReleaseError('Unsupported asset format.')
        destination = str(relative(asset.get('path'))).casefold()
        # Separate signed archives may overlay one application root. Extraction
        # uses exclusive file creation, so overlapping files still fail safely.
        if asset['format'] == 'file' and destination in destinations:
            raise ReleaseError('Duplicate asset destination.')
        if asset['format'] == 'file':
            destinations.add(destination)
        if asset['format'] == 'zip' and (type(asset.get('unpackedBytes')) is not int or not 0 < asset['unpackedBytes'] <= MAX_ASSET):
            raise ReleaseError('Archive extraction requires a signed size budget.')
    if not {'application', 'text', 'image', 'video', 'speechRecognition', 'speechSynthesis'} <= kinds:
        raise ReleaseError('The unified release is missing a required AI component.')
    return payload


@contextlib.contextmanager
def cache_lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as stream:
        stream.seek(0)
        if not stream.read(1):
            stream.write(b'0'); stream.flush()
        stream.seek(0)
        if os.name == 'nt':
            import msvcrt
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as error:
                raise ReleaseError('Another installer is using this download cache.') from error
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


class Installer:
    def __init__(self, config, cache, progress=lambda event: None, opener=None, cancel=None):
        self.config, self.cache, self.progress = config, Path(cache).resolve(), progress
        self.opener = opener or client()
        self.cancel = cancel

    def check(self):
        if self.cancel and self.cancel.is_set():
            raise ReleaseError('Installation cancelled. Download progress was retained.')

    def manifest(self):
        if self.config.get('enabled') is not True:
            raise ReleaseError(self.config.get('disabledReason', 'Release downloads are disabled.'))
        if not self.config.get('trustedKeys'):
            raise ReleaseError('No production signing key is configured. Downloads remain disabled.')
        url = https(self.config.get('manifestUrl'))
        self.check()
        self.progress({'phase': 'manifest', 'message': 'Checking signed release metadata…'})
        with self.opener.open(urllib.request.Request(url, headers={'Accept-Encoding': 'identity'}), timeout=30) as response:
            https(response.geturl())
            data = response.read(MAX_MANIFEST + 1)
        if len(data) > MAX_MANIFEST:
            raise ReleaseError('Release metadata is too large.')
        try:
            envelope = json.loads(data)
            payload = verify_manifest(envelope, self.config)
        except (ValueError, TypeError) as error:
            raise ReleaseError(str(error)) from error
        return envelope, payload

    def download(self, asset):
        self.check()
        self.cache.mkdir(parents=True, exist_ok=True)
        final = self.cache / (asset['sha256'] + '.blob')
        partial = final.with_suffix('.part')
        if final.is_symlink() or partial.is_symlink():
            raise ReleaseError('Download cache links are not accepted.')
        if final.is_file() and final.stat().st_size == asset['bytes'] and digest(final) == asset['sha256']:
            self.progress({'phase': 'download', 'id': asset['id'], 'received': asset['bytes'], 'total': asset['bytes'], 'cached': True})
            return final
        offset = partial.stat().st_size if partial.is_file() else 0
        if offset >= asset['bytes']:
            if offset == asset['bytes'] and digest(partial) == asset['sha256']:
                partial.replace(final)
                return final
            partial.unlink(); offset = 0
        headers = {'Accept-Encoding': 'identity'}
        if offset:
            headers['Range'] = f'bytes={offset}-'
        request = urllib.request.Request(https(asset['url']), headers=headers)
        with self.opener.open(request, timeout=30) as response:
            https(response.geturl())
            status = response.status
            if status == 206:
                match = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)', response.headers.get('Content-Range', ''))
                if not match or tuple(map(int, match.groups())) != (offset, asset['bytes'] - 1, asset['bytes']):
                    raise ReleaseError('The download server returned an invalid resume range.')
            elif status == 200:
                offset = 0  # Server ignored Range: restart, never append a full file.
            else:
                raise ReleaseError('Unexpected download response.')
            if response.headers.get('Content-Encoding', 'identity') != 'identity':
                raise ReleaseError('Encoded payload responses are not accepted.')
            with partial.open('ab' if offset else 'wb') as output:
                received = offset
                while True:
                    self.check()
                    chunk = response.read(min(1024 * 1024, asset['bytes'] - received + 1))
                    if not chunk:
                        break
                    if received + len(chunk) > asset['bytes']:
                        raise ReleaseError('Downloaded asset exceeds its signed size.')
                    output.write(chunk); received += len(chunk)
                    self.progress({'phase': 'download', 'id': asset['id'], 'received': received, 'total': asset['bytes'], 'resumedFrom': offset})
                output.flush(); os.fsync(output.fileno())
        if received != asset['bytes']:
            raise ReleaseError('Download interrupted. Run setup again to resume.')
        self.progress({'phase': 'verify', 'id': asset['id'], 'message': 'Verifying SHA-256…'})
        if digest(partial) != asset['sha256']:
            partial.unlink()
            raise ReleaseError('Asset checksum mismatch. Installation was not changed.')
        partial.replace(final)
        return final

    def remaining_download_bytes(self, assets):
        remaining = 0
        for asset in assets:
            final = self.cache / (asset['sha256'] + '.blob')
            partial = final.with_suffix('.part')
            if final.is_file() and not final.is_symlink() and final.stat().st_size == asset['bytes'] and digest(final) == asset['sha256']:
                continue
            received = partial.stat().st_size if partial.is_file() and not partial.is_symlink() else 0
            remaining += max(0, asset['bytes'] - received) if received <= asset['bytes'] else asset['bytes']
        return remaining

    def install(self, install_base):
        envelope, release = self.manifest()
        base = Path(install_base).resolve()
        destination = base / release['version']
        if destination.exists():
            raise ReleaseError('This version already exists. No existing installation was replaced.')
        base.mkdir(parents=True, exist_ok=True)
        required = sum(a.get('unpackedBytes', a['bytes']) for a in release['assets'])
        pending = self.remaining_download_bytes(release['assets'])
        cache_parent = self.cache
        while not cache_parent.exists():
            cache_parent = cache_parent.parent
        same_volume = base.anchor.casefold() == self.cache.anchor.casefold()
        if shutil.disk_usage(base).free < required + (pending if same_volume else 0) + 1024 ** 3:
            raise ReleaseError('Insufficient disk space for the complete release and safety margin.')
        if not same_volume and shutil.disk_usage(cache_parent).free < pending + 1024 ** 3:
            raise ReleaseError('Insufficient disk space for resumable downloads on the cache volume.')
        with cache_lock(self.cache / 'download.lock'):
            downloads = [(asset, self.download(asset)) for asset in release['assets']]
            # All signed metadata and assets are verified before creating a stage.
            stage = Path(tempfile.mkdtemp(prefix='.yoeai-stage-', dir=base)).resolve()
            try:
                for asset, blob in downloads:
                    self.check()
                    self.progress({'phase': 'install', 'id': asset['id'], 'message': 'Installing verified component…'})
                    target = beneath(stage, asset['path'])
                    if asset['format'] == 'file':
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with blob.open('rb') as source, target.open('xb') as output:
                            shutil.copyfileobj(source, output, 1024 * 1024)
                    else:
                        self.extract(blob, target, asset['unpackedBytes'])
                entrypoint = beneath(stage, release['entrypoint'])
                if not entrypoint.is_file():
                    raise ReleaseError('Verified package does not contain its declared application entry point.')
                (stage / 'installed-release.json').write_bytes(canonical(envelope))
                self.check()
                stage.rename(destination)
            finally:
                if stage.exists() and stage.parent == base and stage.name.startswith('.yoeai-stage-'):
                    cleanup = str(stage)
                    if os.name == 'nt' and not cleanup.startswith('\\\\?\\'):
                        cleanup = '\\\\?\\UNC\\' + cleanup[2:] if cleanup.startswith('\\\\') else '\\\\?\\' + cleanup
                    shutil.rmtree(cleanup)
        result = {'product': 'YOEAI', 'version': release['version'], 'destination': str(destination), 'entrypoint': str(destination.joinpath(*relative(release['entrypoint']).parts)), 'signatureVerified': True, 'sha256Verified': True}
        self.progress({'phase': 'complete', **result})
        return result

    def extract(self, archive, root, budget):
        expanded = 0
        with zipfile.ZipFile(archive) as package:
            entries = package.infolist()
            if len(entries) > 100000:
                raise ReleaseError('Too many files in package.')
            for info in entries:
                self.check()
                name = info.filename.rstrip('/')
                destination = beneath(root, name)
                mode = info.external_attr >> 16
                if stat.S_ISLNK(mode):
                    raise ReleaseError('Package symbolic links are not accepted.')
                if info.is_dir():
                    destination.mkdir(parents=True, exist_ok=True)
                    continue
                expanded += info.file_size
                if expanded > budget:
                    raise ReleaseError('Package exceeds its signed extraction budget.')
                destination.parent.mkdir(parents=True, exist_ok=True)
                with package.open(info) as source, destination.open('xb') as output:
                    copied = 0
                    while True:
                        self.check()
                        chunk = source.read(1024 * 1024)
                        if not chunk:
                            break
                        copied += len(chunk)
                        if copied > info.file_size:
                            raise ReleaseError('Invalid archive file size.')
                        output.write(chunk)
                    if copied != info.file_size:
                        raise ReleaseError('Incomplete archive entry.')
