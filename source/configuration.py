import json,os,sys
from pathlib import Path
APP_DIR=Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(__file__).parent
HOME=Path(os.environ['LOCALAPPDATA'])/'AlsehliAI-Preview'
HOME.mkdir(parents=True,exist_ok=True)
CONFIG_FILE=HOME/'config.json'
def read_config():
    if CONFIG_FILE.exists():return json.loads(CONFIG_FILE.read_text(encoding='utf8'))
    return {'model':str(HOME/'Models/DeepSeek-V4-Pro-Qwen3.5-9B-MTP-Q6_K.gguf'),'projector':str(HOME/'Models/mmproj-F32.gguf'),'apiPort':8080,'uiPort':8085,'context':4096,'externalBackend':False}

