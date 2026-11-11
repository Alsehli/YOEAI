"""Bounded, local still-image preparation for LTX video jobs."""
import base64,io,re,warnings
from PIL import Image,ImageOps,UnidentifiedImageError

def normalise_image(value):
 if not isinstance(value,str) or len(value)>21*1024**2:raise ValueError('Choose a photo smaller than 15 MB.')
 match=re.fullmatch(r'data:image/(?:png|jpeg|jpg|webp|bmp|tiff);base64,([A-Za-z0-9+/=\r\n]+)',value)
 if not match:raise ValueError('Choose a JPG, PNG or WebP photo.')
 try:
  data=base64.b64decode(match[1],validate=True)
  if len(data)>15*1024**2:raise ValueError('Choose a photo smaller than 15 MB.')
  with warnings.catch_warnings():
   warnings.simplefilter('error',Image.DecompressionBombWarning)
   with Image.open(io.BytesIO(data)) as image:
    if image.width*image.height>25_000_000:raise ValueError('Choose a photo with at most 25 million pixels.')
    image=ImageOps.exif_transpose(image);image.thumbnail((1920,1920))
    if image.mode in ('RGBA','LA') or 'transparency' in image.info:
     rgba=image.convert('RGBA');canvas=Image.new('RGBA',rgba.size,'white');canvas.alpha_composite(rgba);image=canvas.convert('RGB')
    else:image=image.convert('RGB')
    output=io.BytesIO();image.save(output,format='PNG');return output.getvalue()
 except (UnidentifiedImageError,OSError,base64.binascii.Error,Image.DecompressionBombError,Image.DecompressionBombWarning) as error:
  raise ValueError('This photo could not be read. Choose a valid JPG, PNG or WebP image.') from error
