"""Offline, pinned LTX 2B distilled worker. Launched only by YOEAI's media gate."""
import argparse, gc, hashlib, json, os, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1')
sys.path.insert(0,str(ROOT))
sys.path.insert(0, str(ROOT/'Upstream/LTX-Video-4b2d053057623ddd4d0a1d3e9cd28890e9ef487f'))

def main():
 p=argparse.ArgumentParser();p.add_argument('--request',required=True);a=p.parse_args()
 r=json.loads(Path(a.request).read_text(encoding='utf8'));out=Path(r['output']);progress=out.with_suffix('.progress.json');started=time.monotonic();times={}
 def report(message,**extra):
  value={'message':message,'elapsed':round(time.monotonic()-started,2),**extra}
  tmp=progress.with_suffix('.tmp');tmp.write_text(json.dumps(value),encoding='utf8');os.replace(tmp,progress);print(json.dumps(value),flush=True)
 try:
  report('Loading LTX-Video on the local GPU…')
  import torch
  from ltx_video.inference import create_ltx_video_pipeline,load_image_to_tensor_with_resize_and_crop
  from ltx_video.pipelines.pipeline_ltx_video import ConditioningItem
  if not torch.cuda.is_available():raise RuntimeError('A compatible NVIDIA CUDA GPU is required.')
  torch.set_num_threads(6);torch.cuda.reset_peak_memory_stats();t=time.monotonic()
  pipe=create_ltx_video_pipeline(str(ROOT/'Models/ltxv-2b-0.9.6-distilled-04-25.safetensors'),'bfloat16',str(ROOT/'Models'),sampler='from_checkpoint',device='cpu',enhance_prompt=False)
  times['loading']=round(time.monotonic()-t,2);report('Understanding your video description…');t=time.monotonic()
  with torch.inference_mode():
   pipe.text_encoder.to('cuda')
   embeds,mask,neg,negmask=pipe.encode_prompt(r['prompt'],do_classifier_free_guidance=True,negative_prompt='',device=torch.device('cuda'))
   pipe.text_encoder.to('cpu');pipe.text_encoder=None;gc.collect();torch.cuda.empty_cache()
   times['encoding']=round(time.monotonic()-t,2)
   from bounded_decode import enable_bounded_decode
   if r['seconds']>3 or r['width']>640:enable_bounded_decode(pipe.vae,report)
   conditions=None
   if r.get('image'):
    photo=Path(r['image']).resolve()
    if photo!=out.with_suffix('.input.png').resolve() or not photo.is_file():raise ValueError('Invalid local source photo.')
    report('Preparing your photo for animation…')
    tensor=load_image_to_tensor_with_resize_and_crop(str(photo),r['height'],r['width'],just_crop=False)
    conditions=[ConditioningItem(tensor,0,1.0)]
   pipe.to('cuda');t=time.monotonic()
   def step(_pipe,i,_ts,_data):
    report(f'Creating video · step {i+1} of 8',step=i+1,steps=8)
    if i==7:times['sampling']=round(time.monotonic()-t,2);report('Decoding video frames…')
   result=pipe(conditioning_items=conditions,height=r['height'],width=r['width'],num_frames=r['seconds']*24+1,frame_rate=24,negative_prompt=None,prompt_embeds=embeds,prompt_attention_mask=mask,negative_prompt_embeds=neg,negative_prompt_attention_mask=negmask,num_inference_steps=8,guidance_scale=1,stg_scale=0,rescaling_scale=1,generator=torch.Generator(device='cuda').manual_seed(r['seed']),output_type='pt',decode_timestep=.05,decode_noise_scale=.025,stochastic_sampling=True,enhance_prompt=False,offload_to_cpu=True,callback_on_step_end=step,is_video=True,vae_per_channel_normalize=True)
   frames=(result.images[0].permute(1,2,3,0).cpu().float().clamp(0,1).numpy()*255).astype('uint8')[:r['seconds']*24]
  times['samplingAndDecode']=round(time.monotonic()-t,2);report('Saving MP4…')
  import imageio.v2 as imageio
  with imageio.get_writer(str(out),fps=24,codec='libx264',quality=8,macro_block_size=1,ffmpeg_log_level='error',output_params=['-pix_fmt','yuv420p','-movflags','+faststart']) as writer:
   for frame in frames:writer.append_data(frame)
  metrics={'engine':'LTX-Video 2B 0.9.6 distilled','imageToVideo':bool(r.get('image')),'sourceImageSHA256':hashlib.sha256(Path(r['image']).read_bytes()).hexdigest() if r.get('image') else None,'steps':8,'fps':24,'frames':len(frames),'phases':times,'totalSeconds':round(time.monotonic()-started,2),'peakAllocatedMiB':round(torch.cuda.max_memory_allocated()/1024**2),'peakReservedMiB':round(torch.cuda.max_memory_reserved()/1024**2),'promptSHA256':hashlib.sha256(r['prompt'].encode()).hexdigest(),'outputSHA256':hashlib.sha256(out.read_bytes()).hexdigest()}
  out.with_suffix('.metrics.json').write_text(json.dumps(metrics,indent=2),encoding='utf8');report('Video ready.',complete=True)
 except Exception as e:
  report('Video generation failed: '+str(e),error=True);raise

if __name__=='__main__':main()
