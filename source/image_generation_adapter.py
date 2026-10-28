"""Normal-edition adapter. Pause only a backend owned by this YOEAI installation."""
import json,os,subprocess
from pathlib import Path
from image_generation import ImageGenerator,handle_request
from design_generation import DesignGenerator,ImageEngines,model_route
import runtime
from configuration import APP_DIR,HOME,read_config
INSTANCE=None;RESTORE=None

def pause_chat():
 global RESTORE
 from model_modes import pause_for_media
 RESTORE='selected' if pause_for_media() else None
 return bool(RESTORE)

def resume_chat():
 global RESTORE
 restore=RESTORE;RESTORE=None
 if restore:
  from model_modes import ensure_selected
  ensure_selected()

def generator():
 global INSTANCE
 if INSTANCE is None:
  candidates=[APP_DIR/'ImageGeneration/config.json',Path('F:/YOEAI-Image-Generation/config.json')]
  config=next((p for p in candidates if p.is_file()),candidates[0])
  turbo=ImageGenerator(config,config.parent/'Outputs',pause_chat,resume_chat,max_size=1024)
  design_config=config.parent/'Design/config.json'
  design=DesignGenerator(design_config,pause_chat,resume_chat,config.parent/'generation.lock')
  from precision_text import PrecisionEngines
  INSTANCE=PrecisionEngines(ImageEngines(turbo,design),HOME/'PrecisionText')
 return INSTANCE

def route(handler,post=False):
 if handler.path.startswith('/imagegen/'):
  engines=generator()
  from precision_text import precision_route
  if precision_route(handler,engines,post):return True
  if model_route(handler,engines,post):return True
  return handle_request(handler,engines,post)
 if post and handler.path in ('/context','/v1/chat/completions') and generator().status().get('status') in ('running','restoring'):
  handler.json(409,{'error':'Image generation is using the GPU. Wait for it to finish or stop the image job.'});return True
 return False
