"""Explicit local GGUF selection. Never copies, renames or downloads weights."""
from pathlib import Path
from gguf_metadata import inspect_model

def selected_model(value, projector=''):
    from security_paths import user_local_path
    path=user_local_path(value).resolve()
    if path.is_dir():
        candidates=[]
        for item in path.glob('*.gguf'):
            if item.name.lower().startswith(('mmproj','projector')):continue
            candidates.append(item)
        if len(candidates)!=1:
            raise ValueError('This folder contains '+str(len(candidates))+' possible models. Select the exact .gguf file using Choose model.')
        path=candidates[0]
    if not path.is_file() or path.suffix.lower()!='.gguf':
        raise ValueError('Select an existing .gguf model file. Reconnect its drive if necessary.')
    try:info=inspect_model(path)
    except Exception as error:raise ValueError('The selected GGUF is incomplete or invalid: '+str(error)) from error
    meta=info['metadata'];arch=meta.get('general.architecture','')
    if not arch or not meta.get(arch+'.block_count') or not any(t['name']=='token_embd.weight' for t in info['selectedTensors']):
        raise ValueError('Select a language model, not an image model or vision projector.')
    if int(meta.get('split.count',1))>1:
        raise ValueError('Split GGUF sets are not supported by this setup yet. Select a complete single-file model.')
    vision=''
    if projector:
        vision_path=user_local_path(projector).resolve()
        if not vision_path.is_file() or vision_path==path:raise ValueError('Select a separate compatible vision projector, or leave it blank for text only.')
        try:inspect_model(vision_path)
        except Exception as error:raise ValueError('Invalid vision projector: '+str(error)) from error
        vision=str(vision_path)
    return {'model':str(path),'projector':vision,'architecture':arch,'modelBytes':info['sizeBytes'],
            'validation':'GGUF structure checked; native runtime compatibility is checked on first model load',
            'customModel':True}
