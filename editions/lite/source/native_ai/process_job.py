"""Track only the private worker tree for bounded cleanup; no elevation."""
import psutil
class WorkerJob:
 def __init__(self,process):
  self.parent=psutil.Process(process.pid);self.processes=[self.parent]
 def refresh(self):
  if self.parent.is_running():
   for child in self.parent.children(recursive=True):
    if all(child.pid!=p.pid for p in self.processes):self.processes.append(child)
 def close(self):
  # psutil.is_running validates the recorded process creation time, so PID
  # reuse cannot target an unrelated process after the owned worker exits.
  for process in reversed(self.processes):
   try:
    if process.is_running():process.terminate()
   except psutil.NoSuchProcess:pass
  psutil.wait_procs(self.processes,timeout=5)
