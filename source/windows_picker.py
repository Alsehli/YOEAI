"""Native, user-driven scope pickers; selections are not permissions by themselves."""
import threading
from pathlib import Path
from PySide6.QtCore import QObject,Signal,Slot
from PySide6.QtWidgets import QFileDialog
BROKER=None
class Picker(QObject):
 requested=Signal(object)
 def __init__(self,parent):super().__init__(parent);self.window=parent;self.requested.connect(self.choose)
 @Slot(object)
 def choose(self,job):
  if job['done'].is_set():return
  try:
   if job['kind']=='folder':
    value=QFileDialog.getExistingDirectory(self.window,'Choose a specific folder for Windows YOE')
    if value:
     from windows_policy import root_folder
     value=str(root_folder(value))
    job['value']={'folder':value or None}
   elif job['kind']=='reverse':
    values,_=QFileDialog.getOpenFileNames(self.window,'Choose software for local static analysis','','Software (*.exe *.dll *.js *.mjs *.cjs *.json *.asar *.gguf)')
    from reverse_yoe import register
    job['value']={'inputs':register(values) if values else []}
   else:
    from windows_policy import scoped_path,root_folder
    root=root_folder(job['folder'])
    if root is None:raise ValueError('Choose the approved folder first.')
    values,_=QFileDialog.getOpenFileNames(self.window,'Choose files inside the approved folder',str(root),'Supported files (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff *.pdf *.docx *.xlsx *.pptx *.txt *.md *.csv *.wav)')
    if len(values)>40:raise ValueError('Choose at most 40 files.')
    files=[]
    for value in values:
     try:relative=str(Path(value).resolve().relative_to(root))
     except ValueError:raise ValueError('Choose files inside the approved folder, or change the folder first.')
     scoped_path(root,relative);files.append(relative)
    job['value']={'files':files}
  except (ValueError,OSError) as ex:job['error']=str(ex)
  finally:job['done'].set()
def configure(parent):
 global BROKER
 BROKER=Picker(parent);return BROKER
def pick(kind,folder=None):
 if BROKER is None:raise ValueError('Use the YOEAI desktop app to choose files or a folder.')
 if kind not in ['folder','files','reverse']:raise ValueError('Choose files or a folder.')
 job={'kind':kind,'folder':folder,'done':threading.Event()};BROKER.requested.emit(job)
 if not job['done'].wait(120):job['done'].set();raise ValueError('Selection timed out. Please choose again.')
 if job.get('error'):raise ValueError(job['error'])
 return job['value']
