import base64,io,tempfile,unittest,json
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from video_inputs import normalise_image
from video_generation import VideoGenerator

def photo(mode='RGB',size=(32,20),fmt='PNG',**kwargs):
 out=io.BytesIO();Image.new(mode,size,'red').save(out,format=fmt,**kwargs);return 'data:image/'+('jpeg' if fmt=='JPEG' else fmt.lower())+';base64,'+base64.b64encode(out.getvalue()).decode()

class VideoPhotoTests(unittest.TestCase):
 def test_formats(self):
  for fmt in ('JPEG','PNG','WEBP'):
   with Image.open(io.BytesIO(normalise_image(photo(fmt=fmt)))) as image:self.assertEqual(image.size,(32,20));self.assertEqual(image.mode,'RGB')
 def test_resize(self):
  with Image.open(io.BytesIO(normalise_image(photo(size=(2500,2000))))) as image:self.assertEqual(image.size,(1920,1536))
 def test_orientation(self):
  exif=Image.Exif();exif[274]=6
  with Image.open(io.BytesIO(normalise_image(photo(fmt='JPEG',exif=exif)))) as image:self.assertEqual(image.size,(20,32))
 def test_transparency(self):
  self.assertTrue(normalise_image(photo(mode='RGBA')).startswith(b'\x89PNG'))
 def test_invalid(self):
  for value in (None,{},'file:///private','data:image/png;base64,AAAA','data:image/svg+xml;base64,PHN2Zz4='):
   with self.assertRaises(ValueError):normalise_image(value)
 def test_pixel_limit(self):
  with self.assertRaisesRegex(ValueError,'25 million'):normalise_image(photo(size=(5100,5000)))
 def test_reuse_scoped_photo(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);config={'engine':'ltx','gpuLock':str(root/'lock')}
   for key in ('python','worker','ffmpeg','checkpoint','encoderIndex'):
    p=root/key;p.write_text('fixture');config[key]=str(p)
   path=root/'config.json';path.write_text(json.dumps(config));v=VideoGenerator(path,root/'outputs');v.home.mkdir();job='a'*32
   data=normalise_image(photo());(v.home/(job+'.input.png')).write_bytes(data)
   with patch('video_generation.threading.Thread') as thread:
    self.assertTrue(v.start({'prompt':'Animate the car','sourceJob':job})['imageToVideo']);self.assertEqual(thread.call_args.kwargs['args'][-1],data)
   v.worker=None;v.state['status']='idle'
   with self.assertRaisesRegex(ValueError,'Invalid source'):v.start({'prompt':'x','sourceJob':'../private'})
   with self.assertRaisesRegex(ValueError,'unavailable'):v.start({'prompt':'x','sourceJob':'b'*32})

if __name__=='__main__':unittest.main()
