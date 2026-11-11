"""Explicit local selections and confined relative names; never accepts network/device roots."""
import os,re,string
from pathlib import Path

def segments(value):
 if not isinstance(value,str) or not value or len(value)>32700:raise ValueError('Use a bounded local path.')
 result=[]
 for item in re.split(r'[\\/]',value):
  if not item or item=='.':continue
  # A segment cannot change drive, directory, stream, or Windows normalization.
  match=re.fullmatch(r'[^/\\:\x00-\x1f<>"|?*]+',item)
  if not match or item=='..' or item!=item.rstrip(' .'):raise ValueError('Unsafe path component.')
  safe=match.group(0)
  if re.fullmatch(r'(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?',safe,re.I):raise ValueError('Device names are not file paths.')
  result.append(safe)
 return result

def user_local_path(value):
 if not isinstance(value,(str,Path)):raise ValueError('Choose an explicit local file or folder.')
 value=str(value)
 if value.startswith('\\\\?\\') and re.match(r'^[A-Za-z]:[\\/]',value[4:]):value=value[4:]
 if value.startswith(('\\\\','//')):raise ValueError('Network and device paths are not local selections.')
 if value=='~' or value.startswith(('~/','~\\')):root=Path.home();tail=value[2:]
 elif os.name=='nt':
  if not re.match(r'^[A-Za-z]:[\\/]',value):raise ValueError('Use a full local drive path.')
  roots={letter:Path(letter+':/') for letter in string.ascii_uppercase};root=roots[value[0].upper()];tail=value[3:]
  import ctypes
  if ctypes.windll.kernel32.GetDriveTypeW(str(root))==4:raise ValueError('Mapped network drives are not supported.')
 else:
  if not value.startswith('/'):raise ValueError('Use an absolute local path.')
  root=Path('/');tail=value[1:]
 return root.joinpath(*segments(tail)) if tail else root

def relative_path(root,value):
 if not isinstance(value,str) or value.startswith(('/','\\')) or ':' in value:raise ValueError('Use an approved relative file path.')
 return Path(root).joinpath(*segments(value))

def job_id(value):
 if not isinstance(value,str) or not re.fullmatch('[0-9a-f]{32}',value):raise ValueError('Invalid generated-file reference.')
 return bytes.fromhex(value).hex()
