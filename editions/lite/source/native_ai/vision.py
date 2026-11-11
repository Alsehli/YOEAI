"""Version-matched mtmd vision adapter. Image bytes stay inside the private worker."""
import base64,ctypes as C,io,os
from PIL import Image,ImageOps
from .libllama import P,I,U,B,Progress
class Params(C.Structure):
 _fields_=[('use_gpu',B),('device',P),('print_timings',B),('n_threads',I),('image_marker',C.c_char_p),('media_marker',C.c_char_p),('flash_attn_type',I),('warmup',B),('image_min_tokens',I),('image_max_tokens',I),('cb_eval',P),('cb_eval_user_data',P),('batch_max_tokens',I),('progress_callback',Progress),('progress_callback_user_data',P)]
class Text(C.Structure):_fields_=[('text',C.c_char_p),('text_len',C.c_size_t),('add_special',B),('parse_special',B)]
class Vision:
 def __init__(self,engine,projector):
  self.engine=engine;self.dll=C.CDLL(str(engine.lib.directory/'mtmd.dll'));self.ctx=None
  def bind(name,restype,args):
   f=getattr(self.dll,'mtmd_'+name);f.restype=restype;f.argtypes=args;setattr(self,name,f)
  for name,restype,args in [('context_params_default',Params,[]),('init_from_file',P,[C.c_char_p,P,Params]),('free',None,[P]),('default_marker',C.c_char_p,[]),('support_vision',B,[P]),('bitmap_init',P,[U,U,C.c_char_p]),('bitmap_free',None,[P]),('input_chunks_init',P,[]),('input_chunks_free',None,[P]),('tokenize',I,[P,P,C.POINTER(Text),C.POINTER(P),C.c_size_t]),('helper_get_n_tokens',C.c_size_t,[P]),('helper_eval_chunks',I,[P,P,P,I,I,I,B,C.POINTER(I)])]:bind(name,restype,args)
  p=self.context_params_default();p.use_gpu=False;p.n_threads=min(8,os.cpu_count()or 4);p.warmup=False;p.image_min_tokens=256;p.image_max_tokens=1024
  self.ctx=self.init_from_file(os.fsencode(projector),engine.model,p)
  if not self.ctx:raise ValueError('The native vision projector could not initialize.')
  if not self.support_vision(self.ctx):self.close();raise ValueError('The installed projector does not support vision.')
 def close(self):
  if self.ctx:self.free(self.ctx);self.ctx=None
 def prepare(self,messages):
  images=[];clean=[];marker=self.default_marker().decode()
  for m in messages:
   content=m.get('content');value=''
   if isinstance(content,list):
    for part in content:
     if part.get('type')=='text':value+=part.get('text','')
     elif part.get('type')=='image_url':
      url=part.get('image_url',{}).get('url','')
      if not url.startswith(('data:image/png;base64,','data:image/jpeg;base64,','data:image/webp;base64,','data:image/bmp;base64,')):raise ValueError('Native vision accepts attached local image data only.')
      raw=base64.b64decode(url.split(',',1)[1],validate=True)
      if len(raw)>20000000:raise ValueError('Attached image exceeds the native size limit.')
      images.append(raw);value+=marker
     else:raise ValueError('Unsupported native message attachment.')
   elif isinstance(content,str):value=content
   else:raise ValueError('Invalid native message content.')
   clean.append({**m,'content':value})
  if not 1<=len(images)<=4:raise ValueError('Use one to four images per native request.')
  return clean,images
 def evaluate(self,prompt,images,limit,cancel):
  bitmaps=[];chunks=None
  try:
   for raw in images:
    if cancel and cancel.is_set():raise InterruptedError('Vision stopped.')
    with Image.open(io.BytesIO(raw))as source:
     if source.width*source.height>40000000:raise ValueError('Attached image dimensions exceed the safety limit.')
     image=ImageOps.exif_transpose(source).convert('RGB');image.thumbnail((1536,1536));bitmap=self.bitmap_init(image.width,image.height,image.tobytes())
    if not bitmap:raise ValueError('Native image decoding failed.')
    bitmaps.append(bitmap)
   chunks=self.input_chunks_init();data=prompt.encode();text=Text(data,len(data),True,True);array=(P*len(bitmaps))(*bitmaps)
   code=self.tokenize(self.ctx,chunks,C.byref(text),array,len(array))
   if code:raise ValueError('Vision tokenization failed (code '+str(code)+').')
   count=self.helper_get_n_tokens(chunks)
   if count+limit>self.engine.context:raise ValueError('Images and output exceed the selected model context.')
   if cancel and cancel.is_set():raise InterruptedError('Vision stopped.')
   past=I();code=self.helper_eval_chunks(self.ctx,self.engine.ctx,chunks,0,0,256,True,C.byref(past))
   if code:raise ValueError('Native vision evaluation failed (code '+str(code)+').')
   return count
  finally:
   if chunks:self.input_chunks_free(chunks)
   for bitmap in bitmaps:self.bitmap_free(bitmap)
