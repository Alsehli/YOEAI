"""Candidate builds have separate profiles, ports and installation directories."""
import os,sys,json
from pathlib import Path
def initialize():
    if not getattr(sys,'frozen',False):return
    root=Path(sys.executable).parent;marker=root/'candidate.json'
    if not marker.is_file():return
    edition=json.loads(marker.read_text())['edition']
    if edition not in ('Lite','Full'):raise ValueError('Unknown candidate edition.')
    original=os.environ.setdefault('YOEAI_CANDIDATE_ORIGINAL_APPDATA',os.environ['LOCALAPPDATA'])
    base=Path(original)/'YOEAI-Candidates'/edition
    os.environ['LOCALAPPDATA']=str(base);os.environ['YOEAI_ASSISTANT_RUNTIME']=str(root)
    advanced=root/'Models/Qwen3.8-27B-GSQ-RCO-IQ3_S.gguf'
    if edition=='Full' and advanced.is_file():os.environ['YOEAI_ADVANCED_MODEL']=str(advanced)
    home=base/('YOEAILite' if edition=='Lite' else 'AlsehliAI-Preview');home.mkdir(parents=True,exist_ok=True)
    config=home/('profile.json' if edition=='Lite' else 'config.json')
    if not config.exists():
        name='DeepSeek-V4-Pro-Qwen3.5-9B-MTP-'+('Q4_K_M' if edition=='Lite' else 'Q6_K')+'.gguf'
        config.write_text(json.dumps({'model':str(root/'Models'/name),'projector':str(root/'Models/mmproj-F32.gguf'),'context':8192 if edition=='Lite' else 16384,'apiPort':19136 if edition=='Lite' else 19146,'uiPort':19137 if edition=='Lite' else 19147,'loadOnDemand':True,'gpuLayers':99,'inferenceEngine':'native','externalBackend':False,**({'modelMode':'fast'} if edition=='Full' else {})},indent=2),encoding='utf8')
    elif edition=='Lite':
        # Relocate only the bundled model from a previous candidate installation.
        # Custom models, active context and other preferences remain user choices.
        value=json.loads(config.read_text(encoding='utf8'));previous=Path(value.get('model',''));bundled=root/'Models/DeepSeek-V4-Pro-Qwen3.5-9B-MTP-Q4_K_M.gguf';candidate_base=Path(original)/'YOEAI-CandidateBuilds/Lite'
        if previous.is_relative_to(candidate_base) and previous.name==bundled.name and previous!=bundled and bundled.is_file():
            import uuid
            backup=home/('profile-before-candidate-move-'+uuid.uuid4().hex+'.json');backup.write_text(json.dumps(value,indent=2),encoding='utf8');value['model']=str(bundled)
            projector=Path(value.get('projector',''))
            if projector.is_relative_to(candidate_base) and projector.name=='mmproj-F32.gguf':value['projector']=str(root/'Models/mmproj-F32.gguf')
            temporary=config.with_name('profile-'+uuid.uuid4().hex+'.tmp');temporary.write_text(json.dumps(value,indent=2),encoding='utf8');temporary.replace(config)
    if '--qualify-sandbox' in sys.argv:
        from intelligence.qualification import qualify
        qualify(root,home/'Assistant');raise SystemExit(0)
