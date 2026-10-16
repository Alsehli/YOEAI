"""Presentation-only installer agreement; no model or runtime behavior changed."""
import json,hashlib,datetime
from pathlib import Path
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QCheckBox,QTextBrowser,QPushButton,QLabel
POLICY_VERSION='yoeai-2026-10-15-draft-v1'
POLICY_NAME='YOEAI-Product-Policies-DRAFT.pdf'
REQUIREMENTS="""<h2>Before you install YOEAI™</h2><ul><li>Windows 11, 64-bit, on a compatible x86-64 PC</li><li>Compatible NVIDIA GPU with <b>16 GB VRAM</b> for this edition</li><li><b>16 GB RAM minimum; 32 GB recommended</b></li><li>Approximately <b>25 GB free SSD space</b></li><li>Compatible NVIDIA driver; the CUDA backend is supplied</li><li>Internet for downloads and initial commercial activation</li><li>4,096-token starting context; larger contexts depend on memory</li></ul><p>These requirements are for the normal 16 GB edition. Lite is separate. Performance varies. No microphone or speech feature is included.</p><p>Vendor activation is intended for one active registered computer, with transfer and unlimited offline verification after activation. Applicable GPL and other open-source rights are preserved.</p><p><b>Unsigned preview / policy draft:</b> this is not an approved customer release. Policies are not effective; live purchases remain disabled.</p>"""
def add_agreement(layout,button,parent,app_dir):
 browser=QTextBrowser(parent);browser.setObjectName('installation-requirements');browser.setHtml(REQUIREMENTS);browser.setMinimumHeight(220);layout.addWidget(browser)
 link=QPushButton('Read privacy, license, refund and support policies (PDF)',parent);link.setObjectName('read-installation-policies');policy=Path(app_dir)/POLICY_NAME
 link.clicked.connect(lambda:QDesktopServices.openUrl(QUrl.fromLocalFile(str(policy))));link.setEnabled(policy.is_file());layout.addWidget(link)
 wording=QLabel('I have reviewed the technical requirements, confirm my PC meets them, understand and agree to the product terms, and acknowledge the privacy notice.',parent);wording.setWordWrap(True);layout.addWidget(wording)
 checkbox=QCheckBox('I understand and agree',parent);checkbox.setObjectName('installation-agreement');checkbox.setChecked(False);checkbox.setStyleSheet('QCheckBox{padding:12px 0}');checkbox.setToolTip('Required before installation starts. Open-source license rights are preserved.');layout.addWidget(checkbox)
 note=QLabel('Required. This box is never preselected. Policy version: '+POLICY_VERSION,parent);note.setWordWrap(True);layout.addWidget(note);button.setEnabled(False);checkbox.toggled.connect(lambda checked:button.setEnabled(checked and policy.is_file()));return checkbox,policy

def save_acceptance(home,policy):
 if not policy.is_file():raise RuntimeError('The bundled policy PDF is missing. Installation cannot continue.')
 record={'policyVersion':POLICY_VERSION,'policySha256':hashlib.sha256(policy.read_bytes()).hexdigest(),'edition':'16gb','acceptedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'requirementsConfirmed':True,'productTermsAccepted':True,'privacyNoticeAcknowledged':True,'policyState':'draft-preview'}
 (Path(home)/'installation-agreement.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
