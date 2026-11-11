"""Read-only model readiness and measured hardware guidance. Never chooses or loads a model."""
import functools, math, ntpath, subprocess
from pathlib import Path

@functools.lru_cache(maxsize=1)
def hardware():
    try:
        text = subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.total','--format=csv,noheader,nounits'], text=True, timeout=3, creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        name, memory = text.splitlines()[0].rsplit(',',1)
        capacity = int(memory.strip())
        if capacity <= 0: raise ValueError('Invalid GPU memory')
        suggestion = 'Start with a Q4 model around 4–9B parameters.' if capacity < 15360 else 'Start with Fast 9B. Advanced models need additional memory checks.'
        return {'gpu':name.strip(), 'vramMiB':capacity, 'recommendation':suggestion+' Fit depends on context, quantization and other GPU use.'}
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        return {'gpu':None,'vramMiB':None,'recommendation':'GPU details are unavailable. Choose a compatible GGUF for your hardware; start small.'}

def describe(config, service, native, exists=None):
    model=config.get('model','')
    same=not native.get('model') or ntpath.normcase(ntpath.normpath(native['model']))==ntpath.normcase(ntpath.normpath(model))
    loaded=bool(native.get('loaded')) and same
    loading=bool(service.get('busy')) or native.get('phase')=='loading'
    # Do not stall status polling on storage while the engine is loading/using weights.
    available=None if loading or loaded else bool(model) and (exists(model) if exists else Path(model).is_file())
    error=service.get('error') or native.get('error')
    value=native.get('progress',0)
    progress=max(0,min(1,float(value))) if isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) else None
    if loading:
        stage=service.get('loadStage') or native.get('loadStage','initializing')
        label={'initializing':'Initializing local engine','weights':'Reading weights and transferring to memory / GPU','context':'Preparing context and checking compatibility'}.get(stage,'Preparing the selected model')
        elapsed=service.get('loadElapsedSeconds')
        clock=f' - {int(elapsed)}s elapsed' if isinstance(elapsed,(int,float)) and math.isfinite(elapsed) and elapsed>=0 else ''
        state,title,detail,action='loading','Loading your model',label+clock+'.',''
    elif loaded and native.get('error'):
        state,title,detail,action='error','Generation needs attention','The model is loaded, but its last request failed. Review the error or choose another model.','Review model'
    elif loaded:
        state,title,detail,action='ready','Ready to chat','Your selected model is running locally.','Start chatting'
        if service.get('error'):detail='Your previous model is available. Review the failed switch in Settings.'
    elif not available:
        state,title,detail,action='choose','Choose your AI model','Select an existing GGUF or use a model download link. If it is on an external drive, reconnect it.','Choose a model'
    elif error:
        state,title,detail,action='error','Your model needs attention','Open Settings to retry this model or choose another. Your conversations are preserved.','Review model'
    else:
        state,title,detail,action='idle','Your model is selected','Open Settings and load it when you are ready.','Load model'
    return {'state':state,'title':title,'detail':detail,'action':action,'loaded':loaded,'modelAvailable':available,'progress':progress,'error':str(error) if error else None}

MODEL_BASE='https://huggingface.co/Jackrong/DeepSeek-V4-Pro-Qwen3.5-9B-MTP-GGUF/resolve/99b43f206bfe6e4e4c311d8fe5bf9b3a9d06d08e/'
DOWNLOADS={'lite':MODEL_BASE+'DeepSeek-V4-Pro-Qwen3.5-9B-MTP-Q4_K_M.gguf','normal':MODEL_BASE+'DeepSeek-V4-Pro-Qwen3.5-9B-MTP-Q6_K.gguf','vision':MODEL_BASE+'mmproj-F32.gguf','catalog':'https://huggingface.co/models?library=gguf'}
def open_download(body):
    if not isinstance(body,dict) or body.get('confirmed') is not True or not isinstance(body.get('kind'),str) or body.get('kind') not in DOWNLOADS:
        raise ValueError('Choose a listed model link explicitly. No download was opened.')
    import webbrowser
    try:opened=webbrowser.open(DOWNLOADS[body['kind']])
    except (OSError,webbrowser.Error):raise ValueError('Windows could not open your browser. Please open Hugging Face manually.') from None
    if not opened:
        raise ValueError('Windows could not open your browser. Visit huggingface.co/models?library=gguf manually.')
    return {'opened':True}
