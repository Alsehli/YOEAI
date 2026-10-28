"""Exact direct app-launch intent only. No paths, shell, editing or chained actions."""
import re
ALIASES={
 'photoshop':'photoshop','adobe photoshop':'photoshop','فوتوشوب':'photoshop','الفوتوشوب':'photoshop',
 'notepad':'notepad','المفكرة':'notepad','chrome':'chrome','google chrome':'chrome','كروم':'chrome',
 'edge':'edge','microsoft edge':'edge','word':'word','microsoft word':'word','وورد':'word',
 'excel':'excel','microsoft excel':'excel','اكسل':'excel','إكسل':'excel','powerpoint':'powerpoint',
 'calculator':'calculator','الحاسبة':'calculator','file explorer':'explorer','explorer':'explorer',
 'task manager':'taskmanager','settings':'settings','الإعدادات':'settings','yoeai':'yoeai'}
def direct_app(text):
 if not isinstance(text,str):return None
 value=' '.join(text.strip().lower().split()).rstrip('.!?؟')
 match=re.fullmatch(r'(?:(?:please|can you|could you) )?(?:open|launch|start|افتح|شغل|شغّل) (.+?)(?: please)?',value)
 return ALIASES.get(match.group(1)) if match else None

def prepare(e,t):
 from windows_policy import validate_action,automatic
 w=t['windows'];app=direct_app(t['objective'])
 if not app:return False
 scope=w['scope']
 if scope['mode']=='ADVISOR':
  t.update(status='COMPLETED',result='Advisor mode cannot open applications. Choose Assisted mode and send the request again.',stream='');w['outcome']='NEEDS_INPUT';e.event(t,t['result']);return True
 if scope['apps'] and app not in scope['apps']:
  t.update(status='COMPLETED',result='The requested application is outside this task scope. Select it under Approved applications, then send the request again.',stream='');w['outcome']='NEEDS_INPUT';e.event(t,t['result']);return True
 if not scope['apps']:
  # This exact user imperative grants only its named app to this task. Tool policy still applies.
  scope['apps']=[app];e.event(t,'Direct user launch request scopes this task to '+app+'. No file or editing permission was added.')
 from windows_tools import app_paths
 if not app_paths().get(app,{}).get('installed'):
  t.update(status='COMPLETED',result='I could not find the requested application installed on this PC. Nothing was launched or installed.',stream='');w['outcome']='NEEDS_INPUT';e.event(t,t['result']);return True
 action=validate_action(dict(tool='app_launch',params={'app':app},why='Open the application explicitly named in your request.',expected='A visible window belonging to the installed application.'),scope)
 if not automatic(action,scope):return False
 w.update(plan=[action],summary='Open '+app,planned=True,planApproved=True,started=__import__('time').time())
 t['plan']='1. Open '+app;t['phase']='windows_continue';e.event(t,'Opening '+app+' under the direct-launch policy.');
 from windows_agent import advance
 advance(e,t);return True
