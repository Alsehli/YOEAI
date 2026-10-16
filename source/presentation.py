"""Same-origin visual assets only. All inference handlers remain unchanged."""
import mimetypes,json
from urllib.parse import unquote,urlsplit
import runtime
from configuration import APP_DIR

class PresentationHandler(runtime.Handler):
    def do_POST(self):
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
            from context_control import change_context
            return self.json(200,change_context(body.get('context'),body.get('confirmedEngineRestart')))
        except (ValueError,TypeError) as error:return self.json(400,{'error':str(error)})
        except Exception as error:return self.json(409,{'error':str(error)})

    def do_GET(self):
        route=unquote(urlsplit(self.path).path)
        if not route.startswith('/assets/'):
            return super().do_GET()
        if not self.allowed():
            return self.json(403,{'error':'Only the local interface may access this service.'})
        base=(APP_DIR/'assets').resolve()
        file=(APP_DIR/route.lstrip('/')).resolve()
        if not file.is_relative_to(base) or file.suffix.lower() not in {'.css','.js','.ttf','.svg','.png','.ico'} or not file.is_file():
            return self.json(404,{'error':'Visual asset not found'})
        data=file.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type',mimetypes.guess_type(str(file))[0] or 'application/octet-stream')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Length',str(len(data)))
        self.end_headers()
        self.wfile.write(data)

def install_visual_assets():
    runtime.Handler=PresentationHandler
