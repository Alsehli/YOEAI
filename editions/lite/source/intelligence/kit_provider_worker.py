"""Disposable Windows SearXNG AI Kit search; no cloud answer API or listener."""
import os,sys,json,asyncio,contextlib
from pathlib import Path
root=Path(os.environ['YOEAI_ASSISTANT_RUNTIME']).resolve()
sys.path[:0]=[str(root/'SearchRuntime/Dependencies'),str(root/'Vendor/searxng-ai-kit'),str(Path(__file__).resolve().parent.parent)]
os.environ['SEARXNG_SETTINGS_PATH']=str(root/'Settings/search.yml')
os.environ['XDG_CONFIG_HOME']=str(Path(os.environ['YOEAI_ASSISTANT_PROFILE'])/'Search/Config')
os.environ['XDG_DATA_HOME']=str(Path(os.environ['YOEAI_ASSISTANT_PROFILE'])/'Search/Data')
try:
    request=json.loads(sys.stdin.buffer.readline(8193))
    with contextlib.redirect_stdout(sys.stderr):
        import searxng,searxng.client as client
        from intelligence.public_reader import read
        async def local_fetch(url):
            value=await asyncio.to_thread(read,url);return dict(value,content=value['text'])
        client.fetch_url_content=local_fetch
        async def local_many(urls,max_concurrent=2):return [await local_fetch(url) for url in urls[:3]]
        client.fetch_multiple_urls_async=local_many
        if request['action']=='read':result=searxng.fetch_url(request['url'])
        elif request['action']=='search':
            from intelligence.automatic_web import public_query
            result=searxng.search(public_query(request['query']),engines=['brave','duckduckgo'],max_results=8,language=request.get('language','en'),safe_search=2)
        else:raise ValueError('Unsupported provider request.')
        if 'litellm' in sys.modules:raise RuntimeError('A remote AI library was imported unexpectedly.')
    print(json.dumps({'result':result},ensure_ascii=False),flush=True)
except Exception as error:print(json.dumps({'error':str(error)[:300]},ensure_ascii=False),flush=True);sys.exit(1)
