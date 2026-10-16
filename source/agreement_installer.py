"""Agreement wrapper around the preserved installer worker."""
import sys
from configuration import APP_DIR,HOME
from installer import Worker
from setup_agreement import add_agreement,save_acceptance
from PySide6.QtWidgets import QApplication,QWidget,QVBoxLayout,QLabel,QPushButton,QPlainTextEdit
class SetupWindow(QWidget):
 def closeEvent(self,event):
  if getattr(self,'worker',None) and self.worker.isRunning():event.ignore()
  else:event.accept()
def create_setup_window(worker_factory=Worker,consent_recorder=save_acceptance):
 window=SetupWindow();window.setWindowTitle('YOEAI™ Setup');window.resize(860,730);layout=QVBoxLayout(window);layout.addWidget(QLabel('YOEAI™ · Review compatibility and policies before installation.'))
 button=QPushButton('Install preview');button.setObjectName('install-button');agreed,policy=add_agreement(layout,button,window,APP_DIR)
 output=QPlainTextEdit();output.setReadOnly(True);output.setMaximumHeight(130);layout.addWidget(output);layout.addWidget(button)
 def start():
  if not agreed.isChecked() or not policy.is_file():output.appendPlainText('Review the requirements and tick the agreement box before installing.');return
  try:consent_recorder(HOME,policy)
  except Exception as error:output.appendPlainText('Setup stopped: '+str(error));return
  button.setEnabled(False);agreed.setEnabled(False);window.worker=worker_factory();window.worker.message.connect(output.appendPlainText);window.worker.finished_result.connect(lambda ok:button.setText('Complete' if ok else 'Setup stopped — see details'));window.worker.start()
 button.clicked.connect(start);window.start_installation=start;window.agreement=agreed;window.install_button=button;return window
def main():
 app=QApplication(sys.argv);window=create_setup_window();window.show();sys.exit(app.exec())
