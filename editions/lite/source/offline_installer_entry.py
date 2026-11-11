import sys
from pathlib import Path
from installer.bootstrap import main

if __name__ == '__main__':
    root = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent.parent
    raise SystemExit(main(default_offline=root / 'Payload'))
