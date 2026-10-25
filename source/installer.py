"""Per-user preview installer. Existing installations are never replaced."""
import hashlib,json,os,shutil,subprocess,sys,urllib.request,uuid,zipfile
from pathlib import Path
from configuration import APP_DIR,HOME,CONFIG_FILE
from PySide6.QtCore import QThread,Signal
from PySide6.QtWidgets import QApplication,QWidget,QVBoxLayout,QLabel,QPushButton,QPlainTextEdit

def digest(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()

def install(options,log):
    manifest=json.loads((APP_DIR/'manifest.json').read_text())
    final_target=HOME/'App'/'0.2.0-preview'
    if final_target.exists():raise RuntimeError('Preview installation already exists. It was preserved. Choose a new version before reinstalling.')
    shortcut=Path(os.environ['USERPROFILE'])/'Desktop'/'Alsehli AI Preview.lnk'
    if shortcut.exists():raise RuntimeError('An existing Preview shortcut was preserved. No installation or configuration was changed.')
    target=final_target.parent/('.staging-'+uuid.uuid4().hex)
    free=shutil.disk_usage(HOME).free
    required=2*1024**3 if options.get('models') else 14*1024**3
    if free<required:raise RuntimeError('Not enough free disk space for this installation.')
    log('Checking NVIDIA graphics…')
    gpu=subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.total,driver_version','--format=csv,noheader'],text=True,creationflags=subprocess.CREATE_NO_WINDOW)
    log(gpu.strip())
    if int(gpu.split(',')[1].strip().split()[0])<12000:raise RuntimeError('This preview requires an NVIDIA GPU with at least 12 GB VRAM.')
    paths={}
    for item in manifest['files']:
        category=item['category']
        if category!='models':raise RuntimeError('This text/image package must not contain audio-model downloads.')
        root=Path(options.get('models') or HOME/'Models')
        path=root/item['path'];path.parent.mkdir(parents=True,exist_ok=True)
        if not path.exists():
            part=path.with_suffix(path.suffix+'.part')
            log('Downloading '+item['path'])
            with urllib.request.urlopen(item['url'],timeout=60) as response,open(part,'wb') as output:
                shutil.copyfileobj(response,output,8*1024*1024)
            if part.stat().st_size!=item['size'] or digest(part)!=item['sha256']:raise RuntimeError('Download integrity failed: '+item['path'])
            part.rename(path)
        log('Verifying '+item['path'])
        if path.stat().st_size!=item['size'] or digest(path)!=item['sha256']:raise RuntimeError('Existing file does not match the verified source: '+str(path))
        paths[category]=str(root)
    log('Installing the desktop app…')
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copytree(APP_DIR,target)
    backend=target/'backend';backend.mkdir()
    for archive in manifest['runtime']:
        cache=HOME/'Downloads'/archive['name'];cache.parent.mkdir(exist_ok=True)
        if not cache.exists():
            partial=cache.with_suffix(cache.suffix+'.part')
            log('Downloading official CUDA runtime: '+archive['name'])
            with urllib.request.urlopen(archive['url'],timeout=60) as response,open(partial,'wb') as output:shutil.copyfileobj(response,output,8*1024*1024)
            if partial.stat().st_size!=archive['size'] or digest(partial)!=archive['sha256']:raise RuntimeError('CUDA archive integrity check failed. Partial download preserved for diagnosis.')
            partial.rename(cache)
        if cache.stat().st_size!=archive['size'] or digest(cache)!=archive['sha256']:raise RuntimeError('CUDA archive integrity check failed.')
        with zipfile.ZipFile(cache) as z:
            for member in z.infolist():
                resolved=(backend/member.filename).resolve()
                if not resolved.is_relative_to(backend.resolve()):raise RuntimeError('Unsafe archive path rejected.')
            z.extractall(backend)
    # Official releases may contain a single enclosing directory.
    servers=list(backend.rglob('llama-server.exe'))
    if len(servers)!=1:raise RuntimeError('Expected exactly one llama-server executable.')
    if servers[0].parent!=backend:
        for file in servers[0].parent.iterdir():
            if file.is_file():shutil.copy2(file,backend/file.name)
    config=dict(model=str(Path(paths['models'])/manifest['files'][0]['path']),projector=str(Path(paths['models'])/'mmproj-F32.gguf'),apiPort=8080,uiPort=8085,context=16384,externalBackend=bool(options.get('externalBackend',False)))
    target.rename(final_target)
    target=final_target.resolve()
    ps="$s=(New-Object -ComObject WScript.Shell).CreateShortcut('"+str(shortcut).replace("'","''")+"');$s.TargetPath='"+str(target/'AlsehliAI.exe').replace("'","''")+"';$s.WorkingDirectory='"+str(target).replace("'","''")+"';$s.Save()"
    subprocess.run(['powershell','-NoProfile','-Command',ps],check=True,creationflags=subprocess.CREATE_NO_WINDOW)
    CONFIG_FILE.write_text(json.dumps(config,indent=2))
    report=dict(status='PASS',app=str(target/'AlsehliAI.exe'),gpu=gpu.strip(),verifiedFiles=len(manifest['files']),config=config)
    (HOME/'installation-result.json').write_text(json.dumps(report,indent=2))
    log('Setup complete. Use the Alsehli AI Preview desktop shortcut.')
    return report

class Worker(QThread):
    message=Signal(str);finished_result=Signal(bool)
    def run(self):
        try:
            path=os.environ.get('ALSEHLI_SETUP_TEST_CONFIG')
            options=json.loads(Path(path).read_text()) if path else {}
            install(options,self.message.emit);self.finished_result.emit(True)
        except Exception as e:
            self.message.emit('SETUP FAILED: '+str(e));(HOME/'installation-error.txt').write_text(str(e));self.finished_result.emit(False)

def main():
    app=QApplication(sys.argv);window=QWidget();window.setWindowTitle('Alsehli AI — Preview Setup');window.resize(650,420)
    layout=QVBoxLayout(window);layout.addWidget(QLabel('Alsehli AI • Bahraini.online\nLocal, private AI with text and image understanding.\nSetup downloads the model and vision projector. NVIDIA 12 GB+ and 14 GB free disk space required.'))
    output=QPlainTextEdit();output.setReadOnly(True);layout.addWidget(output)
    button=QPushButton('Install preview');layout.addWidget(button);worker=Worker()
    worker.message.connect(output.appendPlainText)
    def start():button.setEnabled(False);worker.start()
    button.clicked.connect(start)
    worker.finished_result.connect(lambda ok: app.exit(0 if ok else 1) if os.environ.get('ALSEHLI_SETUP_TEST_CONFIG') else button.setText('Complete' if ok else 'Setup failed — see details'))
    window.show()
    if os.environ.get('ALSEHLI_SETUP_TEST_CONFIG'):start()
    sys.exit(app.exec())
