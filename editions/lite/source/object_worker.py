"""One local TripoSR reconstruction; no remote inference or model substitution."""
import argparse,json,os,sys,time,types
from pathlib import Path

def event(message):print('OBJECT_STAGE '+message,flush=True)
def main(path):
 request=json.loads(path.read_text());assert request.get('executionAuthorized') is True
 root=Path(request['backendRoot']).resolve();output=Path(request['output']).resolve()
 if output.parent!=path.parent:raise ValueError('Output must remain in the job directory')
 os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',U2NET_HOME=str(root/'Models/Background'))
 sys.path.insert(0,str(root/'Dependencies'));sys.path.insert(0,str(root/'Source'))
 event('Loading TripoSR locally...')
 import numpy as np,torch,rembg
 from PIL import Image
 from skimage.measure import marching_cubes
 # Portable CPU surface extraction replaces only the optional native CUDA extension.
 adapter=types.ModuleType('torchmcubes')
 def surface(level,threshold):
  vertices,faces,_,_=marching_cubes(level.detach().cpu().numpy(),level=threshold)
  return torch.from_numpy(vertices[:,[2,1,0]].copy()),torch.from_numpy(faces.astype(np.int64))
 adapter.marching_cubes=surface;sys.modules['torchmcubes']=adapter
 from tsr.system import TSR
 import tsr.models.tokenizers.image as tokenizer
 tokenizer.hf_hub_download=lambda **kwargs:str(root/'Models/dino-config.json')
 from tsr.utils import remove_background,resize_foreground
 if not torch.cuda.is_available():raise RuntimeError('TripoSR requires the configured NVIDIA GPU in this installation')
 model=TSR.from_pretrained(str(root/'Models'),config_name='config.yaml',weight_name='model.ckpt').to('cuda:0').eval();model.renderer.set_chunk_size(8192)
 event('Removing the image background locally...')
 image=Image.open(request['image']).convert('RGBA');session=rembg.new_session('u2netp',providers=['CPUExecutionProvider']);image=resize_foreground(remove_background(image,session),.85)
 array=np.asarray(image).astype(np.float32)/255.;rgb=array[:,:,:3]*array[:,:,3:4]+(1-array[:,:,3:4])*.5;image=Image.fromarray((rgb*255).astype(np.uint8))
 event('Reconstructing the 3D object on the GPU...');started=time.monotonic()
 with torch.no_grad():scene=model([image],device='cuda:0')
 event('Extracting the colored mesh...')
 with torch.no_grad():mesh=model.extract_mesh(scene,has_vertex_color=True,resolution=256)[0]
 mesh.remove_unreferenced_vertices();mesh.fix_normals()
 if not len(mesh.faces) or not np.isfinite(mesh.vertices).all():raise RuntimeError('No usable mesh was reconstructed')
 event('Saving the GLB object...');mesh.export(str(output),file_type='glb');image.save(output.with_suffix('.poster.png'))
 output.with_suffix('.json').write_text(json.dumps({'vertices':len(mesh.vertices),'triangles':len(mesh.faces),'modelSeconds':round(time.monotonic()-started,2),'vertexColors':True,'model':'TripoSR','surfaceExtraction':'CPU marching cubes'}))

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--request',type=Path,required=True);main(parser.parse_args().request.resolve())
