"""Prepared offline transport for the same signed YOEAI 3.0 release contract."""
import json
from pathlib import Path
from .releases import Installer, ReleaseError, beneath, digest, verify_manifest, MAX_MANIFEST


class OfflineInstaller(Installer):
    def __init__(self, config, cache, payload, progress=lambda event: None, cancel=None):
        super().__init__(config, cache, progress, cancel=cancel)
        self.payload = Path(payload).resolve()

    def manifest(self):
        if self.config.get('offlineInstallEnabled') is not True:
            raise ReleaseError('Offline artifacts are prepared but untested. Installation has not been enabled.')
        file = self.payload / 'manifest.json'
        if not file.is_file() or file.stat().st_size > MAX_MANIFEST:
            raise ReleaseError('The complete signed offline manifest is missing or oversized.')
        envelope = json.loads(file.read_text(encoding='utf-8-sig'))
        return envelope, verify_manifest(envelope, self.config)

    def download(self, asset):
        self.check()
        path = beneath(self.payload, asset.get('offlinePath', ''))
        if path.is_symlink() or not path.is_file() or path.stat().st_size != asset['bytes'] or digest(path) != asset['sha256']:
            raise ReleaseError('Offline asset is missing or fails its signed size/SHA-256: ' + asset['id'])
        self.progress({'phase': 'download', 'id': asset['id'], 'received': asset['bytes'], 'total': asset['bytes'], 'offline': True})
        return path

    def remaining_download_bytes(self, assets):
        return 0  # Assets are already present; never contact a download server.
