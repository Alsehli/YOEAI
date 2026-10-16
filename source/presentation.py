"""Same-origin visual assets only. All inference handlers remain unchanged."""
import mimetypes
from urllib.parse import unquote,urlsplit
import runtime
from configuration import APP_DIR

class PresentationHandler(runtime.Handler):
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
