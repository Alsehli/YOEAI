"""Native startup presentation, independent of the local web server."""
import math,time,json
from PySide6.QtCore import Qt,QTimer,QPointF,QRectF
from PySide6.QtGui import QPainter,QPixmap,QColor,QPen,QPainterPath
from PySide6.QtWidgets import QWidget,QVBoxLayout,QLabel,QProgressBar,QPushButton
from configuration import APP_DIR

class RunningMascot(QWidget):
 def __init__(self,parent=None):
  super().__init__(parent);self.setFixedSize(360,210)
  self.atlas=QPixmap(str(APP_DIR/'assets/mascot/fox-atlas.png'));self.rects=json.loads((APP_DIR/'assets/mascot/frames.json').read_text())['rows'][0] if (APP_DIR/'assets/mascot/frames.json').is_file() else None;self.started=time.monotonic();self.frames=0
  self.animation=QTimer(self);self.animation.timeout.connect(self.advance);self.animation.start(40)
 def advance(self):self.frames+=1;self.update()
 def paintEvent(self,event):
  t=time.monotonic()-self.started
  if not self.atlas.isNull():
   p=QPainter(self);p.setRenderHint(QPainter.SmoothPixmapTransform)
   frame=int(t*5)%8
   if self.rects:
    x,y,w,h=self.rects[frame];scale=min(190/h,220/w);dw=w*scale;dh=h*scale
    p.drawPixmap(QRectF(75+(256-dw)/2*210/256,(232-dh)*210/256,dw*210/256,dh*210/256),self.atlas,QRectF(x,y,w,h))
   else:
    w=self.atlas.width()/8;h=self.atlas.height()/4;p.drawPixmap(QRectF(75,0,210,210),self.atlas,QRectF(frame*w,0,w,h))
   return
  phase=t*7;stride=math.sin(phase)
  p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
  x=180+math.sin(t*.65)*55;bob=-abs(math.sin(phase))*3
  p.setPen(Qt.NoPen);p.setBrush(QColor('#202B3C'));p.drawEllipse(QPointF(x,195),48,5)
  p.translate(x,20+bob)
  cream=QColor('#FFF3DF');white=QColor('#FFFCF5');outline=QColor('#EBD8C0');pink=QColor('#F4B6B7')
  def shape(path,fill):p.setPen(QPen(outline,1.3));p.setBrush(fill);p.drawPath(path)
  tail=QPainterPath(QPointF(18,138));tail.cubicTo(78,155,84,91,50,94);tail.cubicTo(72,121,27,107,18,138);shape(tail,cream)
  # Opposite legs and arms alternate through a full walking gait.
  for side in [-1,1]:
   step=stride*side;hip=side*12;foot=hip+step*13;lift=max(step,0)*11
   p.setPen(QPen(outline,18,Qt.SolidLine,Qt.RoundCap));p.drawLine(QPointF(hip,138),QPointF(foot,170-lift))
   p.setPen(QPen(cream,15,Qt.SolidLine,Qt.RoundCap));p.drawLine(QPointF(hip,138),QPointF(foot,170-lift))
   p.setPen(QPen(outline,1));p.setBrush(white);p.drawEllipse(QPointF(foot,174-lift),13,8)
  p.setPen(QPen(outline,1.3));p.setBrush(cream);p.drawEllipse(-26,83,52,65)
  p.setPen(Qt.NoPen);p.setBrush(white);p.drawEllipse(-17,94,34,45)
  for side in [-1,1]:
   swing=-stride*side;start=QPointF(side*23,106);end=QPointF(side*(29+swing*11),137-swing*7)
   p.setPen(QPen(outline,13,Qt.SolidLine,Qt.RoundCap));p.drawLine(start,end)
   p.setPen(QPen(cream,10,Qt.SolidLine,Qt.RoundCap));p.drawLine(start,end)
   p.setPen(Qt.NoPen);p.setBrush(white);p.drawEllipse(end,7,8)
  # Flat vector fox head and large pink ears match the YOEAI mascot palette.
  for side in [-1,1]:
   ear=QPainterPath(QPointF(side*41,65));ear.cubicTo(side*73,25,side*61,-18,side*50,-10);ear.cubicTo(side*27,6,side*15,36,side*19,56);ear.closeSubpath();shape(ear,cream)
   inner=QPainterPath(QPointF(side*39,48));inner.cubicTo(side*58,21,side*55,-2,side*49,2);inner.cubicTo(side*34,16,side*29,34,side*29,47);inner.closeSubpath();p.setPen(Qt.NoPen);p.setBrush(pink);p.drawPath(inner)
  p.setPen(QPen(outline,1.3));p.setBrush(white);p.drawEllipse(-48,34,96,77)
  p.setPen(Qt.NoPen);p.setBrush(cream);p.drawEllipse(-43,38,86,43)
  tuft=QPainterPath(QPointF(-19,46));tuft.lineTo(-11,28);tuft.lineTo(-4,37);tuft.lineTo(6,25);tuft.lineTo(8,38);tuft.lineTo(19,32);tuft.lineTo(16,51);tuft.closeSubpath();p.setBrush(white);p.drawPath(tuft)
  for side in [-1,1]:
   eye=side*21;p.setBrush(QColor('#253047'));p.drawEllipse(QPointF(eye,73),13,17)
   p.setBrush(QColor('#2387EF'));p.drawEllipse(QPointF(eye,76),10,13)
   p.setBrush(QColor('#09234A'));p.drawEllipse(QPointF(eye,73),7,11)
   p.setBrush(QColor('#FFFFFF'));p.drawEllipse(QPointF(eye-4,66),4,5);p.drawEllipse(QPointF(eye+4,78),2,2)
   p.setBrush(QColor('#F9D5D0'));p.drawEllipse(QPointF(side*34,91),8,4)
  p.setBrush(QColor('#65463E'));p.drawEllipse(QPointF(0,90),5,3)
  p.setPen(QPen(QColor('#78544C'),1.8,Qt.SolidLine,Qt.RoundCap));mouth=QPainterPath(QPointF(-9,96));mouth.quadTo(0,104,9,96);p.drawPath(mouth)
  p.setPen(Qt.NoPen);p.setBrush(QColor('#285DAD'));p.drawRoundedRect(-21,107,42,9,4,4)
  p.setBrush(QColor('#4F8CFF'));p.drawEllipse(QPointF(0,116),9,9);p.setBrush(QColor('#DDF5FF'));p.drawEllipse(QPointF(0,116),4,4)

class LoadingScreen(QWidget):
 def __init__(self,parent=None):
  super().__init__(parent);self.setObjectName('startup-screen');self.setAttribute(Qt.WA_StyledBackground,True)
  self.setStyleSheet('#startup-screen{background:#0B0F19;color:#F8FAFC} QLabel{color:#94A3B8;background:transparent;font-family:Inter;font-size:15px} QLabel#loading-title{color:#F8FAFC;font-family:Manrope;font-size:32px;font-weight:600} QProgressBar{background:#202B3C;border:0;border-radius:3px;height:6px} QProgressBar::chunk{background:#4F8CFF;border-radius:3px} QPushButton{background:#4F8CFF;color:white;border:0;border-radius:10px;padding:12px 24px;font-family:Inter;font-size:14px}')
  layout=QVBoxLayout(self);layout.setAlignment(Qt.AlignCenter);layout.setSpacing(16)
  self.runner=RunningMascot();layout.addWidget(self.runner,0,Qt.AlignHCenter)
  title=QLabel('Starting YOEAI™');title.setObjectName('loading-title');title.setAlignment(Qt.AlignCenter);layout.addWidget(title)
  self.stage=QLabel('Preparing your private workspace…');self.stage.setAlignment(Qt.AlignCenter);self.stage.setWordWrap(True);self.stage.setFixedWidth(520);self.stage.setMinimumHeight(48);layout.addWidget(self.stage,0,Qt.AlignHCenter)
  self.progress=QProgressBar();self.progress.setRange(0,0);self.progress.setTextVisible(False);self.progress.setFixedSize(300,6);layout.addWidget(self.progress,0,Qt.AlignHCenter)
  self.note=QLabel('The first start can take longer while the AI loads.');self.note.setAlignment(Qt.AlignCenter);layout.addWidget(self.note)
  self.retry=QPushButton('Try again');self.retry.hide();layout.addWidget(self.retry,0,Qt.AlignHCenter)
 def message(self,text):self.stage.setText(text)
 def failed(self,text):
  self.message(text);self.progress.hide();self.runner.animation.stop();self.note.setText('Your models and conversations are safe.');self.retry.show()
 def restart(self):
  self.retry.hide();self.progress.show();self.runner.animation.start();self.note.setText('The first start can take longer while the AI loads.');self.message('Checking the local AI engine…')
