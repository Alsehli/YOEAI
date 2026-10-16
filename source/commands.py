"""Only direct user requests can reach this fixed action allowlist."""
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class Action:
    key: str
    label: str
    target: str

HOME = Path.home()
ACTIONS = {
    'notepad': Action('notepad', 'Open Notepad', 'notepad.exe'),
    'calculator': Action('calculator', 'Open Calculator', 'calc.exe'),
    'explorer': Action('explorer', 'Open File Explorer', 'explorer.exe'),
    'settings': Action('settings', 'Open Windows Settings', 'ms-settings:'),
    'documents': Action('documents', 'Open your Documents folder', str(HOME / 'Documents')),
    'desktop': Action('desktop', 'Open your Desktop folder', str(HOME / 'Desktop')),
}
PHRASES = {
    'open notepad': 'notepad', 'افتح المفكرة': 'notepad',
    'open calculator': 'calculator', 'افتح الحاسبة': 'calculator', 'افتح الآلة الحاسبة': 'calculator',
    'open file explorer': 'explorer', 'افتح مستكشف الملفات': 'explorer',
    'open settings': 'settings', 'افتح الإعدادات': 'settings', 'افتح الاعدادات': 'settings',
    'open documents': 'documents', 'افتح المستندات': 'documents',
    'open desktop': 'desktop', 'افتح سطح المكتب': 'desktop',
}
def propose(text):
    normalized = ' '.join(text.strip().lower().rstrip('.!?؟').split())
    key = PHRASES.get(normalized)
    return ACTIONS.get(key)

def launch(action):
    if action != ACTIONS.get(action.key):
        raise ValueError('Action is outside the supported allowlist.')
    if action.key in {'settings', 'documents', 'desktop'}:
        os.startfile(action.target)
    else:
        system32 = Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'System32'
        subprocess.Popen([str(system32 / action.target)], shell=False)

def execute_confirmed(action, confirm, runner=launch):
    if action != ACTIONS.get(action.key):
        raise ValueError('Unsupported action.')
    if not confirm(action):
        return False
    runner(action)
    return True
