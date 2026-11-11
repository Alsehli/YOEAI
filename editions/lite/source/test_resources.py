import unittest
from unittest.mock import patch
from native_ai.resources import resources


class ResourceInventory(unittest.TestCase):
    @patch('native_ai.resources.subprocess.check_output', return_value='GPU A, 8192, 6144\nGPU B, 12288, 10240\n')
    def test_independent_gpu_memory(self, query):
        value = resources()
        self.assertEqual(len(value['gpus']), 2)
        self.assertEqual(value['gpu']['freeBytes'], 6144 * 1048576)
        self.assertFalse(value['gpuMemoryPooling'])
        self.assertGreater(value['ramTotalBytes'], 0)
        self.assertGreaterEqual(value['storageFreeBytes'], 0)

    @patch('native_ai.resources.subprocess.check_output', side_effect=FileNotFoundError)
    def test_cpu_only(self, query):
        value = resources()
        self.assertEqual(value['gpus'], [])
        self.assertIsNone(value['gpu'])


if __name__ == '__main__':
    unittest.main()
