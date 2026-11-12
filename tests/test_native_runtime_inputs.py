"""Runtime transport/extraction tests never execute DLLs or use a network."""
import io
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from provision_native_runtime import digest, extract_libraries, obtain, UpstreamRedirect


class NativeRuntimeInputTests(unittest.TestCase):
    def test_stages_only_native_libraries_not_servers(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); archive = root / 'input.zip'; stage = root / 'stage'; stage.mkdir()
            with zipfile.ZipFile(archive, 'w') as package:
                for name in ('bin/llama.dll', 'bin/mtmd.dll', 'bin/ggml-cpu-x64.dll', 'bin/llama-server.exe',
                             'bin/llama-server-impl.dll', 'bin/ggml-rpc.dll'):
                    package.writestr(name, b'fixture only')
            extract_libraries(archive, stage)
            self.assertEqual({p.name for p in stage.iterdir()}, {'llama.dll', 'mtmd.dll', 'ggml-cpu-x64.dll'})

    def test_rejects_traversal_and_duplicate_libraries(self):
        for paths in (('../llama.dll',), ('llama.dll', 'second/llama.dll')):
            with self.subTest(paths=paths), tempfile.TemporaryDirectory() as raw:
                root = Path(raw); archive = root / 'input.zip'; stage = root / 'stage'; stage.mkdir()
                with zipfile.ZipFile(archive, 'w') as package:
                    for name in paths:
                        package.writestr(name, b'fixture only')
                with self.assertRaises(ValueError):
                    extract_libraries(archive, stage)

    def test_existing_verified_cache_is_reused_without_network(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); path = root / 'pinned.zip'; path.write_bytes(b'fixture')
            actual = obtain(root, path.name, 7, digest(path), 'https://invalid.example/never-requested')
            self.assertEqual(actual, path)

    def test_invalid_cached_input_is_preserved_and_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); path = root / 'pinned.zip'; path.write_bytes(b'changed')
            with self.assertRaises(ValueError):
                obtain(root, path.name, 7, hashlib.sha256(b'correct').hexdigest(), 'https://invalid.example/never-requested')
            self.assertEqual(path.read_bytes(), b'changed')

    def test_rejects_external_or_insecure_redirects(self):
        for url in ('http://github.com/file', 'https://github.com.evil.example/file', 'https://localhost/file'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                UpstreamRedirect().redirect_request(None, None, 302, '', {}, url)


if __name__ == '__main__':
    unittest.main()
