"""Visible completion text from actual structured outcomes, never imagined actions."""
from pathlib import Path

def summary(records,arabic=False):
 if arabic:return arabic_summary(records)
 out=[]
 for r in records:
  name=r['name'];v=r.get('result') or {};p=r.get('scope',{})
  if r.get('status')!='PASS':out.append('A step failed. Review its error in Details.');continue
  if r.get('verification')!='VERIFIED':out.append('A requested '+name.replace('_',' ')+' step still needs checking.');continue
  if name=='app_launch':out.append('Opened '+p.get('app','the application').title()+'.')
  elif name=='window_focus':out.append('Brought the approved window to the front.')
  elif name=='window_close':out.append('Closed the approved window.')
  elif name=='known_folder':out.append('Folder: '+str(v.get('path',''))+'. Folder access still needs approval.')
  elif name=='app_info':
   rows=v.get('processes',[]);out.append(p.get('app','Application').title()+(' is running' if v.get('running') else ' is not running')+(f"; {sum(x['ramBytes'] for x in rows)/1024**3:.2f} GiB RAM in this sample." if rows else '.'))
  elif name=='system_info' and 'cpuPercent' in v and 'ramPercent' in v:out.append(f"CPU: {v['cpuPercent']:.1f}%. RAM: {v.get('ramPercent',0):.1f}% used. These are current sample readings.")
  elif name=='system_info' and 'activeModel' in v:out.append('Active model: '+str(v['activeModel'] or 'could not be verified')+'.')
  elif name=='selected_files':out.append('Selected files: '+(', '.join(v.get('selectedFiles',[])) or 'none')+'.')
  elif name=='files_search':out.append('Found: '+(', '.join(str(x.get('path','')) for x in v.get('entries',[])[:10]) or 'no matching files in the approved folder')+'.')
  elif name=='files_list':out.append('Folder contains: '+(', '.join(str(x.get('path','')) for x in v.get('entries',[])[:10]) or 'no visible supported items')+'.')
  elif name=='files_stat':out.append('Size: '+str(v.get('bytes',v.get('bytesCounted',0)))+' bytes'+(' (partial count).' if v.get('truncated') else '.'))
  elif name in ['images_pdf','pdf_transform']:out.append(('Created PDF: ' if name=='images_pdf' else 'Saved PDF results: ')+str(v.get('saved',''))+(' ('+str(v['pages'])+' pages).' if 'pages' in v else '.'))
  elif name in ['office_create','office_pdf','image_transform','app_shortcut','files_write','files_mkdir','browser_download']:out.append('Saved: '+str(v.get('saved',v.get('created','the approved output')))+'.')
  elif name=='calendar_draft':out.append('Saved calendar draft: '+str(v.get('saved',''))+'. Import it to your calendar; no active reminder or invitation was created.')
  elif name in ['files_copy','files_move','files_rename']:out.append({'files_copy':'Copied','files_move':'Moved','files_rename':'Renamed'}[name]+' to '+str(v.get('destination',''))+'.')
  elif name=='document_preview':out.append('Preview ready'+(' — page '+str(v.get('previewPage',1))+' of '+str(v['pages']) if v.get('pages') else '')+'. See the preview in Details; the source was not changed.')
  elif name=='document_info' or name=='media_info':out.append('File details: '+', '.join(k+': '+str(v[k]) for k in ['pages','width','height','frames','slides','seconds','paragraphs','tables','bytes'] if k in v)+'.')
  elif name=='browser_open':out.append('Opened the approved page: '+str(v.get('url',''))+'.')
  elif name=='browser_read':out.append('Read the approved browser page. Its text is available in Details.')
  elif name=='browser_fill':out.append('Filled the approved '+str(v.get('field','field'))+'. The form was not submitted.')
  elif name=='web_search':
   links='\n'.join('- ['+str(x['title']).replace('[','\\[').replace(']','\\]')+']('+x['url']+') — '+str(x['snippet'])[:300] for x in v.get('results',[])[:5])
   out.append('Found '+str(len(v.get('results',[])))+' web results. Search snippets are not independently verified facts.\n'+links)
  elif name=='window_capture':out.append('Captured the approved application window. See its preview in Details.')
  elif name=='ui_read':out.append('Read '+str(len(v.get('observation',{}).get('controls',[])))+' accessible controls in the approved window.')
  else:out.append('Verified: '+name.replace('_',' ')+'. Details contains the actual output.')
 return '\n\n'.join(out) if out else 'No computer action was performed.'


def arabic_summary(records):
 out=[];apps={'notepad':'المفكرة','calculator':'الآلة الحاسبة','explorer':'مستكشف الملفات','settings':'إعدادات ويندوز','taskmanager':'إدارة المهام'}
 for r in records:
  v=r.get('result') or {};p=r.get('scope',{});name=r['name']
  if r.get('verification')!='VERIFIED':out.append('تحتاج هذه الخطوة إلى التحقق. راجع التفاصيل.');continue
  if name=='app_launch':out.append('تم فتح '+apps.get(p.get('app'),p.get('app','التطبيق'))+'.')
  elif name=='window_focus':out.append('تم إظهار النافذة المعتمدة في المقدمة.')
  elif name=='window_close':out.append('تم إغلاق النافذة المعتمدة.')
  elif name=='system_info' and 'cpuPercent' in v and 'ramPercent' in v:out.append(f"استخدام المعالج: {v['cpuPercent']:.1f}٪. الذاكرة المستخدمة: {v.get('ramPercent',0):.1f}٪. هذه قراءة لحظية وليست تشخيصاً مؤكداً.")
  elif name=='known_folder':out.append('موقع المجلد: '+str(v.get('path','')))
  elif name in ['images_pdf','pdf_transform','office_create','office_pdf','image_transform','files_write','files_mkdir','files_copy','files_move','files_rename','browser_download','app_shortcut']:out.append('تم حفظ الناتج في: '+str(v.get('saved',v.get('created',v.get('destination',''))))+('. عدد الصفحات: '+str(v['pages']) if v.get('pages') else ''))
  elif name=='files_search':out.append('الملفات المطابقة: '+(', '.join(x.get('path','') for x in v.get('entries',[])[:10]) or 'لم أعثر على ملفات مطابقة في المجلد المعتمد.'))
  elif name=='document_preview':out.append('المعاينة جاهزة في التفاصيل. لم يتم تعديل الملف الأصلي.')
  elif name=='calendar_draft':out.append('تم حفظ مسودة التقويم: '+str(v.get('saved',''))+'. لم يتم تفعيل تذكير أو إرسال دعوة.')
  elif name=='web_search':out.append('نتائج البحث: '+str(len(v.get('results',[])))+'\n'+'\n'.join('['+x['title'].replace('[','').replace(']','')+']('+x['url']+')' for x in v.get('results',[])[:5]))
  else:out.append('تم التحقق من تنفيذ هذه الخطوة. النتائج الفعلية موجودة في التفاصيل.')
 return '\n\n'.join(out) if out else 'لم يتم تنفيذ أي إجراء على الكمبيوتر.'
