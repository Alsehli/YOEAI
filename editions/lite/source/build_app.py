from pathlib import Path
import subprocess,sys
root=Path(__file__).resolve().parent.parent;s=root/'Source'
args=['--noconfirm','--onefile','--windowed','--name','YOEAILite','--version-file',str(s/'version-resource.txt'),'--icon',str(s/'yoeai.ico'),'--add-data',str(s/'ui.html')+';.','--add-data',str(s/'assets')+';assets','--distpath',str(root/'App-Dist'),'--workpath',str(root/'Build-App'),'--specpath',str(root),'--collect-submodules','ddgs','--collect-all','primp','--collect-all','lxml','--copy-metadata','ddgs','--copy-metadata','primp','--copy-metadata','lxml','--collect-all','playwright','--collect-submodules','pywinauto','--collect-submodules','comtypes','--collect-all','psutil','--exclude-module','torch','--exclude-module','PySide6',str(s/'app.py')]
subprocess.run([sys.executable,'-m','PyInstaller',*args],check=True)
