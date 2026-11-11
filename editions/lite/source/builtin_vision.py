"""A fixed bundled vision pair, independent of the user's text-model choice."""
import json,os
from pathlib import Path
MODEL='DeepSeek-V4-Pro-Qwen3.5-9B-MTP-Q4_K_M.gguf'

def has_current_image(messages):
 if not isinstance(messages,(list,tuple)):return False
 return any(isinstance(m.get('content'),list) and any(isinstance(p,dict) and p.get('type')=='image_url' for p in m['content']) for m in messages[-12:] if isinstance(m,dict) and m.get('role')=='user')

def policy(app):
 root=Path(os.environ.get('YOEAI_ASSISTANT_RUNTIME',str(app)))
 cfg={'enabled':True,'selectable':False,'mode':'images','model':'Models/'+MODEL,'projector':'Models/mmproj-F32.gguf','context':8192}
 path=root/'Settings/vision.json'
 if path.is_file():cfg.update(json.loads(path.read_text(encoding='utf-8-sig')))
 cfg['model']=str((root/cfg['model']).resolve());cfg['projector']=str((root/cfg['projector']).resolve())
 return cfg

def describe(app):
 cfg=policy(app)
 return {'builtIn':True,'selectable':False,'available':Path(cfg['model']).is_file() and Path(cfg['projector']).is_file(),'model':MODEL,'loadPolicy':'automatic on image questions','mode':cfg['mode'],'verified':False}

def activate(app,home,read,vision=False,explicit=False):
 import lite_native
 base=read();cfg=policy(app);use_vision=bool(vision or cfg.get('mode')=='all')
 selected=dict(base,_builtinVisionRequest=use_vision)
 if use_vision:
  if not Path(cfg['model']).is_file() or not Path(cfg['projector']).is_file():raise ValueError('The built-in vision files are missing. Repair the YOEAI installation; no model choice is required.')
  selected.update(model=cfg['model'],projector=cfg['projector'],context=int(cfg.get('context',8192)),customModel=False)
 else:selected['projector']=''
 if lite_native.INSTANCE.state.get('manualUnloaded') and not use_vision and not explicit:raise ValueError('The text model is unloaded. Load it to resume text chat.')
 try:lite_native.start(app,home,lambda:selected)
 finally:
  # Other tools always continue to read the user's selected text configuration.
  lite_native.initialize(app,home,read)
 lite_native.INSTANCE.state['builtinVisionActive']=use_vision
 return use_vision
