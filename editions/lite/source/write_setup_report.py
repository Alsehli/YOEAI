from pathlib import Path
import json,hashlib
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from xml.sax.saxutils import escape
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'lite-development/native-setup-20261017/Verification'
deployment=json.loads((OUT/'deployment.json').read_text(encoding='utf-8'))
compiled=json.loads((OUT/'compiled-restricted-test.json').read_text(encoding='utf-8-sig'))
assert compiled['status']=='PASS'
styles=getSampleStyleSheet();styles['BodyText'].fontSize=10;styles['BodyText'].leading=14;styles['Heading2'].textColor=colors.HexColor('#285bb4')
story=[]
def p(text,style='BodyText'):story.extend([Paragraph(escape(text.replace(chr(92)*2,chr(92))),styles[style]),Spacer(1,8)])
p('YOEAI Lite','Title');p('Setup repair and verification | 17 October 2026 | 0.1.1-native-setup')
p('PowerShell-script dependency removed','Heading2')
p('The previous installer called an external Update-Installed-Lite.ps1 file. Windows Restricted execution policy prevented that file from loading. Setup/update now runs bundled Python code and native Windows COM shortcut creation. No permanent or process-level policy weakening is used by the installer.')
rows=[['Status','Check','Evidence'],['PASS','Source regression tests','18 tests, including offline setup, verified downloads, preservation, native shortcuts and rollback.'],['PASS','Compiled setup under Restricted','Execution policy was Restricted. The compiled EXE verified its embedded payload, updated an isolated fixture and created a native shortcut.'],['PASS','Payload integrity','All '+str(compiled['payloadFiles'])+' embedded payload files passed checksum verification.'],['PASS','Model/runtime checks','12 pinned SHA-256 checks passed across the working package and both D: Lite folders. Weights were not recopied.'],['PASS','Branding correction','Setup title uses ASCII text; the visible assistant label is YOEAI Lite. Old named PDF guides/build scripts archived outside delivery folders.'],['PASS','Preservation tests','Existing model, projector, profile bytes and 8,192 context setting preserved in update fixtures.'],['NOT TESTED','Fresh second-PC installation','The affected other PC is not remotely connected. It must receive this new setup and be retested.'],['NOT TESTED','New 8 GB inference benchmark','No fresh target-PC GPU/vision performance claim is made for this fix.'],['NOT SIGNED','Trusted code signature','Development build. Code signing and final commercial release checks remain outstanding.']]
t=Table([[Paragraph(escape(x),styles['BodyText']) for x in row] for row in rows],colWidths=[77,128,306],repeatRows=1,hAlign='LEFT')
t.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e7effb')),('LINEBELOW',(0,0),(-1,-1),.3,colors.HexColor('#d8e0eb')),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]));story.append(t)
story.append(PageBreak());p('Use the repaired package','Title')
for step in ['1. Copy the entire D:\\YOEAI-Lite folder to the other PC. Keep Models, Runtime, Source and Documents with the EXEs.','2. Open the new YOEAI-Lite-Setup.exe inside that folder. This is the single current setup entry point. Do not use an older copied setup.','3. Read the requirements, tick the confirmation box and choose Install / update Lite. Existing installed profiles use the native updater; verified offline files are reused for a new installation.','4. Launch the one YOEAI Lite desktop shortcut. Check text and image replies, then test the desired context on that PC.']:
 p(step)
p('Requirements','Heading2');p('Windows 11 x64; compatible NVIDIA GPU with at least 8 GB VRAM; 16 GB system RAM minimum (32 GB recommended); Microsoft Edge; a compatible NVIDIA driver; 25 GB free SSD space for a new installation. Official CUDA runtime archives and the Q4_K_M model/projector are supplied. If needed, install Microsoft Visual C++ 2015-2022 x64 runtime from https://aka.ms/vs/17/release/vc_redist.x64.exe ; Windows may request administrator approval for that separate dependency.')
p('What remains unchanged','Heading2');p('Existing models, runtime configuration, context and private chat storage are preserved. New per-user data uses YOEAILite. An existing private legacy data directory is kept in place to avoid losing history. It is not a second installed app. No normal-edition app or model was replaced. No inference server was stopped during the isolated verification tests.')
p('Exact delivery checksums','Heading2')
for name,key in [('YOEAILite.exe','appSha256'),('YOEAI-Lite-Setup.exe','setupSha256')]:
 p(name);value=deployment[key];p(value[:32]+' '+value[32:])
p('If the other PC still fails','Heading2');p('Keep the new error message and the online-setup-error.txt file from the current per-user data folder. Reconnect any model drive before retrying. Do not delete models, install duplicate CUDA toolkits or disable Windows protections.')
def footer(c,doc):c.setFont('Helvetica',8);c.setFillColor(colors.HexColor('#64748b'));c.drawString(42,24,'YOEAI Lite - development verification');c.drawRightString(A4[0]-42,24,str(doc.page))
pdf=OUT/'YOEAI-Lite-Setup-Verification.pdf';SimpleDocTemplate(str(pdf),pagesize=A4,leftMargin=42,rightMargin=42,topMargin=36,bottomMargin=38).build(story,onFirstPage=footer,onLaterPages=footer)
print(pdf)
