import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from kandinsky_video import VideoGenerator, memory_policy


class VideoLifecycle(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.restore = Mock()
        self.video = VideoGenerator(self.root/'config.json', self.root/'videos', pause=Mock(return_value=True), resume=self.restore)
        self.addCleanup(self.video.shutdown)
        self.cfg = {'testingAuthorized': True, 'gpuLock': str(self.root/'gpu.lock'), 'backendRoot': str(self.root), 'python': 'unused', 'worker': 'unused', 'ffmpeg': 'unused'}

    def test_authorization_gate_never_starts_worker(self):
        with patch.object(self.video, 'config', return_value={'testingAuthorized': False}), patch('kandinsky_video.subprocess.Popen') as spawn:
            with self.assertRaisesRegex(ValueError, 'authorization'):
                self.video.start({'prompt': 'A lighthouse', 'seconds': 5})
            spawn.assert_not_called()

    def test_invalid_duration_cannot_launch(self):
        with patch.object(self.video, 'config', return_value=self.cfg):
            for duration in (8, True, 0, '5'):
                with self.subTest(duration=duration), self.assertRaises(ValueError):
                    self.video.start({'prompt': 'A lighthouse', 'seconds': duration})

    def test_failure_restores_chat_and_preserves_user_video(self):
        self.video.home.mkdir(); historical=self.video.home/'historical.mp4'; historical.write_bytes(b'user video')
        with patch.object(self.video, 'select_gpu', side_effect=ValueError('No free GPU')):
            self.video.run(self.cfg, 'A lighthouse', 'a'*32, None)
        self.assertEqual(self.video.status()['status'], 'error')
        self.restore.assert_called_once_with(restore=True)
        self.assertFalse(Path(self.cfg['gpuLock']).exists())
        self.assertEqual(historical.read_bytes(), b'user video')

    def test_lock_conflict_does_not_remove_another_jobs_lock(self):
        lock=Path(self.cfg['gpuLock']); lock.write_text('other owner')
        self.video.run(self.cfg, 'A lighthouse', 'b'*32, None)
        self.assertEqual(self.video.status()['status'], 'error')
        self.assertEqual(lock.read_text(), 'other owner')
        self.video.pause.assert_not_called(); self.restore.assert_not_called()

    def test_gpu_selection_never_pools_memory(self):
        rows='0, GPU-A, RTX 3090, 24576, 14000\n1, GPU-B, RTX 5060 Ti, 16384, 15000\n'
        with patch('kandinsky_video.subprocess.check_output', return_value=rows):
            self.assertEqual(self.video.select_gpu(self.cfg)['uuid'], 'GPU-B')
            self.assertEqual(self.video.select_gpu(dict(self.cfg,gpuIndex=0))['uuid'], 'GPU-A')
            with self.assertRaises(ValueError):
                self.video.select_gpu(dict(self.cfg,minimumFreeMiB=20000))

    def test_low_host_ram_uses_nf4_without_bulk_pinning(self):
        policy=memory_policy({'totalMiB':24576},20*1024**3)
        self.assertEqual(policy,{'memoryProfile':'24gb','quantizedQwen':True,'pinMemory':False})
        self.assertFalse(memory_policy({'totalMiB':24576},80*1024**3)['quantizedQwen'])
        self.assertTrue(memory_policy({'totalMiB':16384},80*1024**3)['quantizedQwen'])

    def test_decode_phase_is_not_overwritten_by_last_denoising_step(self):
        self.video.home.mkdir();job='d'*32
        self.video.state={'id':job,'status':'running'}
        (self.video.home/(job+'.log')).write_text('Denoising: 100% 10/10\nKANDINSKY_EVENT {"stage":"decoding","message":"Decoding frames"}\n')
        self.assertEqual(self.video.status()['message'],'Decoding frames')

    def test_completed_metadata_uses_exported_dimensions(self):
        import struct
        job='f'*32
        gpu={'uuid':'GPU-A','name':'RTX 3090','totalMiB':24576}
        def execute(arguments, *args):
            if '--request' in arguments:
                (self.video.home/(job+'.kandinsky.partial.mp4')).write_bytes(b'fixture')
            elif '-frames:v' in arguments:
                (self.video.home/(job+'.poster.png')).write_bytes(b'\x89PNG\r\n\x1a\n'+b'\0'*8+struct.pack('>II',832,448))
            else:
                (self.video.home/(job+'.encoded.partial.mp4')).write_bytes(b'fixture')
        with patch.object(self.video,'select_gpu',return_value=gpu), patch.object(self.video,'execute',side_effect=execute):
            self.video.run(self.cfg,'A lighthouse',job,None)
        state=self.video.status()
        self.assertEqual(state['status'],'complete')
        self.assertEqual((state['width'],state['height']),(832,448))
        self.restore.assert_called_once_with(restore=True)

    def test_worker_failure_releases_resources_without_fallback(self):
        gpu={'uuid':'GPU-A','name':'RTX 3090','totalMiB':24576}
        with patch.object(self.video,'select_gpu',return_value=gpu), patch.object(self.video,'execute',side_effect=ValueError('worker failed')) as execute:
            self.video.run(self.cfg,'A lighthouse','c'*32,None)
        self.assertEqual(execute.call_count,1)
        self.assertEqual(self.video.status()['status'],'error')
        self.restore.assert_called_once_with(restore=True)
        self.assertFalse(Path(self.cfg['gpuLock']).exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
