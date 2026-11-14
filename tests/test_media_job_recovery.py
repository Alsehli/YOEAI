"""Failure injection for current YOEAI media jobs; no models or devices used."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

SOURCE = Path(__file__).resolve().parents[1] / 'editions/lite/source'


def load(name):
    spec = importlib.util.spec_from_file_location('recovery_' + name, SOURCE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


image = load('image_generation')
speech = load('lite_read_aloud')
dictation = load('speech_input')


class MediaJobRecoveryTests(unittest.TestCase):
    def check_launch_recovery(self, module, service, start):
        for failure in ('construct', 'start'):
            with self.subTest(failure=failure):
                service.state = {'status': 'idle'}
                thread = MagicMock()
                thread.is_alive.return_value = False
                if failure == 'start':
                    thread.start.side_effect = RuntimeError('cannot start new thread')
                with patch.object(module.threading, 'Thread', return_value=thread, side_effect=OSError('not enough resources') if failure == 'construct' else None):
                    with self.assertRaisesRegex(ValueError, 'could not start'):
                        start()
                self.assertEqual(service.status()['status'], 'error')
                retry = MagicMock()
                retry.is_alive.return_value = False
                with patch.object(module.threading, 'Thread', return_value=retry):
                    self.assertEqual(start()['status'], 'running')
                retry.start.assert_called_once()
                service.state = {'status': 'idle'}

    def test_image_thread_failure_allows_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            service = image.ImageGenerator(Path(folder) / 'config.json', Path(folder) / 'images')
            with patch.object(service, 'config', return_value={}):
                self.check_launch_recovery(image, service, lambda: service.start({'prompt': 'A tree'}))

    def test_read_aloud_thread_failure_allows_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(speech, 'APP_DIR', Path(folder)), patch.object(speech, 'HOME', Path(folder)):
                service = speech.SpeechJobs()
            with patch.object(Path, 'is_file', return_value=True):
                self.check_launch_recovery(speech, service, lambda: service.start('Hello', 1.0))

    def test_dictation_thread_failure_allows_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            service = dictation.Recognition(folder, folder)
            with patch.object(dictation, 'validate_audio', return_value=b'fixture'), patch.object(service, 'assets', return_value=(Path('worker.exe'), Path('model.bin'))):
                self.check_launch_recovery(dictation, service, lambda: service.start({'audio': 'fixture'}))

    def test_image_output_directory_failure_finishes_without_pausing_chat(self):
        with tempfile.TemporaryDirectory() as folder:
            pause, resume = MagicMock(), MagicMock()
            service = image.ImageGenerator(Path(folder) / 'config.json', Path(folder) / 'images', pause, resume)
            service.state = {'status': 'running'}
            with patch.object(Path, 'mkdir', side_effect=PermissionError('output access denied')), patch.object(image.subprocess, 'Popen') as launch:
                service.run({}, 'A tree', 512, 'a' * 32)
            self.assertEqual(service.status()['status'], 'error')
            self.assertIn('output access denied', service.status()['message'])
            launch.assert_not_called()
            pause.assert_not_called()
            resume.assert_not_called()
            self.assertIsNone(service.process)
            self.assertFalse((Path(folder) / 'generation.lock').exists())


if __name__ == '__main__':
    unittest.main()
