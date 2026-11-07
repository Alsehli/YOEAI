"""One desktop window/model manager per user profile; private activation IPC."""
import hashlib
from PySide6.QtCore import QLockFile
from PySide6.QtNetwork import QLocalServer,QLocalSocket
class SingleInstance:
 def __init__(self,home):
  self.window=None;self.server=None;self.name='YOEAI-'+hashlib.sha256(str(home.resolve()).casefold().encode()).hexdigest()[:24]
  self.lock=QLockFile(str(home/'desktop-native.lock'));self.lock.setStaleLockTime(0)
 def acquire(self):
  if not self.lock.tryLock(100):
   socket=QLocalSocket();socket.connectToServer(self.name)
   if socket.waitForConnected(1500):socket.write(b'activate');socket.waitForBytesWritten(1000);socket.disconnectFromServer()
   return False
  self.server=QLocalServer();self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
  if not self.server.listen(self.name):self.lock.unlock();raise RuntimeError('The private desktop activation channel could not initialize.')
  self.server.newConnection.connect(self.activate);return True
 def activate(self):
  while self.server.hasPendingConnections():
   socket=self.server.nextPendingConnection();socket.close();socket.deleteLater()
  if self.window:self.window.showNormal();self.window.raise_();self.window.activateWindow()
