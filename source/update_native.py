"""Native confirmation and GUI health broker, independent of generated web content."""
import threading,time,json
from PySide6.QtCore import QObject,Signal,Slot,Qt,QTimer
from PySide6.QtWidgets import QApplication,QMessageBox
INSTANCE=None
class Broker(QObject):
 requested=Signal(object)
 def __init__(self):
  super().__init__();app=QApplication.instance()
  if not app:raise ValueError('Native YOEAI window is required.')
  self.moveToThread(app.thread());self.requested.connect(self.dispatch,Qt.QueuedConnection)
 def request(self,kind,record,cancel=None):
  r={'kind':kind,'record':record,'cancel':cancel or threading.Event(),'done':threading.Event(),'result':False};self.requested.emit(r)
  if not r['done'].wait(110):r['cancel'].set();return False
  return r['result']
 @Slot(object)
 def dispatch(self,r):
  app=QApplication.instance();window=next((w for w in app.topLevelWidgets() if hasattr(w,'web') and w.isVisible()),None)
  if not window:r['record']['_approvalDecision']='No visible owned native YOEAI window; approval unavailable.';r['done'].set();return
  if r['kind']=='approve':
   record=r['record'];message=QMessageBox(window);message.setWindowTitle('YOEAI — Approve exact update');message.setTextFormat(Qt.PlainText);message.setIcon(QMessageBox.Warning);message.setText(record.get('operation','Deploy reviewed UI improvement')+'?');message.setInformativeText('Files:\n'+'\n'.join(x['path'] for x in record['files'])+'\n\nCandidate SHA-256:\n'+record['digest']+'\n\nOnly this candidate is approved. Recovery files will be preserved.');message.setDetailedText('\n\n'.join(x['diff'] for x in record['files']));message.setStandardButtons(QMessageBox.Yes|QMessageBox.No);message.setDefaultButton(QMessageBox.No)
   timer=QTimer(message);started=time.monotonic();timer.timeout.connect(lambda:message.reject() if r['cancel'].is_set() or time.monotonic()-started>90 else None);timer.start(150);answer=message.exec();r['result']=answer==QMessageBox.Yes and not r['cancel'].is_set();r['record']['_approvalDecision']='Approved' if r['result'] else 'Operation cancelled before native approval.' if r['cancel'].is_set() else 'Native approval dialog timed out.' if time.monotonic()-started>90 else 'User selected No or closed the native approval dialog.';timer.stop();message.deleteLater();r['done'].set();return
  # Reload the actual owned desktop UI, then evaluate a fixed trusted readiness probe.
  web=window.web;finished={'value':False}
  def done(success):
   if finished['value']:return
   if not success:finish(False);return
   web.page().runJavaScript("Boolean(document.getElementById('mini-nav') && window.MiniYoeUI && window.YoeMarkdown && ['prompt','mini-objective','wy-objective'].some(id=>{const e=document.getElementById(id);if(!e)return false;const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none';}))",restore_context)
  def finish(value):
   if finished['value']:return
   finished['value']=True
   try:web.loadFinished.disconnect(done)
   except RuntimeError:pass
   r['result']=bool(value);r['done'].set()
  def restore_context(healthy):
   if finished['value']:return
   if not healthy:finish(False);return
   state=getattr(self,'saved_context',{}) or {}
   payload=json.dumps(state)
   script="(()=>{const s="+payload+";for(const id of ['prompt','mini-objective']){const e=document.getElementById(id);if(e&&typeof s[id]==='string')e.value=s[id];}if(s.miniOpen&&window.MiniYoeUI){if(s.selected)MiniYoeUI.selectTask({id:s.selected,agent:s.agent||'update'});else MiniYoeUI.openAgent(s.agent||'update',false);}return true;})()"
   web.page().runJavaScript(script,lambda value:finish(bool(value)))
  def begin(state):
   if finished['value']:return
   if isinstance(state,str):
    try:state=json.loads(state)
    except ValueError:state=None
   if isinstance(state,dict) and state.get('valid'):self.saved_context=state
   from PySide6.QtWebEngineCore import QWebEnginePage
   web.loadFinished.connect(done);QTimer.singleShot(15000,lambda:finish(False));web.page().triggerAction(QWebEnginePage.ReloadAndBypassCache)
  web.page().runJavaScript("JSON.stringify((()=>{const s=window.MiniYoeUI?.snapshot();return {valid:!!document.getElementById('prompt'),prompt:document.getElementById('prompt')?.value||'','mini-objective':document.getElementById('mini-objective')?.value||'',miniOpen:document.body.classList.contains('mini-open'),agent:s?.agent,selected:s?.selected};})())",begin)
def broker():
 global INSTANCE
 if INSTANCE is None:INSTANCE=Broker()
 return INSTANCE
def approve(record,cancel):
 try:return broker().request('approve',record,cancel)
 except Exception:return False
def health():
 try:return broker().request('health',{})
 except Exception:return False

def install_stop(window):
 from PySide6.QtGui import QShortcut,QKeySequence
 shortcut=QShortcut(QKeySequence('Ctrl+Alt+Backspace'),window);shortcut.setContext(Qt.ApplicationShortcut)
 def stop():
  import update_routes,mini_agents
  if update_routes.INSTANCE is not None:update_routes.INSTANCE.stop()
  if mini_agents.INSTANCE is not None:
   for parent in mini_agents.INSTANCE.tasks():
    if parent.get('healthAudit'):parent['auditFollowupsStopped']=True;mini_agents.INSTANCE.save(parent)
   for task in mini_agents.INSTANCE.tasks():
    if (task['agent']=='update' or task.get('auditOrigin')) and task['status'] in {'QUEUED','PLANNING','RUNNING','WAITING_FOR_APPROVAL'}:mini_agents.INSTANCE.cancel(task['id'])
  window.statusBar().showMessage('Update YOE stopped. Background schedule disabled.',6000)
 shortcut.activated.connect(stop);window._update_stop_shortcut=shortcut
