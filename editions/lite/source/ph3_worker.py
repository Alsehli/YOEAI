"""Run one fixed, local-only ComfyUI P-H3 graph in an isolated child."""
import argparse,json,os,socket,subprocess,sys,time,urllib.request,shutil
from pathlib import Path

def graph(prompt,size,seed):
 def node(kind,**inputs):return {'class_type':kind,'inputs':inputs}
 return {
 '1':node('UNETLoader',unet_name='p-h3-image_w4a8.safetensors',weight_dtype='default'),
 '2':node('MiniMaxH3SigmaShift',model=['1',0],shift_video=1.0,shift_audio=1.0),
 '3':node('CLIPLoader',clip_name='p-h3-image_text_encoder_w4a8.safetensors',type='minimax',device='default'),
 '4':node('VAELoader',vae_name='p-h3-image_vae_int8_convrot.safetensors'),
 '5':node('CLIPLoader',clip_name='p-h3-image_prompt_upsampler_w4a8.safetensors',type='minimax',device='default'),
 '6':node('TextGenerate',clip=['5',0],prompt='Aspect ratio: 1:1\nRequest: '+prompt,max_length=2048,sampling_mode='off',thinking=True,use_default_template=True,mtp='off'),
 '7':node('PH3ImageConditioning',clip=['3',0],prompt=['6',0],width=size,height=size),
 '8':node('RandomNoise',noise_seed=seed),
 '9':node('BasicGuider',model=['2',0],conditioning=['7',0]),
 '10':node('KSamplerSelect',sampler_name='euler'),
 '11':node('ManualSigmas',sigmas='1.0, 0.984753, 0.967905, 0.951688, 0.925372, 0.881923, 0.810083, 0.528718, 0.0'),
 '12':node('SamplerCustomAdvanced',noise=['8',0],guider=['9',0],sampler=['10',0],sigmas=['11',0],latent_image=['7',1]),
 '13':node('VAEDecodeTiled',samples=['12',0],vae=['4',0],tile_size=512,overlap=64,temporal_size=8,temporal_overlap=4),
 '14':node('SaveImage',images=['13',0],filename_prefix='YOEAI-PH3')}

def main(request_path):
 request=json.loads(request_path.read_text());assert request.get('executionAuthorized') is True
 root=Path(request['backendRoot']).resolve();job=request_path.parent;output=Path(request['output']).resolve()
 if output.parent!=job:raise ValueError('Output must remain in its owned job directory')
 for name in ('render','input','user'):(job/name).mkdir(exist_ok=True)
 paths=job/'model-paths.yaml';paths.write_text('yoeai_ph3:\n  base_path: '+json.dumps(str(root/'Models'))+'\n  diffusion_models: diffusion_models\n  text_encoders: text_encoders\n  vae: vae\n')
 with socket.socket() as probe:probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
 base='http://127.0.0.1:'+str(port);http=urllib.request.build_opener(urllib.request.ProxyHandler({}))
 def api(path,body=None):
  req=urllib.request.Request(base+path,json.dumps(body).encode() if body is not None else None,{'Content-Type':'application/json'})
  with http.open(req,timeout=30) as r:return json.load(r)
 env=dict(os.environ,HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',PYTHONNOUSERSITE='1')
 args=[sys.executable,'-u',str(root/'ComfyUI/main.py'),'--listen','127.0.0.1','--port',str(port),'--disable-auto-launch','--disable-all-custom-nodes','--offline','--preview-method','none','--use-pytorch-cross-attention','--cache-none','--disable-dynamic-vram','--reserve-vram','1.5','--extra-model-paths-config',str(paths),'--output-directory',str(job/'render'),'--input-directory',str(job/'input'),'--user-directory',str(job/'user')]
 args+=['--disable-pinned-memory','--disable-async-offload']
 server=subprocess.Popen(args,env=env,stdin=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
 try:
  print('PH3_STAGE Loading the local P-H3-Image runtime...',flush=True)
  deadline=time.monotonic()+240
  while True:
   try:api('/system_stats');break
   except Exception:
    if server.poll() is not None:raise RuntimeError('P-H3 runtime exited during startup')
    if time.monotonic()>deadline:raise TimeoutError('P-H3 runtime startup timed out')
    time.sleep(1)
  result=api('/prompt',{'prompt':graph(request['prompt'],request['size'],request['seed']),'client_id':'yoeai-local'})
  if result.get('node_errors'):raise RuntimeError(str(result['node_errors']))
  key=result['prompt_id'];print('PH3_STAGE Creating your image with P-H3-Image (8 steps)...',flush=True)
  deadline=time.monotonic()+2400
  while time.monotonic()<deadline:
   if server.poll() is not None:raise RuntimeError('P-H3 runtime exited')
   history=api('/history/'+key).get(key)
   if history:
    if history.get('status',{}).get('status_str')=='error':raise RuntimeError(str(history['status'].get('messages'))[-2500:])
    images=history.get('outputs',{}).get('14',{}).get('images',[])
    if images:
     image=(job/'render'/images[0].get('subfolder','')/images[0]['filename']).resolve()
     if not image.is_relative_to((job/'render').resolve()):raise ValueError('Unexpected output path')
     shutil.copy2(image,output);print('PH3_STAGE Image exported; releasing GPU memory...',flush=True);return
   time.sleep(2)
  raise TimeoutError('P-H3 generation timed out')
 finally:
  server.terminate()
  try:server.wait(timeout=15)
  except subprocess.TimeoutExpired:server.kill();server.wait(timeout=10)

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--request',type=Path,required=True);main(parser.parse_args().request.resolve())
