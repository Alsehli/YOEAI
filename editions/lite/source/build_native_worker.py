"""Rebuild the private worker; reuse the package's qualified native DLLs."""
import subprocess,sys,shutil
from pathlib import Path
source=Path(__file__).resolve().parent;root=source.parent;out=root/'Worker-Build'
subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--console','--onedir','--name','YOEAI-Inference','--paths',str(source),'--distpath',str(out/'dist'),'--workpath',str(out/'work'),'--specpath',str(out),'--exclude-module','torch','--exclude-module','PySide6','--exclude-module','numpy',str(source/'native_worker_entry.py')],check=True)
shutil.copytree(out/'dist/YOEAI-Inference',root/'NativeEngine',dirs_exist_ok=True)
# Preserve app-local Microsoft runtimes already supplied with NativeEngine.
