import sys,unittest,queue,threading,io,tempfile,os
from pathlib import Path
from unittest.mock import patch,Mock
sys.path.insert(0,os.environ.get('YOEAI_AUDIT_SOURCE',str(Path(__file__).resolve().parents[1]/'source')))
from native_ai.manager import Manager
class RecoveryTests(unittest.TestCase):
 def test_failed_send_clears_busy(self):
  m=Manager();m.start=lambda:None;m.send=Mock(side_effect=BrokenPipeError('closed pipe'))
  with self.assertRaises(BrokenPipeError):list(m.request('status'))
  self.assertFalse(m.state['busy']);self.assertIn('closed pipe',m.state['error'])
 def test_close_cleans_up_when_cancel_pipe_is_broken(self):
  m=Manager();m.worker=Mock();m.worker.poll.return_value=1;m.worker.stdin=io.StringIO();m.worker.stdout=io.StringIO();m.log=io.StringIO();m.job=Mock();m.cancel=Mock(side_effect=BrokenPipeError('closed pipe'));worker=m.worker;job=m.job
  m.close();self.assertIsNone(m.worker);self.assertTrue(worker.stdin.closed);self.assertTrue(worker.stdout.closed);self.assertTrue(m.log.closed);job.close.assert_called_once();self.assertFalse(m.state['loaded'])
 def test_start_timeout_releases_worker(self):
  import configuration
  m=Manager();worker=Mock();worker.poll.return_value=None;worker.stdin=io.StringIO();worker.stdout=io.StringIO();messages=Mock();messages.get.side_effect=queue.Empty();job=Mock()
  with tempfile.TemporaryDirectory() as temp:
   with patch.object(configuration,'HOME',Path(temp)),patch('pathlib.Path.is_file',return_value=True),patch('native_ai.manager.subprocess.Popen',return_value=worker),patch('native_ai.manager.queue.Queue',return_value=messages),patch('native_ai.manager.threading.Thread'),patch('native_ai.process_job.WorkerJob',return_value=job):
    with self.assertRaisesRegex(RuntimeError,'initialize'):m.start()
   self.assertIsNone(m.worker);self.assertEqual(m.state['phase'],'error');self.assertFalse(m.state['busy']);self.assertTrue(worker.stdin.closed);job.close.assert_called_once()
if __name__=='__main__':unittest.main(verbosity=2)
