"""Current YOEAI dictation failures must finish without stranding the UI."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('yoeai_current_dictation', ROOT / 'editions/lite/source/speech_input.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DictationFailureRecoveryTests(unittest.TestCase):
    def test_unwritable_output_finishes_and_next_job_can_succeed(self):
        with tempfile.TemporaryDirectory() as folder:
            service = module.Recognition(folder, folder)
            service.state = {'status': 'running'}
            with patch.object(Path, 'mkdir', side_effect=PermissionError('access denied')), patch.object(module.subprocess, 'Popen') as launch:
                service.run(b'fixture', 'en', Path('whisper.exe'), Path('model.bin'))
            launch.assert_not_called()
            self.assertEqual(service.status()['status'], 'error')
            self.assertIsNone(service.process)

            process = MagicMock()
            def complete(**kwargs):
                next(service.home.glob('*.wav')).with_suffix('.txt').write_text('Recovered transcript', encoding='utf8')
                return 0
            process.wait.side_effect = complete
            with patch.object(module.subprocess, 'Popen', return_value=process):
                service.run(b'fixture', 'en', Path('whisper.exe'), Path('model.bin'))
            self.assertEqual(service.status()['status'], 'complete')
            self.assertEqual(service.status()['text'], 'Recovered transcript')
            self.assertEqual(list(service.home.iterdir()), [])

    def test_cleanup_failure_attempts_all_job_files_and_finishes(self):
        with tempfile.TemporaryDirectory() as folder:
            service = module.Recognition(folder, folder)
            service.state = {'status': 'running'}
            with patch.object(module.subprocess, 'Popen', side_effect=OSError('worker unavailable')), patch.object(Path, 'unlink', side_effect=PermissionError('file locked')) as remove:
                service.run(b'fixture', 'en', Path('whisper.exe'), Path('model.bin'))
            self.assertEqual(remove.call_count, 3)
            self.assertEqual(service.status()['status'], 'error')
            self.assertIn('could not be removed', service.status()['message'])
            self.assertIsNone(service.process)

    def test_worker_failure_preserves_unrelated_profile_files(self):
        with tempfile.TemporaryDirectory() as folder:
            service = module.Recognition(folder, folder)
            service.home.mkdir()
            unrelated = service.home / 'user-notes.txt'
            unrelated.write_text('Keep this', encoding='utf8')
            with patch.object(module.subprocess, 'Popen', side_effect=OSError('worker unavailable')):
                service.run(b'fixture', 'en', Path('whisper.exe'), Path('model.bin'))
            self.assertEqual(service.status()['status'], 'error')
            self.assertEqual(unrelated.read_text(encoding='utf8'), 'Keep this')
            self.assertEqual(list(service.home.iterdir()), [unrelated])


if __name__ == '__main__':
    unittest.main()
