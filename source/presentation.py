"""Same-origin visual assets only. All inference handlers remain unchanged."""
import mimetypes,json,hashlib,threading
from urllib.parse import unquote,urlsplit
import runtime
from configuration import APP_DIR,HOME
_asset_versions={}
_asset_lock=threading.Lock()

class PresentationHandler(runtime.Handler):
    def send_header(self,name,value):
        if name.lower()=='content-security-policy' and urlsplit(self.path).path=='/':
            from configuration import read_config
            value += "; frame-src 'self' http://localhost:"+str(read_config()['uiPort'])
        return super().send_header(name,value)
    def do_POST(self):
        from interactive_voice import route as interactive_route
        if interactive_route(self,True):return
        if self.path in ('/models/switch','/context','/imagegen/create','/videogen/create'):
            import speech_input
            voice=speech_input.INSTANCE
            if voice is not None and hasattr(voice,'release_idle'):
                if not self.allowed() or self.headers.get('Origin')!='http://'+self.headers.get('Host',''):
                    return self.json(403,{'error':'Use the local YOEAI interface.'})
                try:voice.release_idle()
                except ValueError as ex:return self.json(409,{'error':str(ex)})
        from speech_input import route as dictation_route
        if dictation_route(self,True):return
        from game_routes import route as game_route
        if game_route(self,True):return
        from windows_spelling import route as spell_route
        if spell_route(self,True):return
        from reverse_routes import route as reverse_route
        if reverse_route(self,True):return
        from writing_check import route as writing_route
        if writing_route(self,True):return
        from language_understanding import route as language_route
        if language_route(self,True):return
        from image_pdf import route as image_pdf_route
        if image_pdf_route(self,True):return
        from model_modes import route as models_route
        if models_route(self,True):return
        from research_pdf import route as report_route
        if report_route(self):return
        from code_preview import route as preview_route
        if preview_route(self,True):return
        from mini_agents import route as mini_route,shared_request
        if mini_route(self,True):return
        with shared_request(self) as ready:
            if ready:return self.existing_POST()

    def existing_POST(self):
        from vision_chat import route as vision_chat_route
        if vision_chat_route(self):return
        from video_generation_adapter import route as video_route
        if video_route(self,True):return
        from web_search import route as search_route
        if search_route(self,True,HOME):return
        from read_aloud import route as speech_route
        if speech_route(self,True):return
        from image_generation_adapter import route
        if route(self,True):return
        from configuration import read_config
        if self.path!='/context' or not read_config().get('externalBackend'):
            return super().do_POST()
        if not self.allowed() or self.headers.get('Origin')!=f"http://127.0.0.1:{read_config()['uiPort']}":
            return self.json(403,{'error':'Only the local Settings screen may restart this engine.'})
        try:
            if self.headers.get('Transfer-Encoding'):raise ValueError('Unsupported transfer encoding.')
            length=int(self.headers.get('Content-Length','-1'))
            if not 0<length<=512:raise ValueError('Invalid context request size.')
            body=json.loads(self.rfile.read(length))
            from model_modes import change_context
            return self.json(200,change_context(body.get('context'),body.get('confirmedEngineRestart')))
        except (ValueError,TypeError) as error:return self.json(400,{'error':str(error)})
        except Exception as error:return self.json(409,{'error':str(error)})

    def do_GET(self):
        from interactive_voice import route as interactive_route
        if interactive_route(self):return
        from speech_input import route as dictation_route
        if dictation_route(self):return
        from game_routes import route as game_route
        if game_route(self):return
        from reverse_routes import route as reverse_route
        if reverse_route(self):return
        from image_pdf import route as image_pdf_route
        if image_pdf_route(self):return
        from model_modes import route as models_route
        if models_route(self):return
        from code_preview import route as preview_route
        if preview_route(self):return
        from mini_agents import route as mini_route
        if mini_route(self):return
        from video_generation_adapter import route as video_route
        if video_route(self):return
        from web_search import route as search_route
        if search_route(self,False,HOME):return
        from read_aloud import route as speech_route
        if speech_route(self):return
        from image_generation_adapter import route
        if route(self):return
        route=unquote(urlsplit(self.path).path)
        if not route.startswith('/assets/'):
            return super().do_GET()
        if not self.allowed():
            return self.json(403,{'error':'Only the local interface may access this service.'})
        if route=='/assets/language-policy.js':
            from language_understanding import POLICY
            data=('window.YoeLanguagePolicy='+json.dumps(POLICY)+';').encode('utf-8')
            self.send_response(200);self.send_header('Content-Type','application/javascript; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data);return
        base=(APP_DIR/'assets').resolve()
        file=(APP_DIR/route.lstrip('/')).resolve()
        if not file.is_relative_to(base) or file.suffix.lower() not in {'.css','.js','.ttf','.svg','.png','.ico'} or not file.is_file():
            return self.json(404,{'error':'Visual asset not found'})
        stat=file.stat();signature=(stat.st_mtime_ns,stat.st_size)
        with _asset_lock:known=_asset_versions.get(file)
        etag=known[1] if known and known[0]==signature else None
        if etag and self.headers.get('If-None-Match')==etag:
            self.send_response(304);self.send_header('ETag',etag);self.send_header('Cache-Control','private, no-cache');self.end_headers();return
        data=file.read_bytes();etag='"'+hashlib.sha256(data).hexdigest()+'"'
        with _asset_lock:
            if len(_asset_versions)>512:_asset_versions.clear()
            _asset_versions[file]=(signature,etag)
        self.send_response(200)
        self.send_header('Content-Type',mimetypes.guess_type(str(file))[0] or 'application/octet-stream')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('ETag',etag)
        self.send_header('Cache-Control','private, no-cache')
        self.send_header('Content-Length',str(len(data)))
        self.end_headers()
        self.wfile.write(data)

def install_visual_assets():
    runtime.Handler=PresentationHandler
