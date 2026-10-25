"""Normal-only local video adapter; reuse the existing verified chat ownership checks."""
from pathlib import Path
from configuration import APP_DIR,HOME
from video_generation import VideoGenerator,handle_request,ACTIVE
import image_generation_adapter as images
INSTANCE=None
def generator():
 global INSTANCE
 if INSTANCE is None:
  candidates=[APP_DIR/'VideoGeneration/config.json',Path('C:/AI/YOEAI-Video-LTX/config.json'),Path('F:/YOEAI-Video-Generation/config.json')];path=next((p for p in candidates if p.is_file()),candidates[0]);INSTANCE=VideoGenerator(path,Path('C:/AI/YOEAI-Video-LTX/Outputs') if path.is_file() and 'YOEAI-Video-LTX' in path.read_text(encoding='utf-8-sig') else path.parent/'Outputs',images.pause_chat,images.resume_chat)
 return INSTANCE
def route(handler,post=False):
 path=handler.path.split('?',1)[0]
 if post and path=='/videogen/create' and images.generator().status().get('status') in ('running','restoring'):
  if not handler.allowed():handler.json(403,{'error':'Only the local YOEAI screen may access this service.'});return True
  handler.json(409,{'error':'An image is using the GPU. Wait for it to finish or stop it.'});return True
 if path.startswith('/videogen/'):return handle_request(handler,generator(),post)
 if post and path in ('/context','/v1/chat/completions','/imagegen/create') and generator().state.get('status') in ('running','restoring'):
  if not handler.allowed():handler.json(403,{'error':'Only the local YOEAI screen may access this service.'});return True
  handler.json(409,{'error':'Video creation is active. Wait for it to finish, or stop the video job.'});return True
 return False
