"""Fixed Photoshop recipes. Model text is JSON data, never ExtendScript."""
import contextlib,hashlib,json,re,uuid
from pathlib import Path
from windows_policy import scoped_path

def validate(name,p,scope):
 if 'photoshop' not in scope['apps']:raise ValueError('Approve Photoshop in this task application scope.')
 if name=='photoshop_preview':
  scoped_path(scope.get('folder'),'.')
  for k in ('width','height'):
   if type(p.get(k))!=int or not 64<=p[k]<=4096:raise ValueError('Canvas dimensions must be integers from 64 to 4096.')
  if len(p.get('text',''))>500:raise ValueError('Title is limited to 500 characters.')
  if not re.fullmatch('#[0-9a-fA-F]{6}',p.get('color','#102040')):raise ValueError('Use a six-digit background hex color.')
  if p.get('path'):
   f=scoped_path(scope.get('folder'),p['path'])
   if f.suffix.lower() not in {'.png','.jpg','.jpeg'} or f.stat().st_size>25_000_000:raise ValueError('Choose PNG/JPEG under 25 MB in the approved folder.')
 else:
  if not re.fullmatch('[0-9a-f]{32}',p.get('draft','')):raise ValueError('Choose an actual Photoshop preview ID.')
  f=scoped_path(scope.get('folder'),p.get('destination',''),False)
  if f.suffix.lower()!='.psd':raise ValueError('Choose a new .psd destination in the approved folder.')
  for out in (f,f.with_suffix('.png')):
   if out.exists():raise ValueError('Existing files are never overwritten. Choose a new name.')
 return True

def script(data):
 # All operations are static; potentially hostile text is only parsed JSON.
 payload=json.dumps(data,ensure_ascii=True)
 return """(function(){var p=("""+payload+""");var previous=app.documents.length?app.activeDocument:null;var dialogs=app.displayDialogs;var units=app.preferences.rulerUnits;var d=null;var opened=null;var wasOpen=false;try{app.displayDialogs=DialogModes.NO;app.preferences.rulerUnits=Units.PIXELS;
 if(p.exporting){d=app.open(new File(p.source));}
 else if(p.source){for(var i=0;i<app.documents.length;i++){try{if(app.documents[i].fullName.fsName==new File(p.source).fsName)wasOpen=true;}catch(ignore){}}opened=app.open(new File(p.source));d=opened.duplicate('YOEAI design copy');if(!wasOpen){opened.close(SaveOptions.DONOTSAVECHANGES);opened=null;}d.resizeImage(UnitValue(p.width,'px'),UnitValue(p.height,'px'),null,ResampleMethod.BICUBIC);}
 else{d=app.documents.add(p.width,p.height,72,'YOEAI design',NewDocumentMode.RGB,DocumentFill.TRANSPARENT);var bg=d.artLayers.add();bg.name='Background';var c=new SolidColor();c.rgb.hexValue=p.color.substring(1);d.selection.selectAll();d.selection.fill(c);d.selection.deselect();}
 if(!p.exporting&&p.text){var t=d.artLayers.add();t.kind=LayerKind.TEXT;t.name='Editable title';t.textItem.contents=p.text;t.textItem.size=UnitValue(Math.max(12,Math.min(120,p.width/14)),'px');t.textItem.position=[UnitValue(p.width*.08,'px'),UnitValue(p.height*.5,'px')];var tc=new SolidColor();tc.rgb.hexValue='FFFFFF';t.textItem.color=tc;}
 var psd=new File(p.psd);var png=new File(p.png);if(psd.exists||png.exists)throw Error('Output already exists');var opts=new PhotoshopSaveOptions();opts.layers=true;d.saveAs(psd,opts,true,Extension.LOWERCASE);d.saveAs(png,new PNGSaveOptions(),true,Extension.LOWERCASE);return 'YOEAI_OK';
 }finally{if(d)d.close(SaveOptions.DONOTSAVECHANGES);if(opened&&!wasOpen){try{opened.close(SaveOptions.DONOTSAVECHANGES);}catch(ignore){}}app.displayDialogs=dialogs;app.preferences.rulerUnits=units;if(previous){try{app.activeDocument=previous;}catch(ignore){}}}})();"""

def execute(name,p,scope,context):
 validate(name,p,scope)
 import pythoncom,win32com.client
 pythoncom.CoInitialize()
 try:
  app=win32com.client.Dispatch('Photoshop.Application');home=Path(context['home']);tid=context['task']
  if not re.fullmatch('[0-9a-f]{32}',tid):raise ValueError('Invalid task identity.')
  relative='YOEAI-Photoshop-Drafts/'+tid
  folder=scoped_path(scope['folder'],relative,False);folder.mkdir(parents=True,exist_ok=True)
  folder=scoped_path(scope['folder'],relative)
  # Adobe runs outside the packaged host: use the actual filesystem directory.
  import win32file,win32con
  handle=win32file.CreateFile(str(folder),0,7,None,win32con.OPEN_EXISTING,win32con.FILE_FLAG_BACKUP_SEMANTICS,None)
  try:folder=Path(win32file.GetFinalPathNameByHandle(handle,0).removeprefix('\\\\?\\'))
  finally:handle.Close()
  if name=='photoshop_preview':
   id=uuid.uuid4().hex;psd=folder/(id+'.psd');png=folder/(id+'.png');source=str(scoped_path(scope['folder'],p['path'])) if p.get('path') else ''
   data=dict(p,source=source,psd=str(psd),png=str(png),color=p.get('color','#102040'))
   if app.DoJavaScript(script(data))!='YOEAI_OK':raise ValueError('Photoshop did not confirm the recipe.')
   from PIL import Image
   with Image.open(png) as image:
    image=image.convert('RGB');image.thumbnail((1280,960));shots=home/'WindowsShots'/tid;shots.mkdir(parents=True,exist_ok=True);shot=hashlib.sha256(id.encode()).hexdigest()+'.jpg';image.save(shots/shot,'JPEG',quality=85)
   record={'draft':id,'sha256':hashlib.sha256(psd.read_bytes()).hexdigest(),'width':p['width'],'height':p['height']};(folder/(id+'.json')).write_text(json.dumps(record),encoding='utf-8')
   return {**record,'screenshot':shot,'verified':True,'notice':'Preview created in Photoshop. Review it before approving photoshop_export. Original images and open documents were not saved.'}
  id=p['draft'];source=folder/(id+'.psd');record=json.loads((folder/(id+'.json')).read_text(encoding='utf-8'))
  if hashlib.sha256(source.read_bytes()).hexdigest()!=record['sha256']:raise ValueError('Draft changed; create a fresh preview.')
  target=scoped_path(scope['folder'],p['destination'],False)
  data={'exporting':True,'source':str(source),'psd':str(target),'png':str(target.with_suffix('.png'))}
  if app.DoJavaScript(script(data))!='YOEAI_OK':raise ValueError('Photoshop export did not confirm success.')
  return {'psd':str(target),'png':str(target.with_suffix('.png')),'verified':target.is_file() and target.with_suffix('.png').is_file(),'notice':'New layered PSD and PNG exported. No originals overwritten.'}
 finally:pythoncom.CoUninitialize()
