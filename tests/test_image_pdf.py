import sys,io,base64,json,unittest
from pathlib import Path
sys.path.insert(0,'F:/YOEAI-Autonomy/Source')
from PIL import Image
from pypdf import PdfReader
from PySide6.QtGui import QGuiApplication
from image_pdf import convert,run,JOBS
app=QGuiApplication.instance() or QGuiApplication([])
OUT=Path('F:/YOEAI-Autonomy/Reports/Image-PDF');OUT.mkdir(exist_ok=True)
def item(fmt='PNG',size=(640,400),orientation=None,multi=False):
 im=Image.new('RGB',size,'#1967df');im.paste('#ff6222',(0,0,size[0]//4,size[1]//4));b=io.BytesIO();opts={}
 if orientation:
  exif=im.getexif();exif[274]=orientation;opts['exif']=exif
 if multi:opts.update(save_all=True,append_images=[Image.new('RGB',(300,500),'green')])
 im.save(b,format=fmt,**opts);return {'name':'صورة.'+fmt.lower(),'data':base64.b64encode(b.getvalue()).decode()}
class Tests(unittest.TestCase):
 def test_formats(self):
  for fmt in ['JPEG','PNG','WEBP','BMP','TIFF']:
   data,pages=convert([item(fmt)]);self.assertEqual(len(PdfReader(io.BytesIO(data)).pages),1);self.assertEqual(len(pages),1)
 def test_multi_sizes_and_no_crop(self):
  for size in ['a4','letter','original']:
   data,pages=convert([item(size=(400,800)),item(size=(1600,200))],size)
   self.assertEqual(len(PdfReader(io.BytesIO(data)).pages),2)
   for p in pages:
    self.assertLessEqual(p['drawWidth'],p['width']+.001);self.assertLessEqual(p['drawHeight'],p['height']+.001)
    self.assertAlmostEqual(p['drawWidth']/p['drawHeight'],p['imageWidth']/p['imageHeight'])
 def test_orientation(self):
  _,pages=convert([item('JPEG',(600,300),6)]);self.assertEqual((pages[0]['imageWidth'],pages[0]['imageHeight']),(300,600))
 def test_tiff(self):
  data,p=convert([item('TIFF',multi=True)]);self.assertEqual(len(PdfReader(io.BytesIO(data)).pages),2)
 def test_large(self):
  data,p=convert([item(size=(5000,3500))]);self.assertEqual(p[0]['imageWidth'],5000)
 def test_bad(self):
  for items in [[],[{'data':'!!!'}],[item('GIF')]]:
   with self.assertRaises(ValueError):convert(items)
 def test_preview_and_arabic(self):
  JOBS['fixture']={'status':'running'};run('fixture',{'images':[item(),item('TIFF',multi=True)],'size':'a4'});j=JOBS['fixture'];self.assertEqual(j['status'],'ready',j);self.assertEqual(len(j['previews']),3)
  (OUT/'صور تجريبية.pdf').write_bytes(j['pdf']);(OUT/'preview.png').write_bytes(base64.b64decode(j['previews'][0].split(',')[1]));self.assertEqual(len(PdfReader(OUT/'صور تجريبية.pdf').pages),3)
if __name__=='__main__':unittest.main()
