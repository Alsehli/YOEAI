import struct,json,sys,collections
from pathlib import Path
FORMATS={0:'B',1:'b',2:'H',3:'h',4:'I',5:'i',6:'f',7:'?',10:'Q',11:'q',12:'d'}
def inspect(path):
 p=Path(path);f=p.open('rb')
 def read(fmt):return struct.unpack('<'+fmt,f.read(struct.calcsize('<'+fmt)))[0]
 def string():
  n=read('Q')
  if n>100000000:raise ValueError('Invalid GGUF string length')
  return f.read(n).decode('utf8',errors='replace')
 def value(kind,keep=True):
  if kind in FORMATS:return read(FORMATS[kind])
  if kind==8:return string()
  if kind==9:
   element=read('I');n=read('Q')
   if n>10000000:raise ValueError('Invalid array size')
   if element in FORMATS and not keep:f.seek(struct.calcsize('<'+FORMATS[element])*n,1);return {'arrayLength':n,'type':element}
   result=[]
   for i in range(n):
    v=value(element,keep and n<100)
    if keep and n<100:result.append(v)
   return result if keep and n<100 else {'arrayLength':n,'type':element}
  raise ValueError('Unsupported GGUF metadata type '+str(kind))
 assert f.read(4)==b'GGUF','Not GGUF';version=read('I');assert version in [2,3]
 count=read('Q');kv=read('Q');metadata={}
 for _ in range(kv):
  key=string();kind=read('I');metadata[key]=value(kind,not key.startswith(('tokenizer.ggml.tokens','tokenizer.ggml.merges','tokenizer.ggml.token_type','tokenizer.ggml.scores')))
 tensors=[];types=collections.Counter();maximum=0;parameters=0
 for _ in range(count):
  name=string();nd=read('I');dims=[read('Q') for i in range(nd)];dtype=read('I');offset=read('Q');types[dtype]+=1;maximum=max(maximum,offset);parameters+=__import__('math').prod(dims)
  if name.startswith(('token_embd','output.','v.','mm.')):tensors.append({'name':name,'shape':dims,'type':dtype,'offset':offset})
 alignment=metadata.get('general.alignment',32);data_offset=(f.tell()+alignment-1)//alignment*alignment;assert data_offset+maximum<p.stat().st_size,'Truncated tensor data'
 f.close();return {'path':str(p),'sizeBytes':p.stat().st_size,'sizeGiB':round(p.stat().st_size/1024**3,3),'ggufVersion':version,'tensorCount':count,'parameterCount':parameters,'tensorTypes':dict(types),'metadata':metadata,'selectedTensors':tensors,'dataOffset':data_offset,'lastTensorOffset':maximum,'structuralCheck':'PASS; exact tensor byte-size verification also requires backend loading'}
if __name__=='__main__':
 records=[inspect(p) for p in sys.argv[1:]]
 out=Path(__file__).resolve().parents[1]/'Documents/Model-Modes/gguf-metadata.json';out.write_text(json.dumps(records,indent=2,ensure_ascii=False),encoding='utf8')
 for r in records:print(json.dumps({k:r[k] for k in ['path','sizeBytes','sizeGiB','ggufVersion','tensorCount','parameterCount','tensorTypes']},indent=2));print(json.dumps({k:v for k,v in r['metadata'].items() if not k.startswith('tokenizer.')},indent=2,ensure_ascii=True))

inspect_model=inspect