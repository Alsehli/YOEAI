"""Build a source-preview launcher without touching installed applications."""
import subprocess, sys, shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def main():
    subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--windowed','--onedir','--name','YOEAI','--icon',str(ROOT/'source/assets/yoeai.ico'),'--distpath',str(ROOT/'dist'),'--workpath',str(ROOT/'build'),'--specpath',str(ROOT),'--exclude-module','torch','--exclude-module','faster_whisper','--exclude-module','piper',str(ROOT/'source/customer.py')],cwd=ROOT,check=True)
    target=ROOT/'dist/YOEAI'
    for name in ['ui.html','manifest.json']:
        shutil.copy2(ROOT/'source'/name,target/name)
    shutil.copy2(ROOT/'LICENSE',target/'LICENSE')
    shutil.copytree(ROOT/'source/assets',target/'assets',dirs_exist_ok=True)
    print('Unsigned development build:',target/'YOEAI.exe')
    print('Model/backend/configuration and approved installation policies are not included.')
if __name__=='__main__':main()
