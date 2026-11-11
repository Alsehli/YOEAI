"""Existing /videogen interface, now backed exclusively by prepared Kandinsky."""
import json,os,re,sys,threading
from pathlib import Path
from kandinsky_video import ACTIVE,MODEL,VideoGenerator
INSTANCE=None
INIT=threading.Lock()

def generator(app,home,bundle,config):
 global INSTANCE
 with INIT:
  if INSTANCE is None:
   from lite_image_generation import instance
   images=instance(app,home,bundle,config)
   runtime=Path(os.environ.get('YOEAI_ASSISTANT_RUNTIME',str(app)))
   candidates=[runtime/'VideoGeneration/config.json']
   if not getattr(sys,'frozen',False):candidates.append(Path(__file__).resolve().parents[2]/'VideoGeneration/config.json')
   selected=next((p for p in candidates if p.is_file()),candidates[0])
   INSTANCE=VideoGenerator(selected,Path(home)/'GeneratedVideos',images.pause,images.resume,gpu_lock=images.config_path.parent/'generation.lock')
  return INSTANCE

def route(handler,post,app,home,bundle,config):
 path=handler.path.split('?',1)[0]
 if not path.startswith('/videogen/'):
  if post and INSTANCE and INSTANCE.status()['status'] in ACTIVE and path in ('/imagegen/create','/context','/v1/chat/completions','/local-models/apply'):
   handler.reply(409,{'error':'Video is using the GPU. Wait or press Stop.'});return True
  return False
 if not handler.allowed() or (post and handler.headers.get('Origin')!='http://'+handler.headers.get('Host','')):handler.reply(403,{'error':'Use the local YOEAI interface.'});return True
 try:
  gen=generator(app,home,bundle,config)
  if post:
   n=int(handler.headers.get('Content-Length','0'))
   if handler.headers.get('Transfer-Encoding') or not 0<n<=22*1024**2:raise ValueError('Invalid video request size.')
   handler.connection.settimeout(20);body=json.loads(handler.rfile.read(n))
   if not isinstance(body,dict):raise ValueError('Video request must be an object.')
   if path=='/videogen/create':value=gen.start(body)
   elif path=='/videogen/stop':value=gen.cancel()
   else:raise ValueError('Unknown video operation.')
  elif path=='/videogen/status':value=gen.status()
  elif path=='/videogen/models':
   c=gen.config();value={'ready':c.get('testingAuthorized') is True,'prepared':True,'verified':False,'model':MODEL,'seconds':[5],'audio':True,'testingAuthorizationRequired':c.get('testingAuthorized') is not True,'imageInput':'Animate an attached or generated image; text-to-video uses Kandinsky directly.'}
  elif path=='/videogen/license':
   file=Path(gen.config()['license']);data=file.read_bytes();handler.send_response(200);handler.send_header('Content-Type','text/plain; charset=utf-8');handler.send_header('X-Content-Type-Options','nosniff');handler.send_header('Content-Length',str(len(data)));handler.end_headers();handler.wfile.write(data);return True
  elif re.fullmatch('/videogen/(output|poster)/[0-9a-f]{32}',path):
   poster='/poster/' in path;file=gen.home/(path.rsplit('/',1)[-1]+('.poster.png' if poster else '.mp4'))
   if not file.is_file():raise ValueError('Video is unavailable.')
   size=file.stat().st_size;start=0;end=size-1;partial=False
   requested=handler.headers.get('Range') if not poster else None
   if requested:
    match=re.fullmatch(r'bytes=(\d*)-(\d*)',requested)
    if not match or not any(match.groups()):raise ValueError('Invalid video byte range.')
    first,last=match.groups()
    if first:start=int(first);end=min(int(last),size-1) if last else size-1
    else:start=max(0,size-int(last))
    if start>=size or start>end:
     handler.send_response(416);handler.send_header('Content-Range',f'bytes */{size}');handler.send_header('Content-Length','0');handler.end_headers();return True
    partial=True
   handler.send_response(206 if partial else 200);handler.send_header('Content-Type','image/png' if poster else 'video/mp4');handler.send_header('X-Content-Type-Options','nosniff');handler.send_header('Accept-Ranges','bytes');handler.send_header('Content-Length',str(end-start+1))
   if partial:handler.send_header('Content-Range',f'bytes {start}-{end}/{size}')
   handler.end_headers()
   with file.open('rb') as stream:
    stream.seek(start);remaining=end-start+1
    while remaining:
     data=stream.read(min(1024*1024,remaining))
     if not data:break
     handler.wfile.write(data);remaining-=len(data)
   return True
  else:handler.reply(404,{'error':'Unknown video endpoint.'});return True
  handler.reply(200,value)
 except (ValueError,KeyError,OSError,TypeError) as error:handler.reply(400,{'error':str(error)})
 return True
