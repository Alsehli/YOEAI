"""Deterministic additions to the existing Windows YOE tool catalogue."""
import json
from pathlib import Path
SPECS={
 'known_folder':('Locate a Windows Downloads/Documents/Pictures/Desktop folder; this does not grant file access','read',('name',)),
 'app_shortcut':('Create a new shortcut to an approved detected application inside the approved folder','file_write',('app','destination')),
 'app_info':('Inspect the installed path, running status and actual process CPU/RAM of an approved application','read',('app',)),
 'selected_files':('Read selected files in the approved Explorer window, restricted to the approved folder','private',('window',)),
 'files_stat':('Read actual size and metadata of an approved file or bounded folder','file_read',('path',)),
 'images_pdf':('Combine approved images as a local PDF, A4/Letter/original, one image per page; no overwrite','file_write',('paths','destination','size')),
 'document_preview':('Preview an approved image or one PDF page inside Windows YOE before saving; no source or user output is modified','file_private',('path','page')),
 'document_info':('Read approved PDF page count, image metadata or Office document structure; not inferred pagination','file_private',('path',)),
 'pdf_transform':('Merge/rotate/losslessly compress/fit PDF pages to A4 or extract images into a new folder; no overwrite','file_write',('paths','destination','operation','degrees')),
 'image_transform':('Rotate or make a contact sheet from approved pictures into a new image; no overwrite','file_write',('paths','destination','operation','degrees')),
 'office_create':('Create a new DOCX document, XLSX tracker or PPTX slide outline from supplied text; no macros or overwrite','file_write',('destination','format','title','text')),
 'office_pdf':('Export an approved macro-free Office file to a new PDF using the installed Office application','change',('path','destination')),
 'calendar_draft':('Save a local ICS calendar draft with confirmed ISO start time; never sends invitations or creates an active reminder','file_write',('destination','title','start','minutes')),
 'web_search':('Search using local SearXNG after explicit web-search permission; only this query is transmitted','network',('query',)),
 'media_info':('Read local WAV duration or image metadata; other media needs a verified installed ffprobe','file_private',('path',)),
}
WRITES={'app_shortcut','images_pdf','pdf_transform','image_transform','office_create','office_pdf','calendar_draft'}
def paths(value,scope):
 from windows_policy import scoped_path
 try:items=json.loads(value)
 except (ValueError,TypeError):raise ValueError('Choose the source files first.')
 if not isinstance(items,list) or not 1<=len(items)<=40 or not all(isinstance(p,str) for p in items):raise ValueError('Choose 1-40 source files.')
 return [scoped_path(scope.get('folder'),p) for p in items]
def validate(name,p,scope):
 from windows_policy import scoped_path
 if name=='known_folder' and p.get('name') not in ['downloads','documents','pictures','desktop']:raise ValueError('Choose Downloads, Documents, Pictures or Desktop.')
 if name=='document_preview' and (type(p.get('page',1))!=int or not 1<=p.get('page',1)<=200):raise ValueError('Choose a page from 1 to 200.')
 if name=='web_search' and scope.get('webSearch') is not True:raise ValueError('Approve web search in this task scope before searching.')
 if name=='web_search' and not 1<=len(p.get('query','').strip())<=500:raise ValueError('Use a search question under 500 characters.')
 if name in {'files_stat','document_info','document_preview','office_pdf','media_info'}:scoped_path(scope.get('folder'),p.get('path',''))
 if name in {'images_pdf','pdf_transform','image_transform'}:paths(p.get('paths'),scope)
 if name in WRITES:
  dest=scoped_path(scope.get('folder'),p.get('destination',''),False)
  if dest==Path(scope['folder']) or dest.exists():raise ValueError('Choose a new output name. Existing files and the approved root cannot be overwritten.')
  suffix='.pdf' if name in {'images_pdf','office_pdf'} or name=='pdf_transform' and p.get('operation')!='extract_images' else None
  if suffix and dest.suffix.lower()!=suffix:raise ValueError('The output filename must end with .pdf.')
 if name=='app_shortcut' and dest.suffix.lower()!='.lnk':raise ValueError('Choose a new .lnk filename.')
 if name=='images_pdf' and p.get('size','a4') not in ['a4','letter','original']:raise ValueError('Choose A4, Letter or original image size.')
 if name=='pdf_transform' and p.get('operation') not in ['merge','rotate','compress','a4','extract_images']:raise ValueError('Choose a supported PDF operation.')
 if name=='image_transform' and p.get('operation') not in ['rotate','contact_sheet']:raise ValueError('Choose rotation or contact sheet.')
 if name in {'image_transform','pdf_transform'} and p.get('operation')=='rotate' and p.get('degrees',90) not in [90,180,270]:raise ValueError('Rotate by 90, 180 or 270 degrees.')
 if name=='image_transform' and dest.suffix.lower() not in ['.png','.jpg','.jpeg']:raise ValueError('Choose a new PNG or JPEG output.')
 if name=='office_create' and (p.get('format') not in ['docx','xlsx','pptx'] or dest.suffix.lower()!='.'+p['format']):raise ValueError('Choose a matching DOCX, XLSX or PPTX output filename.')
 if name=='calendar_draft':
  from datetime import datetime
  if dest.suffix.lower()!='.ics':raise ValueError('Choose a new .ics filename.')
  try:start=datetime.fromisoformat(p.get('start',''))
  except ValueError:raise ValueError('Ask for the date and time before creating the calendar draft.')
  if start.tzinfo is None or type(p.get('minutes'))!=int or not 1<=p['minutes']<=1440:raise ValueError('Confirm a start time with timezone offset and duration of 1-1440 minutes.')
