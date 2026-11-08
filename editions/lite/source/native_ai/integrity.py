"""Validate the version-paired runtime before loading any executable library."""
import hashlib,json
from pathlib import Path

def verify(directory):
 directory=Path(directory).resolve();manifest=directory/'runtime-manifest.json'
 if not manifest.is_file():raise ValueError('Native runtime integrity manifest is missing. Repair the installation.')
 data=json.loads(manifest.read_text(encoding='utf8'))
 if data.get('abi')!='llama.cpp-b11784-win-x64':raise ValueError('Unsupported native runtime ABI.')
 files=data.get('files',{})
 for required in ('llama.dll','ggml.dll','ggml-base.dll','mtmd.dll'):
  if required not in files:raise ValueError('Native runtime manifest is incomplete.')
 actual={p.name for p in directory.glob('*.dll')}
 if actual!={name for name in files if name.lower().endswith('.dll')}:raise ValueError('Unverified native libraries found in runtime directory.')
 for name,digest in files.items():
  if Path(name).name!=name:raise ValueError('Invalid native runtime manifest path.')
  path=directory/name
  if not path.is_file():raise ValueError('Required native runtime file is missing: '+name)
  h=hashlib.sha256()
  with path.open('rb') as stream:
   for chunk in iter(lambda:stream.read(8*1024*1024),b''):h.update(chunk)
  if h.hexdigest()!=digest:raise ValueError('Native runtime integrity check failed: '+name)
 return data
