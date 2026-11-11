import json
import tempfile
import unittest
from pathlib import Path
from release_readiness import audit


class OfflineReadiness(unittest.TestCase):
    def test_missing_models_cannot_pass(self):
        with tempfile.TemporaryDirectory() as folder:
            result = audit(folder)
            self.assertFalse(result['offlineReleaseReady'])
            self.assertFalse(result['allRequiredAssetsPresent'])
            self.assertFalse(result['checks']['speechRecognition']['assetsPresent'])

    def test_external_model_paths_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / 'ImageGeneration/config.json'
            config.parent.mkdir()
            config.write_text(json.dumps({'executable': str(Path(folder).anchor + 'external.exe')}))
            check = audit(folder)['checks']['image']
            self.assertFalse(check['assetsPresent'])
            self.assertIn('machine-specific', check['error'])

    def test_relative_escape_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / 'ImageGeneration/config.json'
            config.parent.mkdir()
            config.write_text(json.dumps({'executable': '../../external.exe'}))
            check = audit(folder)['checks']['image']
            self.assertFalse(check['assetsPresent'])
            self.assertIn('escapes payload', check['error'])

    def test_present_files_are_not_execution_proof(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder) / 'ImageGeneration'
            directory.mkdir()
            (directory / 'component').write_bytes(b'fixture')
            (directory / 'config.json').write_text(json.dumps(dict.fromkeys(('executable', 'diffusion', 'encoder', 'vae'), 'component')))
            result = audit(folder)
            self.assertTrue(result['checks']['image']['assetsPresent'])
            self.assertFalse(result['checks']['image']['functionallyVerified'])
            self.assertFalse(result['offlineReleaseReady'])


if __name__ == '__main__':
    unittest.main()
