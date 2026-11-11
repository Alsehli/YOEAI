"""Lite-only configuration adapter. Never loads or installs a model."""
from pathlib import Path
HOME=Path.home()/'.yoeai-lite-unbound'
APP_DIR=Path(__file__).parent
_config=None
def bind(home,bundle,config):
 global HOME,APP_DIR,_config
 HOME=Path(home);APP_DIR=Path(bundle);_config=config
def read_config():
 if _config is None:raise RuntimeError('Lite agent configuration is not bound.')
 return dict(_config(),modelAlias='alsehli-lite')
