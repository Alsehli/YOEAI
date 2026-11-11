from pathlib import Path
import sys
root=Path(__file__).resolve().parents[3];path=root/'build_candidates.py';code=path.read_text(encoding='utf8').replace("dest=root/edition/'Candidate-App'","dest=root/edition/'Candidate-App-Models-20261111'");sys.argv=[str(path),'Lite'];scope={'__file__':str(path),'__name__':'model_folder_build'};exec(compile(code,str(path),'exec'),scope);scope['build']('Lite')
