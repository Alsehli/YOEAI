"""Bound peak decoder memory using overlapping causal latent windows.

The installed causal VAE has eight output frames per latent interval.
Each new window carries three latent frames (24 output frames) of context.
Only the new tail is retained. No upscaler or extra model is involved.
"""
import types

def enable_bounded_decode(vae,progress=None):
 original=vae.decode
 def decode(self,z,return_dict=True,target_shape=None,timestep=None):
  if z.shape[2]<=5:return original(z,return_dict=return_dict,target_shape=target_shape,timestep=timestep)
  import torch
  from diffusers.models.autoencoders.vae import DecoderOutput
  factor=int(self.temporal_downscale_factor);parts=[];covered=0;expected=min(target_shape[2],(z.shape[2]-1)*factor+1)
  for start in range(0,z.shape[2]-1,2):
   stop=min(start+5,z.shape[2]);shape=list(target_shape);shape[2]=(stop-start-1)*factor+1
   if progress:progress('Decoding video frames · '+str(min(start*factor+shape[2],expected))+' / '+str(expected))
   value=original(z[:,:,start:stop],return_dict=False,target_shape=shape,timestep=timestep)[0]
   offset=max(0,covered-start*factor);tail=value[:,:,offset:]
   if tail.shape[2]:parts.append(tail);covered=start*factor+value.shape[2]
   del value
   if stop==z.shape[2]:break
  # The upstream target uses latent_count * factor; causal decoding emits
  # (latent_count - 1) * factor + 1 real frames, including its first frame.
  expected=min(target_shape[2],(z.shape[2]-1)*factor+1)
  result=torch.cat(parts,dim=2)[:,:,:expected]
  if result.shape[2]!=expected:raise RuntimeError('Video decoder returned an incomplete frame sequence.')
  return DecoderOutput(sample=result) if return_dict else (result,)
 vae.decode=types.MethodType(decode,vae)

