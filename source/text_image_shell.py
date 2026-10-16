"""Local text and image desktop shell. No audio recording or playback."""
import argparse,os,sys,subprocess,json,shutil,time
from pathlib import Path
os.environ.setdefault('QTWEBENGINE_CHROMIUM_FLAGS','--disable-gpu --disable-gpu-compositing')
from PySide6.QtCore import QUrl,QThread,Signal,Slot,QTimer
from PySide6.QtGui import QDesktopServices,QIcon,QFont,QFontDatabase
from PySide6.QtWidgets import QApplication,QMainWindow,QMessageBox,QStackedWidget,QFileDialog
from PySide6.QtWebEngineCore import QWebEnginePage,QWebEngineProfile,QWebEngineUrlRequestInterceptor
from PySide6.QtWebEngineWidgets import QWebEngineView
from configuration import APP_DIR,HOME,read_config
from commands import propose,execute_confirmed
from loading_screen import LoadingScreen
LEGACY=APP_DIR==Path('C:/AI/Apps/AlsehliAI-0.1.2')
PORT=8082 if LEGACY else read_config()['uiPort']
def startup_trace(stage,**details):
 (HOME/'desktop-startup-state.json').write_text(json.dumps(dict(stage=stage,time=time.time(),**details),indent=2))
def ensure_legacy_services():
 from runtime import HTTP,healthy
 if not healthy(8080):
  subprocess.run(['powershell.exe','-NoProfile','-File','C:/AI/llama.cpp/start-deepseek.ps1'],check=True,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
 try:
  with HTTP.open('http://127.0.0.1:8082/status',timeout=5) as response:status=json.load(response)
 except Exception:
  node=shutil.which('node.exe')
  if not node:raise RuntimeError('The local interface is unavailable and Node.js could not be found.')
  subprocess.Popen([node,'C:/AI/llama.cpp/local-ui.js'],cwd='C:/AI/llama.cpp',stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
  for _ in range(30):
   try:
    with HTTP.open('http://127.0.0.1:8082/status',timeout=2) as response:status=json.load(response)
    break
   except Exception:time.sleep(.5)
  else:raise RuntimeError('The local chat interface did not become ready.')
 expected=json.loads(Path('C:/AI/llama.cpp/model-config.json').read_text(encoding='utf-8-sig'))['model']
 if status.get('status')!='ok' or Path(status.get('model',''))!=Path(expected):raise RuntimeError('The local interface is not serving your configured model.')
class LocalOnly(QWebEngineUrlRequestInterceptor):
 def interceptRequest(self,info):
  u=info.requestUrl()
  if not(u.scheme() in {'data','blob','qrc','about'} or (u.scheme()=='http' and u.host()=='127.0.0.1' and u.port()==PORT)):info.block(True)
class LocalPage(QWebEnginePage):
 def acceptNavigationRequest(self,u,kind,main):
  if u.toString()=='about:blank':return True
  if kind==QWebEnginePage.NavigationType.NavigationTypeLinkClicked and (u.scheme() in {'https','http'} and bool(u.host()) and u.host()!='127.0.0.1' or u.toString()=='mailto:hello@bahraini.online'):QDesktopServices.openUrl(u);return False
  return u.scheme()=='http' and u.host()=='127.0.0.1' and u.port()==PORT
class Startup(QThread):
 ready=Signal();failed=Signal(str);progress=Signal(str)
 def run(self):
  try:
   startup_trace('checking_services',legacy=LEGACY,port=PORT)
   if LEGACY:
    ensure_legacy_services()
   else:
    from runtime import ensure_engine,start_ui,healthy
    from presentation import install_visual_assets
    install_visual_assets()
    self.progress.emit('Checking the local AI engine…')
    starter=os.environ.get('YOEAI_ENGINE_STARTER')
    if starter and read_config().get('externalBackend') and not healthy(read_config()['apiPort']):
     self.progress.emit('Loading the AI model and vision support…')
     if not Path(starter).is_file():raise RuntimeError('The existing engine launcher is missing: '+starter)
     startup_log=HOME/'launcher-startup.log'
     with startup_log.open('w',encoding='utf-8') as output:
      result=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',starter,'-Context',str(int(read_config().get('context',4096)))],stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,text=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=240)
     if result.returncode:raise RuntimeError('The AI engine could not start. '+startup_log.read_text(encoding='utf-8',errors='replace')[-1200:])
    self.progress.emit('Preparing the local chat interface…')
    ensure_engine();start_ui()
   startup_trace('services_ready',port=PORT);self.ready.emit()
  except Exception as e:startup_trace('startup_failed',error=str(e));self.failed.emit(str(e))
class TextImageWindow(QMainWindow):
 def __init__(self,start_services=True):
  super().__init__();self.setWindowTitle('YOEAI™');self.setMinimumSize(640,480);self.resize(1440,960);self.setWindowIcon(QIcon(str(APP_DIR/'assets/yoeai.ico')))
  self.stack=QStackedWidget(self);self.setCentralWidget(self.stack);self.loading=LoadingScreen();self.stack.addWidget(self.loading)
  if start_services:self.show();QApplication.processEvents()
  self.web=QWebEngineView(self);self.stack.addWidget(self.web)
  self.ready_poll=QTimer(self);self.ready_poll.setInterval(200);self.ready_poll.timeout.connect(self.check_chat_ready)
  self.ready_deadline=0
  self.profile=QWebEngineProfile('DeepSeekDesktop',self)
  self.profile.downloadRequested.connect(self.save_visual_download)
  data=Path(os.environ['LOCALAPPDATA'])/'DeepSeekDesktop' if LEGACY else HOME/'UserData'
  self.profile.setPersistentStoragePath(str(data/'web-profile'));self.profile.setCachePath(str(data/'web-cache'))
  self.interceptor=LocalOnly(self);self.profile.setUrlRequestInterceptor(self.interceptor);self.page=LocalPage(self.profile,self.web);self.web.setPage(self.page)
  menu=self.menuBar().addMenu('Windows commands')
  for label,phrase in [('Notepad','open notepad'),('Calculator','open calculator'),('File Explorer','open file explorer'),('Settings','open settings'),('Documents','open documents'),('Desktop','open desktop')]:
   action=menu.addAction('Open '+label);action.triggered.connect(lambda checked=False,p=phrase:self.command(p))
  self.statusBar().showMessage('Starting local text and image interface…')
  self.web.loadFinished.connect(self.page_loaded)
  settings=self.menuBar().addMenu('Settings');developer=settings.addAction('Developer Mode — custom GGUF models…')
  def open_developer():
   from developer_mode import launch
   launch(Path(__file__).parent/'customer.py')
  developer.triggered.connect(open_developer)
  self.worker=Startup(self);self.worker.ready.connect(self.services_ready);self.worker.failed.connect(self.startup_failed);self.worker.progress.connect(self.loading.message)
  self.loading.retry.clicked.connect(self.retry_startup)
  if start_services:self.worker.start()
 @Slot()
 def services_ready(self):
  startup_trace('opening_chat',port=PORT);self.statusBar().showMessage('Opening chat…');self.web.setUrl(QUrl(f'http://127.0.0.1:{PORT}/'))
 @Slot(str)
 def startup_failed(self,error):
  self.ready_poll.stop();self.stack.setCurrentWidget(self.loading);self.loading.failed(error);self.statusBar().showMessage('Startup failed — see the message above.')
 @Slot(bool)
 def page_loaded(self,success):
  startup_trace('chat_loaded' if success else 'chat_failed',url=self.web.url().toString())
  if success:self.ready_deadline=time.monotonic()+60;self.ready_poll.start();self.check_chat_ready()
  else:self.startup_failed('Chat could not load. Check that the local service is available.')
 def check_chat_ready(self):
  if time.monotonic()>self.ready_deadline:
   self.startup_failed('The chat took too long to become ready. Try again or check the startup logs.');return
  self.page.runJavaScript("document.getElementById('status')?.textContent==='Ready' && !!document.getElementById('send')",self.chat_ready)
 def chat_ready(self,ready):
  if ready and self.ready_poll.isActive():
   self.ready_poll.stop();self.loading.runner.animation.stop();self.stack.setCurrentWidget(self.web);self.statusBar().showMessage('Ready — local text and image chat');startup_trace('chat_ready',url=self.web.url().toString())
 def retry_startup(self):
  if self.worker.isRunning():return
  self.loading.restart();self.ready_poll.stop();self.worker.start()
 def command(self,phrase):
  action=propose(phrase)
  if action:execute_confirmed(action,lambda p:QMessageBox.question(self,'Confirm Windows action',p.label+'?',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes)
 def save_visual_download(self,request):
  name=request.downloadFileName();extension=Path(name).suffix.lower()
  if request.url().scheme()!='blob' or extension not in {'.svg','.png','.pdf'}:request.cancel();return
  target,_=QFileDialog.getSaveFileName(self,'Save generated file',str(Path.home()/'Downloads'/name),'PDF documents (*.pdf)' if extension=='.pdf' else 'PDF documents (*.pdf)' if extension=='.pdf' else 'PDF documents (*.pdf)' if extension=='.pdf' else 'Images (*.png *.svg)')
  if not target:request.cancel();return
  path=Path(target)
  if path.suffix.lower()!=extension:path=path.with_suffix(extension)
  request.setDownloadDirectory(str(path.parent));request.setDownloadFileName(path.name);request.accept()
 def closeEvent(self,event):
  if self.worker.isRunning():event.ignore();self.statusBar().showMessage('Wait for startup before closing.')
  else:event.accept()
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--smoke-test',action='store_true');parser.add_argument('--screenshot');args=parser.parse_args()
 application=QApplication(sys.argv);application.setApplicationName('YOEAI')
 for font in (APP_DIR/'assets/fonts').glob('*.ttf'):QFontDatabase.addApplicationFont(str(font))
 ui_font=QFont('Inter');ui_font.setPixelSize(14);application.setFont(ui_font)
 application.setStyleSheet('QMenuBar,QMenu,QStatusBar { background: #101725; color: #94A3B8; border: none; padding: 4px; } QMenu::item:selected,QMenuBar::item:selected {background: #202B3C; color: #F8FAFC;}')
 window=TextImageWindow(not args.smoke_test)
 if args.smoke_test:
  menus=[action.text() for action in window.menuBar().actions()]
  assert menus==['Windows commands','Settings'],menus
  assert 'desktop' not in sys.modules and 'speech_worker' not in sys.modules
  (HOME/'text-image-shell-test.json').write_text(json.dumps(dict(status='PASS',menus=menus,scope='Native shell construction without starting inference; recording/playback modules absent.'),indent=2));window.close();return
 window.show();sys.exit(application.exec())
