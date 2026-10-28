"""Optional installed Office export. No macros, links, prompts, or existing files are accepted."""
import contextlib,io,tempfile,zipfile,xml.etree.ElementTree as ET
from pathlib import Path

def export_pdf(source,parent):
 kind={'.docx':'word','.xlsx':'excel','.pptx':'powerpoint'}.get(source.suffix.lower())
 if not kind:raise ValueError('Choose a macro-free DOCX, XLSX or PPTX file.')
 from windows_tools import app_paths
 if not app_paths().get(kind,{}).get('installed'):raise ValueError('The required Microsoft Office application is not installed. No conversion was performed.')
 with zipfile.ZipFile(source) as z:
  if sum(x.file_size for x in z.infolist())>100_000_000:raise ValueError('Expanded Office file is too large.')
  for name in z.namelist():
   if 'vbaproject' in name.lower() or 'embeddings/' in name.lower():raise ValueError('Macros and embedded executable objects are blocked.')
   if name.endswith('.rels'):
    if z.getinfo(name).file_size>1_000_000:raise ValueError('Relationship data is too large.')
    if any(x.attrib.get('TargetMode')=='External' for x in ET.fromstring(z.read(name))):raise ValueError('This Office file contains external relationships. Remove them manually before conversion.')
 import pythoncom,win32com.client
 pythoncom.CoInitialize();application=None;document=None;owned=False
 try:
  application=win32com.client.DispatchEx({'word':'Word.Application','excel':'Excel.Application','powerpoint':'PowerPoint.Application'}[kind])
  collection=application.Documents if kind=='word' else application.Workbooks if kind=='excel' else application.Presentations
  if collection.Count:raise ValueError('Office reused an instance containing open documents. Export was stopped to preserve them.')
  owned=True
  if kind in ['word','excel']:application.AutomationSecurity=3
  with tempfile.TemporaryDirectory(prefix='YOEAI-Office-',dir=parent) as folder:
   output=Path(folder)/'export.pdf'
   if kind=='word':
    document=collection.Open(str(source),ConfirmConversions=False,ReadOnly=True,AddToRecentFiles=False);document.ExportAsFixedFormat(str(output),17)
   elif kind=='excel':
    document=collection.Open(str(source),UpdateLinks=0,ReadOnly=True,AddToMru=False);document.ExportAsFixedFormat(0,str(output))
   else:
    document=collection.Open(str(source),ReadOnly=True,Untitled=False,WithWindow=False);document.ExportAsFixedFormat(str(output),2)
   if not output.is_file():raise ValueError('Office did not create a PDF. No output was claimed.')
   return output.read_bytes()
 finally:
  if document:
   with contextlib.suppress(Exception):document.Close(False) if kind!='powerpoint' else document.Close()
  if application and owned:
   with contextlib.suppress(Exception):application.Quit()
  pythoncom.CoUninitialize()
