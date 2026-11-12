"""Moved voice packages must not depend on the application's working directory."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from optional_paths import load_paths
import interactive_voice
import speech_input

WORKER = Path(__file__).resolve().parents[1] / 'source/assets/speech-input/interactive_worker.py'
SPEC = importlib.util.spec_from_file_location('portable_voice_worker', WORKER)
worker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(worker)


class OptionalVoicePathTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'moved package'
        self.folder = self.root / 'SpeechInput'
        self.folder.mkdir(parents=True)
        for name in ('python.exe', 'worker.py'):
            (self.folder / name).write_bytes(b'fixture, never executed')
        (self.folder / 'model').mkdir()
        (self.root / 'Speech').mkdir()
        self.values = {'python': 'python.exe', 'worker': 'worker.py', 'model': 'model', 'speech': '../Speech'}

    def config(self, name, values=None):
        path = self.folder / name
        path.write_text(json.dumps(self.values if values is None else values), encoding='utf-8-sig')
        return path

    def test_dictation_resolves_beside_config_and_defaults_cache_to_profile(self):
        config = self.config('config.json')
        home = self.root / 'profile'
        with patch.object(speech_input, 'HOME', home):
            service = speech_input.Dictation(config)
            self.addCleanup(service.cancel)
            value = service.settings()
        self.assertEqual(Path(value['python']), self.folder / 'python.exe')
        self.assertEqual(Path(value['worker']), self.folder / 'worker.py')
        self.assertEqual(Path(value['model']), self.folder / 'model')
        self.assertEqual(Path(value['cache']), home / 'Dictation/Cache')
        self.assertFalse((home / 'Dictation/Cache').exists())

    def test_explicit_relative_cache_is_relative_to_config(self):
        config = self.config('config.json', dict(self.values, cache='local cache'))
        result = load_paths(config, ('python',), {'cache': self.root / 'fallback'})
        self.assertEqual(Path(result['cache']), self.folder / 'local cache')

    def test_interactive_controller_and_worker_agree_after_move(self):
        config = self.config('interactive-config.json')
        with patch.object(interactive_voice, 'APP_DIR', self.root):
            session = interactive_voice.VoiceSession()
            self.addCleanup(session.end)
            controller = session.settings()
        audio = worker.load_settings(config)
        self.assertEqual(controller['model'], audio['model'])
        self.assertEqual(controller['speech'], audio['speech'])
        self.assertEqual(Path(audio['speech']), self.root / 'Speech')

    def test_existing_absolute_paths_still_work(self):
        model = self.folder / 'model'
        config = self.config('config.json', {'model': str(model)})
        self.assertEqual(load_paths(config, ('model',))['model'], str(model))

    def test_missing_runtime_and_invalid_path_values_fail_clearly(self):
        for value in ('missing.exe', '', None, [], True):
            with self.subTest(value=value):
                config = self.config('config.json', {'python': value})
                with self.assertRaises(ValueError):
                    load_paths(config, ('python',))

    def test_non_object_config_rejected_by_controller_and_worker(self):
        config = self.config('config.json', [])
        for load in (lambda: load_paths(config, ('model',)), lambda: worker.load_settings(config)):
            with self.assertRaisesRegex(ValueError, 'object'):
                load()


if __name__ == '__main__':
    unittest.main()
