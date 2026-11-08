"""User-initiated local model changes; shared engine, existing task gate and rollback."""
import copy,json,threading,time,ntpath,functools
from pathlib import Path
from model_selection import selected_model

def atomic(path,value):
    path=Path(path);tmp=path.with_name(path.name+'.model-settings.tmp')
    tmp.write_text(json.dumps(value,indent=2),encoding='utf8');tmp.replace(path)

def recent_models(path,extra=()):
    try:items=json.loads(Path(path).read_text(encoding='utf8'))
    except (OSError,ValueError):items=[]
    if not isinstance(items,list):items=[]
    items=list(extra)+items;result=[];seen=set()
    for entry in items:
        if not isinstance(entry,dict) or not isinstance(entry.get('model'),str) or not entry['model']:continue
        if not isinstance(entry.get('projector',''),str):continue
        item={key:entry.get(key,'') for key in ('model','projector')}
        identity=tuple(ntpath.normcase(ntpath.normpath(item[key])) if item[key] else '' for key in ('model','projector'))
        if identity not in seen:seen.add(identity);result.append(item)
    return result[:12]

def choose_file():
    # Windows common file dialog runs on the calling request thread. No model can invoke it.
    import ctypes as C
    from ctypes import wintypes as W
    class OpenFile(C.Structure):
        _fields_=[('lStructSize',W.DWORD),('hwndOwner',W.HWND),('hInstance',W.HINSTANCE),('lpstrFilter',W.LPCWSTR),('lpstrCustomFilter',W.LPWSTR),('nMaxCustFilter',W.DWORD),('nFilterIndex',W.DWORD),('lpstrFile',W.LPWSTR),('nMaxFile',W.DWORD),('lpstrFileTitle',W.LPWSTR),('nMaxFileTitle',W.DWORD),('lpstrInitialDir',W.LPCWSTR),('lpstrTitle',W.LPCWSTR),('Flags',W.DWORD),('nFileOffset',W.WORD),('nFileExtension',W.WORD),('lpstrDefExt',W.LPCWSTR),('lCustData',W.LPARAM),('lpfnHook',C.c_void_p),('lpTemplateName',W.LPCWSTR),('pvReserved',C.c_void_p),('dwReserved',W.DWORD),('FlagsEx',W.DWORD)]
    buffer=C.create_unicode_buffer(32768);info=OpenFile();info.lStructSize=C.sizeof(info)
    info.lpstrFilter='GGUF model files\0*.gguf\0\0';info.lpstrFile=C.cast(buffer,W.LPWSTR);info.nMaxFile=len(buffer)
    info.lpstrTitle='Choose an existing local GGUF file';info.Flags=0x80000|0x1000|0x800|0x8
    dialog=C.WinDLL('comdlg32',use_last_error=True);dialog.GetOpenFileNameW.argtypes=[C.POINTER(OpenFile)];dialog.GetOpenFileNameW.restype=W.BOOL
    if dialog.GetOpenFileNameW(C.byref(info)):return buffer.value
    error=dialog.CommDlgExtendedError()
    if error:raise ValueError('Windows could not open the file picker (code '+str(error)+'). You can paste the full file path instead.')
    return None

class Service:
    def __init__(self,home,read,apply,gate,check):
        self.home=Path(home);self.read=read;self.apply_model=apply;self.gate=gate;self.check=check
        self.lock=threading.RLock();self.state={'busy':False,'phase':'idle','error':None,'rollback':None}
    def snapshot(self):
        with self.lock:value=copy.deepcopy(self.state)
        from native_ai.manager import INSTANCE as native
        value['progress']=native.state.get('progress',0)
        c=self.read()
        if not isinstance(c,dict) or not isinstance(c.get('model',''),str):raise ValueError('The saved model configuration is invalid. Restore its backup or choose a model again.')
        value.update(model=c.get('model',''),projector=c.get('projector',''),context=c.get('context'),name=Path(c.get('model','')).name)
        history=self.home/'model-library.json'
        value['recent']=recent_models(history)
        from model_experience import describe,hardware
        mode_state=self.mode_status() if hasattr(self,'mode_status') else {}
        if mode_state.get('busy'):value.update(busy=True,phase=mode_state.get('phase','loading'))
        if mode_state.get('error') and not value.get('error'):value['error']=mode_state['error']
        value['experience']=describe(c,value,dict(native.state))
        value['hardware']=hardware()
        from context_limits import model_info,capacity
        try:
            info=getattr(self,'context_info',None)
            if not value.get('busy') and native.state.get('phase')!='loading' and (not info or info.get('path')!=str(Path(c['model']))):
                info=model_info(c['model']);self.context_info=info;self.projector_bytes=Path(c['projector']).stat().st_size if c.get('projector') else 0
            if info:
                from native_ai.resources import resources
                if not value.get('busy') and (not hasattr(self,'budget_at') or time.monotonic()-self.budget_at>15):
                    self.budget=resources();self.budget_at=time.monotonic()
                budget=getattr(self,'budget',None)
                # Use the worker's measured pre-load free VRAM when a model already occupies it.
                if native.state.get('loaded') and native.state.get('loadMemory',{}).get('gpuMemoryBefore'):
                    budget={'gpu':native.state['loadMemory']['gpuMemoryBefore']}
                value['contextCapacity']=capacity(info,c.get('context'),native.state.get('context') if native.state.get('loaded') else None,budget,getattr(self,'projector_bytes',0))
                value['contextCapacity']['budgetScope']='Measured pre-load GPU snapshot' if native.state.get('loaded') else 'Available GPU snapshot; other applications can change it'
                value['contextCapacity']['loadMemory']=native.state.get('loadMemory')
                value['contextCapacity']['allocationMeasured']=bool(native.state.get('allocationMeasured'))
        except (OSError,ValueError,AssertionError,KeyError):pass
        return value
    def start(self,body):
        if not isinstance(body,dict):raise ValueError('Invalid model-settings request.')
        if body.get('confirmed') is not True:raise ValueError('Confirm loading the selected local model.')
        if not isinstance(body.get('model'),str) or not isinstance(body.get('projector',''),str):raise ValueError('Model and projector paths must be text.')
        choice=selected_model(body.get('model',''),body.get('projector',''))
        with self.lock:
            if self.state['busy']:raise ValueError('A model change is already in progress.')
            if not self.gate.acquire(blocking=False):raise ValueError('Finish or stop the active AI task or voice conversation before changing models.')
            try:
                self.check();previous=copy.deepcopy(self.read())
                if not isinstance(previous,dict):raise ValueError('The saved model configuration is invalid.')
            except Exception:self.gate.release();raise
            self.state.update(busy=True,phase='loading',error=None,rollback=None,warning=None,target=choice['model'])
        def work():
            try:
                self.apply_model(choice)
                self.context_info=None
                path=self.home/'model-library.json'
                try:atomic(path,recent_models(path,[choice,previous]))
                except OSError as error:
                    with self.lock:self.state['warning']='Model loaded, but recent selections could not be saved: '+str(error)
                with self.lock:self.state.update(phase='ready')
            except Exception as error:
                with self.lock:self.state.update(phase='error',error=str(error),rollback=getattr(error,'rollback',None))
            finally:
                with self.lock:self.state['busy']=False
                self.gate.release()
        try:threading.Thread(target=work,daemon=True,name='YOEAI-user-model-change').start()
        except Exception as error:
            with self.lock:self.state.update(busy=False,phase='error',error='Could not start the model-loading task: '+str(error))
            self.gate.release();raise ValueError(self.state['error']) from error
        return {'accepted':True,'model':choice['model']}

def phase_snapshot(modes):
    with modes.LOCK:return copy.deepcopy(modes.STATE)

class SwitchError(ValueError):pass
INSTANCE=None
_FACTORY_LOCK=threading.RLock()
def singleton_factory(function):
    @functools.wraps(function)
    def invoke(*args,**kwargs):
        with _FACTORY_LOCK:return function(*args,**kwargs)
    return invoke

@singleton_factory
def normal_service():
    global INSTANCE
    if INSTANCE is not None:return INSTANCE
    import model_modes as modes
    from configuration import HOME,CONFIG_FILE,read_config
    from mini_agents import GATE
    def check():
        modes.assert_idle()
        if modes.STATE['busy']:raise ValueError('Wait for the current model switch to finish.')
        import mini_agents
        if mini_agents.INSTANCE is not None and mini_agents.INSTANCE.running_id:raise ValueError('Finish or stop the current agent task first.')
    def apply(choice):
        old=read_config();catalog=copy.deepcopy(modes.catalog());was_loaded=modes.NATIVE.state['loaded']
        backup=HOME/'ModelChangeBackups'/str(time.time_ns());backup.mkdir(parents=True)
        atomic(backup/'config.json',old);atomic(backup/'model-modes.json',catalog)
        candidate=copy.deepcopy(catalog);candidate['custom']=dict(old,**choice,modelMode='custom');candidate['selected']='custom'
        modes.set_state(busy=True,phase='loading',target='custom',error=None)
        try:
            modes.stop_current();modes.load_native('custom',candidate);modes.atomic(modes.CATALOG,candidate)
            modes.set_state(phase='ready',detail='Selected local GGUF loaded. All workspaces share this model.',error=None)
        except Exception as failure:
            modes.NATIVE.close();modes.atomic(CONFIG_FILE,old);modes.atomic(modes.CATALOG,catalog)
            error=SwitchError('The selected model could not load: '+str(failure))
            try:
                if was_loaded:modes.load_native(old.get('modelMode','fast'),catalog)
                error.rollback='Previous configuration restored'+(' and model reloaded.' if was_loaded else '.')
            except Exception as restore:error.rollback='Previous configuration restored; reload failed: '+str(restore)
            modes.set_state(phase='error',error=str(error),detail=error.rollback);raise error from failure
        finally:modes.set_state(busy=False)
    INSTANCE=Service(HOME,read_config,apply,GATE,check);INSTANCE.mode_status=lambda:phase_snapshot(modes);return INSTANCE

@singleton_factory
def configure_lite(app,home,read):
    global INSTANCE
    if INSTANCE is not None:return INSTANCE
    import lite_native
    from mini_agents import GATE
    path=Path(home)/'profile.json'
    def check():
        if lite_native.INSTANCE.state['busy']:raise ValueError('Finish or stop the active AI response first.')
        import mini_agents
        if mini_agents.INSTANCE is not None and mini_agents.INSTANCE.running_id:raise ValueError('Finish or stop the current agent task first.')
    def apply(choice):
        old=read();was_loaded=lite_native.healthy();backup=Path(home)/'ModelChangeBackups'/str(time.time_ns());backup.mkdir(parents=True)
        atomic(backup/'profile.json',old)
        try:
            lite_native.stop();atomic(path,dict(old,**choice));lite_native.start(app,home,read)
        except Exception as failure:
            lite_native.stop();atomic(path,old);error=SwitchError('The selected model could not load: '+str(failure))
            try:
                if was_loaded:lite_native.start(app,home,read)
                error.rollback='Previous configuration restored'+(' and model reloaded.' if was_loaded else '.')
            except Exception as restore:error.rollback='Previous configuration restored; reload failed: '+str(restore)
            raise error from failure
    INSTANCE=Service(home,read,apply,GATE,check);return INSTANCE

def route(handler,post=False,service=None):
    if handler.path not in ('/local-models/state','/local-models/pick','/local-models/apply','/local-models/downloads'):return False
    reply=getattr(handler,'json',None) or handler.reply
    if not handler.allowed() or (post and handler.headers.get('Origin')!='http://'+handler.headers.get('Host','')):
        reply(403,{'error':'Use the local YOEAI Settings interface.'});return True
    try:
        service=service or normal_service()
        if not post and handler.path=='/local-models/state':value=service.snapshot()
        elif post and handler.path=='/local-models/pick':value={'path':choose_file()}
        elif post and handler.path in ('/local-models/apply','/local-models/downloads'):
            if handler.headers.get('Transfer-Encoding'):raise ValueError('Unsupported request encoding.')
            size=int(handler.headers.get('Content-Length','0'))
            if not 0<size<=32768:raise ValueError('Invalid model-settings request size.')
            body=json.loads(handler.rfile.read(size))
            if not isinstance(body,dict):raise ValueError('Invalid model-settings request.')
            if handler.path=='/local-models/downloads':
                from model_experience import open_download
                value=open_download(body)
            else:value=service.start(body)
        else:raise ValueError('Unsupported model-settings operation.')
        reply(200,value)
    except (ValueError,OSError) as error:reply(400,{'error':str(error)})
    return True
