"""Relative image assets must work independently of the app launch directory."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import image_generation
from design_generation import DesignGenerator

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('lite_portable_image', ROOT / 'editions/lite/source/image_generation.py')
lite = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lite)


class OptionalImagePathTests(unittest.TestCase):
    def test_both_editions_resolve_relative_files_beside_config(self):
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw) / 'moved image package'
            folder.mkdir()
            values = {key: key + '.fixture' for key in ('executable', 'diffusion', 'encoder', 'vae')}
            for name in values.values():
                (folder / name).write_bytes(b'fixture, not an executable or model')
            config = folder / 'config.json'
            config.write_text(json.dumps(values), encoding='utf-8-sig')
            for module in (image_generation, lite):
                result = module.ImageGenerator(config, folder / 'output').config()
                self.assertEqual(result, {key: str(folder / name) for key, name in values.items()})
            self.assertFalse((folder / 'output').exists())

    def test_both_editions_preserve_existing_absolute_files(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            asset = root / 'asset.fixture'
            asset.write_bytes(b'fixture')
            values = {key: str(asset) for key in ('executable', 'diffusion', 'encoder', 'vae')}
            config = root / 'config.json'
            config.write_text(json.dumps(values))
            for module in (image_generation, lite):
                self.assertEqual(module.ImageGenerator(config, root).config(), values)

    def test_both_editions_reject_invalid_shapes_and_path_values(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            config = root / 'config.json'
            for value in ([], None, {'executable': None}, {'executable': True}, {'executable': ''}, {'executable': 'missing.exe'}):
                config.write_text(json.dumps(value))
                for module in (image_generation, lite):
                    with self.subTest(value=value, module=module.__name__), self.assertRaises(ValueError):
                        module.ImageGenerator(config, root).config()

    def test_design_resolves_paths_before_checking_verified_model(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / 'python.exe').write_bytes(b'fixture, never executed')
            (root / 'Models').mkdir()
            (root / 'Models/weights.fixture').write_bytes(b'fixture')
            for name, value in {
                'config.json': {'python': 'python.exe', 'modelDirectory': 'Models', 'revision': 'fixture-revision'},
                'backend.json': {'cudaAvailable': True},
                'files-verified.json': {'revision': 'fixture-revision'},
                'model-manifest.json': {'siblings': [{'rfilename': 'weights.fixture', 'size': 7}]},
            }.items():
                (root / name).write_text(json.dumps(value))
            design = DesignGenerator(root / 'config.json', None, None, root / 'lock')
            result = design.config()
            self.assertEqual(Path(result['python']), root / 'python.exe')
            self.assertEqual(Path(result['modelDirectory']), root / 'Models')
            (root / 'Models/weights.fixture').write_bytes(b'incomplete')
            with self.assertRaisesRegex(ValueError, 'missing or incomplete'):
                design.config()

    def test_design_rejects_non_object_configuration(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / 'config.json').write_text('[]')
            design = DesignGenerator(root / 'config.json', None, None, root / 'lock')
            with self.assertRaisesRegex(ValueError, 'object'):
                design.config()


if __name__ == '__main__':
    unittest.main()
