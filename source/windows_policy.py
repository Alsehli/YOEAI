"""Windows YOE capability policy. Tool names are capabilities, never shell text."""
import hashlib,json,os,re,time
from pathlib import Path
from urllib.parse import urlsplit

APPS=('notepad','explorer','edge','chrome','word','excel','settings','taskmanager','photoshop','calculator','powerpoint','yoeai')
MODES=('ADVISOR','ASSISTED','ADVANCED')
SPECS={
 'files_explorer':('Open interactive file/storage results for an approved folder. Use view=scan for largest files, categories, duplicate candidates, cleanup or organization; browse for browsing. category may be Documents, Images, Videos, Audio, Applications, Archives, AI Models, Programming, Games, Temporary Files, Other or empty. sort may be name, size, date, type, -size or -date. This prepares the widget, not a completed scan or deletion.','file_read',('path','view','category','sort')),
 'photoshop_preview':('Create a Photoshop design preview from a new canvas or a copy of an approved PNG/JPEG; resize to exact dimensions and add editable white title text','change',('path','width','height','text','color')),
 'photoshop_export':('Export a reviewed Photoshop draft as new layered PSD and PNG without overwriting','file_write',('draft','destination')),
 'system_info':('Read actual system diagnostics','read',('topic',)),
 'powershell_diagnostic':('Run a fixed read-only PowerShell diagnostic','read',('topic',)),
 'apps_detect':('Detect supported installed applications','read',()),
 'software_info':('Read installed software identity and versions','read',()),
 'software_updates':('Check winget for available application updates','network',()),
 'software_install':('Install a verified, explicitly approved winget package for this user','software',('package','publisher')),
 'software_uninstall':('Remove an explicitly approved installed winget package for this user','software',('package','publisher')),
 'windows_list':('List windows belonging to approved applications','private',()),
 'app_launch':('Launch an approved installed application','launch',('app','path')),
 'window_focus':('Focus an approved window','position',('window',)),
 'window_state':('Minimise, maximise, restore or resize an approved window','position',('window','state','width','height')),
 'window_close':('Request normal application close; unsaved prompts are not dismissed','change',('window',)),
 'ui_read':('Read non-password accessibility controls in an approved window','private',('window',)),
 'ui_invoke':('Invoke one previously observed accessible control','change',('window','control')),
 'ui_type':('Set text in one previously observed non-password edit control','change',('window','control','text')),
 'ui_select':('Select one previously observed accessible item','change',('window','control')),
 'ui_scroll':('Scroll one observed accessible control','position',('window','control','direction')),
 'ui_key':('Send a restricted keyboard shortcut to an approved offline editor','change',('window','key')),
 'window_capture':('Capture only the approved application window locally','private',('window',)),
 'window_analyse':('Capture an approved window and ask the existing local vision model','private',('window','question')),
 'files_list':('List the approved folder','file_read',('path',)),
 'files_search':('Search file names under the approved folder','file_read',('path','query')),
 'files_read':('Read a supported document in the approved folder','file_private',('path',)),
 'files_duplicates':('Find duplicate small files in the approved folder','file_read',('path',)),
 'files_cleanup':('Recommend cleanup without deleting files','file_read',('path',)),
 'files_mkdir':('Create a folder inside the approved root','file_write',('path',)),
 'files_write':('Create a UTF-8 document; existing files are never overwritten','file_write',('path','text')),
 'files_copy':('Copy a file without overwriting','file_write',('path','destination')),
 'files_move':('Move a file without overwriting','file_write',('path','destination')),
 'files_rename':('Rename a file without overwriting','file_write',('path','destination')),
 'files_recycle':('Move a single approved file to the Recycle Bin','destructive',('path',)),
 'browser_open':('Navigate the isolated agent browser to an approved origin','network',('app','url')),
 'browser_read':('Read the isolated browser page as untrusted evidence','private',()),
 'browser_fill':('Fill one ordinary labelled field in the isolated browser','transmit',('label','text')),
 'browser_link':('Follow one labelled same-scope link in the isolated browser','network',('label',)),
 'browser_download':('Download a bounded public file to the approved folder','transmit',('url','destination')),
 'handoff':('Ask the user to perform a sensitive or unsupported action manually','handoff',('instruction',)),
}
from windows_capabilities import SPECS as EXTRA_SPECS
SPECS.update(EXTRA_SPECS)
TOPICS=('overview','processes','storage','disk_health','startup','updates','defender','firewall','network','power','apps','model')
PRIVATE_NAME=re.compile(r'(^\.env|credential|password|secret|token|private.?key|id_rsa|id_ed25519)',re.I)
PROTECTED={'.ssh','.aws','.azure','.gnupg','.codex','.config','.kube','.docker','appdata','windows','program files','program files (x86)','programdata','$recycle.bin','system volume information','.git','node_modules','.venv','venv'}
SENSITIVE_UI=re.compile(r'password|passcode|credential|security key|sign.?in|log.?in|buy|purchase|pay\b|checkout|transfer|send\b|submit|publish|post\b|delete|remove|overwrite|replace|\bsave\b|install|uninstall|elevat|administrator|defender|firewall|antivirus|security|macro|visual basic|execute|\brun\b|accept.*terms|agree|allow access',re.I)

def fingerprint(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def redact(text):
 text=str(text)
 text=re.sub(r'\b(?:sk-[\w-]{16,}|gh[pousr]_[\w]{20,}|AKIA[A-Z0-9]{16})','[REDACTED]',text)
 return re.sub(r'((?:password|api[_ -]?key|client[_ -]?secret|access[_ -]?token)\s*[:=]\s*)[^\s,;]+',r'\1[REDACTED]',text,flags=re.I)
def reject_secret(text):
 if redact(text)!=str(text) or 'PRIVATE KEY-----' in str(text):raise ValueError('Credentials must not be supplied to Windows YOE.')

def canonical_path(value):
 text=str(value)
 if text.startswith('\\\\.\\'):raise ValueError('Device namespaces are not approved folders.')
 if text.startswith('\\\\?\\'):
  tail=text[4:]
  if tail.startswith('UNC\\'):text='\\\\'+tail[4:]
  elif re.match(r'^[A-Za-z]:\\',tail):text=tail
  else:raise ValueError('Only ordinary drive/UNC paths are supported.')
 return Path(text)

def native_path(value):
 p=Path(value);text=str(p)
 canonical_path(p)
 if os.name=='nt' and len(text)>=240 and not text.startswith('\\\\?\\'):
  return Path('\\\\?\\UNC\\'+text[2:] if text.startswith('\\\\') else '\\\\?\\'+text)
 return p

def relative_path(value,root):return canonical_path(value).relative_to(canonical_path(root))

def root_folder(value):
 if not value:return None
 p=native_path(Path(value).expanduser().absolute())
 normal=canonical_path(p)
 if os.name=='nt':
  import ctypes
  if normal.anchor.startswith('\\\\') or ctypes.windll.kernel32.GetDriveTypeW(normal.anchor)==4:raise ValueError('This local storage workspace does not grant access to network shares.')
 for part in [p,*p.parents]:
  if part.is_symlink() or part.exists() and getattr(part.lstat(),'st_file_attributes',0)&0x400:raise ValueError('Linked folder scopes are blocked.')
 p=p.resolve(strict=True)
 normal=canonical_path(p)
 if not p.is_dir() or len(normal.parts)<2 or normal in [Path.home(),Path.home().parent] or normal.parent==Path.home().parent or any(x.lower() in PROTECTED or PRIVATE_NAME.search(x) for x in normal.parts):raise ValueError('Choose a specific non-sensitive folder, not a drive, user or system root.')
 return p

def scoped_path(root,relative,exists=True):
 root=root_folder(root)
 if root is None:raise ValueError('This action requires an explicitly approved folder.')
 if not isinstance(relative,str) or len(relative)>32700:raise ValueError('Invalid relative path.')
 p=Path(relative or '.')
 if p.is_absolute() or '..' in p.parts or ':' in relative or any(x.lower() in PROTECTED or PRIVATE_NAME.search(x) for x in p.parts):raise ValueError('Protected, sensitive or out-of-scope path blocked.')
 current=root
 for part in p.parts:
  current=current/part
  probe=native_path(current)
  if probe.is_symlink() or probe.exists() and getattr(probe.lstat(),'st_file_attributes',0)&0x400:raise ValueError('Linked paths are blocked.')
 resolved=native_path(current).resolve(strict=exists)
 if not canonical_path(resolved).is_relative_to(canonical_path(root)):raise ValueError('Path escaped the approved folder.')
 return resolved

def origin(value):
 try:p=urlsplit(value)
 except ValueError:raise ValueError('Invalid website address.')
 if p.scheme not in ('http','https') or not p.hostname or p.username or p.password:raise ValueError('Only explicitly approved HTTP/HTTPS origins are supported.')
 try:port=p.port
 except ValueError:raise ValueError('Invalid website port.')
 return p.scheme+'://'+p.hostname.lower()+(':'+str(port) if port and port!=({'http':80,'https':443}[p.scheme]) else '')

def make_scope(body):
 if not isinstance(body,dict):raise ValueError('Windows task scope must be an object.')
 mode=body.get('mode','ADVISOR');apps=body.get('apps',[]);origins=body.get('origins',[])
 if mode not in MODES or not isinstance(apps,list) or not all(a in APPS for a in apps):raise ValueError('Choose a supported mode and application scope.')
 if not isinstance(origins,list) or len(origins)>8 or not all(isinstance(x,str) for x in origins):raise ValueError('Approve up to eight website origins.')
 actions=body.get('maxActions',8);seconds=body.get('maxSeconds',300);retries=body.get('maxRetries',0)
 if type(actions)!=int or not 1<=actions<=20 or type(seconds)!=int or not 60<=seconds<=900 or type(retries)!=int or not 0<=retries<=1:raise ValueError('Use 1–20 actions, 60–900 seconds and at most one retry.')
 root=root_folder(body.get('folder'))
 return {'mode':mode,'apps':list(dict.fromkeys(apps)),'folder':str(root) if root else None,'origins':list(dict.fromkeys(origin(x) for x in origins)),'maxActions':actions,'maxSeconds':seconds,'maxRetries':retries,'webSearch':body.get('webSearch') is True,'reuseLowRisk':mode=='ADVANCED' and body.get('reuseLowRisk') is True}

def validate_action(action,scope):
 if not isinstance(action,dict) or action.get('tool') not in SPECS:raise ValueError('Unsupported Windows tool. Shell commands are not capabilities.')
 name=action['tool'];params=action.get('params',{})
 if not isinstance(params,dict) or set(params)-set(SPECS[name][2]):raise ValueError('Unexpected tool parameters.')
 for k,v in params.items():
  if type(v) not in (str,int,float,bool) or isinstance(v,str) and len(v)>12000:raise ValueError('Tool parameters must be bounded scalar values.')
  if isinstance(v,str):reject_secret(v)
 if name in EXTRA_SPECS:
  from windows_capabilities import validate
  validate(name,params,scope)
 if name.startswith('photoshop_'):
  from photoshop_yoe import validate
  validate(name,params,scope)
 risk=SPECS[name][1]
 if scope['mode']=='ADVISOR' and risk not in ('read','file_read','file_private','private','handoff'):raise ValueError('Advisor mode is read-only. Choose Assisted or Advanced for actions.')
 if params.get('app') and params['app'] not in scope['apps']:raise ValueError('Application is outside this task’s allowlist.')
 if name in ['system_info','powershell_diagnostic'] and params.get('topic','overview') not in TOPICS:raise ValueError('Unknown diagnostic template.')
 if name.startswith('files_'):
  p=scoped_path(scope.get('folder'),params.get('path',''),exists=name not in ['files_mkdir','files_write'])
  if name not in ['files_list','files_search','files_duplicates','files_cleanup','files_stat','files_explorer'] and p==Path(scope['folder']):raise ValueError('An operation cannot target the folder scope itself.')
  if name=='files_explorer' and (not p.is_dir() or params.get('view','browse') not in ['browse','scan']):raise ValueError('Choose an approved folder and browse or scan view.')
  if name=='files_explorer' and (params.get('category','') not in ['','Documents','Images','Videos','Audio','Applications','Archives','AI Models','Programming','Games','Temporary Files','Other'] or params.get('sort','name') not in ['name','size','date','type','-size','-date']):raise ValueError('Choose a supported category and sort order.')
  if 'destination' in params:scoped_path(scope['folder'],params['destination'],False)
  if name=='files_recycle':
   from windows_file_safety import cleanup_allowed
   cleanup_allowed(p)
 if name.startswith('software_') and name not in ['software_info','software_updates']:
  if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.+-]{1,100}',params.get('package','')) or not isinstance(params.get('publisher'),str) or not 2<=len(params['publisher'])<=120:raise ValueError('Provide an exact winget package ID and publisher for explicit review.')
 if name in ['browser_open','browser_download']:
  if origin(params.get('url','')) not in scope['origins']:raise ValueError('Website origin is not approved.')
 if name=='browser_download':
  p=scoped_path(scope.get('folder'),params.get('destination',''),False)
  if p.suffix.lower() not in {'.pdf','.txt','.csv','.json','.png','.jpg','.jpeg','.webp','.zip'}:raise ValueError('Only supported document/image/archive downloads are allowed; executable downloads are blocked.')
 if name=='browser_fill' and PRIVATE_NAME.search(params.get('label','')):raise ValueError('Credential entry requires the user to take over.')
 if name=='window_state' and params.get('state') not in ['minimise','maximise','restore','resize']:raise ValueError('Unsupported window state.')
 if name=='window_state' and params['state']=='resize' and not all(type(params.get(k))==int and 400<=params[k]<=3840 for k in ['width','height']):raise ValueError('Choose window dimensions between 400 and 3840 pixels.')
 if name=='ui_key' and params.get('key') not in ['CTRL+A','CTRL+S','CTRL+SHIFT+S','ESC','TAB','ENTER','UP','DOWN','PAGEUP','PAGEDOWN']:raise ValueError('Only the displayed safe keyboard shortcuts are supported.')
 if name=='ui_scroll' and params.get('direction') not in ['up','down']:raise ValueError('Choose up or down.')
 return {'tool':name,'params':params,'why':str(action.get('why',''))[:500],'expected':str(action.get('expected',''))[:500]}

def automatic(action,scope):
 risk=SPECS[action['tool']][1]
 if risk=='read':return True
 if scope['mode'] in ['ASSISTED','ADVANCED'] and risk=='launch' and not action['params'].get('path'):return True
 return scope['mode']=='ADVANCED' and scope['reuseLowRisk'] and risk in ('position','file_read')

def plan_schema():
 keys={k for spec in SPECS.values() for k in spec[2]}
 props={k:({'type':'integer'} if k in ['width','height','degrees','minutes','page'] else {'type':'string'}) for k in keys}
 props['topic']={'type':'string','enum':list(TOPICS)}
 schema={'type':'object','properties':{'summary':{'type':'string'},'steps':{'type':'array','maxItems':20,'items':{'type':'object','properties':{'tool':{'type':'string','enum':list(SPECS)},'params':{'type':'object','properties':props,'additionalProperties':False},'why':{'type':'string'},'expected':{'type':'string'}},'required':['tool','params','why','expected'],'additionalProperties':False}}},'required':['summary','steps'],'additionalProperties':False}

 # Bind each tool to its own parameters so constrained generation cannot mix recipes.
 step=schema['properties']['steps']['items'];variants=[]
 for name,spec in SPECS.items():
  params={k:dict(props[k]) for k in spec[2]}
  for key in ['path','destination']:
   if key in params and name in EXTRA_SPECS:params[key]['description']='Path relative to the approved folder, e.g. report.docx. Never include the drive or approved folder prefix.'
  if 'paths' in params:params['paths']['description']='JSON array of paths relative to the approved folder, e.g. ["photo.png"].'
  if 'paths' in params:params['paths']['pattern']=r'^\[.*\]$'
  if name=='images_pdf':params['size']['enum']=['a4','letter','original']
  if name=='files_explorer':
   params['view']['enum']=['browse','scan'];params['category']['enum']=['','Documents','Images','Videos','Audio','Applications','Archives','AI Models','Programming','Games','Temporary Files','Other'];params['sort']['enum']=['name','size','date','type','-size','-date']
  required_by_tool={'photoshop_preview':['width','height'],'photoshop_export':['draft','destination'],'office_create':['destination','format','title','text'],'office_pdf':['path','destination'],'images_pdf':['paths','destination','size'],'pdf_transform':['paths','destination','operation'],'image_transform':['paths','destination','operation'],'calendar_draft':['destination','title','start','minutes'],'app_shortcut':['app','destination'],'document_info':['path'],'document_preview':['path'],'media_info':['path'],'files_stat':['path'],'known_folder':['name'],'app_info':['app'],'selected_files':['window'],'web_search':['query']}
  required=required_by_tool.get(name,[])
  variants.append({'type':'object','properties':{'tool':{'type':'string','enum':[name]},'params':{'type':'object','properties':params,'required':required,'additionalProperties':False},'why':{'type':'string'},'expected':{'type':'string'}},'required':['tool','params','why','expected'],'additionalProperties':False})
 step['anyOf']=variants
 return schema
