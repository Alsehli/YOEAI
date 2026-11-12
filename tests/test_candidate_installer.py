"""Extraction boundaries and additive installation, with disposable files only."""
import hashlib
import io
import json
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from candidate_installer import archive_entries, digest, install, verify
from source_candidate_environment import configure


class CandidateInstallerTests(unittest.TestCase):
    def package(self, root):
        path = root / 'payload.zip'
        data = b'disposable application fixture; never executable'
        meta = {'sourceCommit': 'a' * 40, 'files': [{'path': 'app.txt', 'bytes': len(data),
                 'sha256': hashlib.sha256(data).hexdigest()}]}
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('app.txt', data)
            archive.writestr('candidate-provenance.json', json.dumps(meta))
        return path

    def test_verified_install_preserves_existing_data(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            original = root / 'existing'
            original.mkdir()
            (original / 'profile.txt').write_text('keep me')
            package = self.package(root)
            with self.assertRaises(ValueError):
                install(package, digest(package), 4096, original)
            result = install(package, digest(package), 4096, root / 'new-version')
            self.assertEqual(result['sourceCommit'], 'a' * 40)
            self.assertFalse(result['functionallyQualified'])
            self.assertEqual((original / 'profile.txt').read_text(), 'keep me')
            self.assertTrue((root / 'new-version/app.txt').is_file())

    def test_tampered_transport_never_creates_destination(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            package = self.package(root)
            expected = digest(package)
            with package.open('ab') as stream:
                stream.write(b'changed')
            with self.assertRaises(ValueError):
                install(package, expected, 4096, root / 'destination')
            self.assertFalse((root / 'destination').exists())

    def test_internal_inventory_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            package = self.package(Path(raw))
            with zipfile.ZipFile(package, 'a') as archive:
                archive.writestr('unexpected.txt', b'extra')
            with self.assertRaises(ValueError):
                verify(package, digest(package), 4096)

    def test_unsafe_windows_paths_and_aliases_are_rejected(self):
        for name in ('../outside', '/absolute', 'C:/absolute', 'a\\outside', 'a/../outside',
                     'CON.txt', 'dir/NUL', 'bad:stream', 'trailing.', 'a//alias', './alias', 'bad?.txt'):
            with self.subTest(name=name), io.BytesIO() as stream:
                with zipfile.ZipFile(stream, 'w') as writer:
                    entry = zipfile.ZipInfo('fixture')
                    entry.filename = name
                    writer.writestr(entry, b'x')
                with zipfile.ZipFile(stream) as reader, self.assertRaises(ValueError):
                    archive_entries(reader, 4096)

    def test_duplicate_case_and_symlink_are_rejected(self):
        for linked in (False, True):
            with io.BytesIO() as stream:
                with zipfile.ZipFile(stream, 'w') as writer:
                    if linked:
                        entry = zipfile.ZipInfo('link')
                        entry.create_system = 3
                        entry.external_attr = (stat.S_IFLNK | 0o777) << 16
                        writer.writestr(entry, '../outside')
                    else:
                        writer.writestr('A.txt', b'a')
                        writer.writestr('a.txt', b'b')
                with zipfile.ZipFile(stream) as reader, self.assertRaises(ValueError):
                    archive_entries(reader, 4096)

    def test_expansion_budget_is_enforced(self):
        with io.BytesIO() as stream:
            with zipfile.ZipFile(stream, 'w') as writer:
                writer.writestr('large.txt', b'x' * 2048)
            with zipfile.ZipFile(stream) as reader, self.assertRaises(ValueError):
                archive_entries(reader, 1024)

    def test_profiles_and_child_processes_keep_candidate_isolation(self):
        with tempfile.TemporaryDirectory() as raw, patch.dict('os.environ', {'LOCALAPPDATA': raw}, clear=True):
            root = Path(raw) / 'app'
            root.mkdir()
            marker = root / 'source-candidate.json'
            marker.write_text(json.dumps({'edition': 'Lite', 'version': 'candidate-test'}))
            home = configure(root)
            profile = home / 'profile.json'
            original = json.loads(profile.read_text())
            self.assertEqual(original['uiPort'], 19237)
            original['context'] = 12345
            profile.write_text(json.dumps(original))
            self.assertEqual(configure(root), home)
            self.assertEqual(json.loads(profile.read_text())['context'], 12345)
            marker.write_text(json.dumps({'edition': 'Normal', 'version': 'candidate-test'}))
            normal = configure(root)
            self.assertEqual(json.loads((normal / 'config.json').read_text())['uiPort'], 19247)
            marker.write_text(json.dumps({'edition': 'Lite', 'version': '../escape'}))
            with self.assertRaises(ValueError):
                configure(root)


if __name__ == '__main__':
    unittest.main()
