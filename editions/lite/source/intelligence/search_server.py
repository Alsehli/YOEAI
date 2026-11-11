"""Private, lazy Windows SearXNG worker. No browser-accessible search app."""
import argparse,json,os,sys,secrets,types
from pathlib import Path

def private_app(app,port,token):
 def private(environ,start_response):
  allowed=environ.get('HTTP_HOST')=='127.0.0.1:'+str(port) and environ.get('HTTP_X_YOEAI_SEARCH_TOKEN')==token and not environ.get('HTTP_ORIGIN') and environ.get('REQUEST_METHOD')=='GET'
  if not allowed or environ.get('PATH_INFO') not in ('/search','/health'):
   start_response('403 Forbidden',[('Content-Type','text/plain'),('Content-Length','0')]);return [b'']
  if environ.get('PATH_INFO')=='/health':
   body=b'{"service":"YOEAI-private-searxng"}';start_response('200 OK',[('Content-Type','application/json'),('Content-Length',str(len(body)))]);return [body]
  environ.pop('HTTP_X_YOEAI_SEARCH_TOKEN',None)
  return app(environ,start_response)
 return private

def register_bundled_version(root):
 # Packaged snapshots must not require Git on the customer's Windows PATH.
 # Preserve upstream frozen metadata when present; otherwise label the snapshot honestly.
 if (Path(root)/'SearchRuntime/Runtime/searx/version_frozen.py').is_file():return
 name='searx.version_frozen'
 if name not in sys.modules:
  module=types.ModuleType(name)
  module.VERSION_STRING='bundled-snapshot-unversioned';module.VERSION_TAG='unknown';module.DOCKER_TAG='unknown'
  module.GIT_URL='https://github.com/searxng/searxng';module.GIT_BRANCH='unknown'
  sys.modules[name]=module

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);parser.add_argument('--home',type=Path,required=True);parser.add_argument('--port',type=int,required=True);args=parser.parse_args()
 root=args.root.resolve();home=args.home.resolve();home.mkdir(parents=True,exist_ok=True)
 sys.path[:0]=[str(root/'SearchRuntime/Runtime'),str(root/'SearchRuntime/Dependencies')]
 import yaml
 template=root/'SearchRuntime/settings.yml';settings=yaml.safe_load(template.read_text())
 settings.setdefault('server',{}).update(bind_address='127.0.0.1',port=args.port,secret_key=secrets.token_hex(32),limiter=False,public_instance=False,image_proxy=False)
 settings.setdefault('general',{}).update(debug=False,instance_name='YOEAI built-in research')
 settings.setdefault('search',{}).update(formats=['json'],safe_search=2)
 settings['valkey']={'url':False}
 config=home/'searxng-settings.yml';config.write_text(yaml.safe_dump(settings),encoding='utf8');os.environ['SEARXNG_SETTINGS_PATH']=str(config)
 os.environ['XDG_CONFIG_HOME']=str(home/'Config');os.environ['XDG_DATA_HOME']=str(home/'Data')
 if os.name=='nt':
  import asyncio
  asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
 register_bundled_version(root)
 from searx.webapp import app
 from waitress import serve
 token=os.environ['YOEAI_SEARCH_TOKEN']
 private=private_app(app,args.port,token)
 serve(private,host='127.0.0.1',port=args.port,threads=4,channel_timeout=20)

if __name__=='__main__':main()
