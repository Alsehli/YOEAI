"""Build a source-preview launcher without touching installed applications."""
import subprocess, sys, shutil, argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--native-runtime', type=Path, help='Existing verified b11784 runtime directory; never downloaded')
    args=parser.parse_args()
    if args.native_runtime:
        sys.path.insert(0,str(ROOT/'source'))
        from native_ai.integrity import verify
        verify(args.native_runtime)

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
    worker=[sys.executable,'-m','PyInstaller','--noconfirm','--console','--onedir','--name','YOEAI-Inference','--distpath',str(ROOT/'dist/worker'),'--workpath',str(ROOT/'build/worker'),'--specpath',str(ROOT),'--paths',str(ROOT/'source')]
    for name in ('torch','PySide6','numpy'): worker += ['--exclude-module',name]
    worker.append(str(ROOT/'source/native_worker_entry.py'))
    subprocess.run(worker,cwd=ROOT,check=True)
    shutil.copytree(ROOT/'dist/worker/YOEAI-Inference',target/'NativeEngine',dirs_exist_ok=True)
    if args.native_runtime:
        shutil.copytree(args.native_runtime,target/'NativeRuntime/b11784',dirs_exist_ok=True)
        shutil.copytree(ROOT/'build-inputs/Native-Licenses',target/'NativeRuntime/Licenses',dirs_exist_ok=True)
    print('Unsigned development build:' ,target/'YOEAI.exe')
    print('No model weights or private configuration included. Without --native-runtime this is a UI-only source preview.')
if __name__=='__main__':main()
