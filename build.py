"""Build a source-preview launcher without touching installed applications."""
import subprocess, sys, shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def main():
    command=[sys.executable,'-m','PyInstaller','--noconfirm','--windowed','--onedir','--name','YOEAI','--icon',str(ROOT/'source/assets/yoeai.ico'),'--distpath',str(ROOT/'dist'),'--workpath',str(ROOT/'build'),'--specpath',str(ROOT),'--exclude-module','torch','--exclude-module','faster_whisper','--exclude-module','piper']
    for name in ('ddgs','pywinauto','comtypes'):command += ['--collect-submodules',name]
    for name in ('primp','lxml','playwright','psutil'):command += ['--collect-all',name]
    for name in ('ddgs','primp','lxml'):command += ['--copy-metadata',name]
    command.append(str(ROOT/'source/customer.py'))
    subprocess.run(command,cwd=ROOT,check=True)
    target=ROOT/'dist/YOEAI'
    for name in ['ui.html','manifest.json','switch_context.ps1','stop_model.ps1','version.json']:
        shutil.copy2(ROOT/'source'/name,target/name)
    shutil.copy2(ROOT/'LICENSE',target/'LICENSE')
    shutil.copytree(ROOT/'source/assets',target/'assets',dirs_exist_ok=True)
    print('Unsigned development build:',target/'YOEAI.exe')
    print('Model/backend/configuration and approved installation policies are not included.')
if __name__=='__main__':main()
