"""Offline setup bootstrap: executable and verified Payload folder travel together."""
import os,sys,json
from pathlib import Path
import online_setup as setup
setup.PAYLOAD=Path(sys.executable).parent/'Payload' if getattr(sys,'frozen',False) else Path(__file__).parent.parent/'Payload'
setup.OFFLINE_ROOT=setup.PAYLOAD
os.environ['YOEAI_OFFLINE_ONLY']='1'
if '--verify' in sys.argv:
    count=setup.verify_payload()
    report=Path(sys.argv[sys.argv.index('--verify')+1]) if len(sys.argv)>sys.argv.index('--verify')+1 else Path(sys.executable).parent/'Setup-verification.json'
    report.write_text(json.dumps({'verifiedFiles':count,'offline':True,'passed':True},indent=2),encoding='utf8')
elif '--test-install' in sys.argv:
    root=Path(sys.argv[sys.argv.index('--test-install')+1]).resolve()
    if root.exists():raise ValueError('Test destination already exists.')
    root.mkdir(parents=True)
    setup.DATA=root/'Profile/YOEAILite'
    setup.desktop_folder=lambda:root/'Desktop'
    result=setup.install()
    (root/'result.json').write_text(json.dumps({'result':result,'profile':str(setup.DATA)},indent=2),encoding='utf8')
else:setup.main()
