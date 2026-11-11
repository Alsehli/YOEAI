"""Local TLS fixture tests. No production endpoint or real model is contacted."""
import base64
import hashlib
import io
import ipaddress
import json
import os
import shutil
import socket
import ssl
import tempfile
import threading
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import Mock

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa
from cryptography.x509.oid import NameOID
from installer.releases import Installer, ReleaseError, canonical, client, verify_manifest, relative


class ReleaseFixtures(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.private = ed25519.Ed25519PrivateKey.generate()
        public = self.private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.requests, self.events = [], []
        self.interrupt, self.ignore_range, self.bad_range, self.corrupt = False, False, False, False
        now = datetime.now(timezone.utc)
        tls_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'YOEAI local test fixture')])
        certificate = x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(tls_key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=1)).not_valid_after(now+timedelta(days=1)).add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]), critical=False).sign(tls_key, hashes.SHA256())
        cert, key = self.root/'test.pem', self.root/'test.key'
        cert.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
        key.write_bytes(tls_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        fixture = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                fixture.requests.append((self.path, self.headers.get('Range')))
                if self.path == '/manifest.json':
                    data = canonical(fixture.envelope)
                elif self.path == '/redirect':
                    self.send_response(302); self.send_header('Location', 'http://127.0.0.1/unsafe'); self.end_headers(); return
                else:
                    data = fixture.blobs[self.path]
                    if fixture.corrupt and self.path == '/text':
                        data = b'X' * len(data)
                size, offset = len(data), 0
                range_value = self.headers.get('Range')
                if range_value and not fixture.ignore_range:
                    offset = int(range_value.removeprefix('bytes=').removesuffix('-'))
                    self.send_response(206)
                    self.send_header('Content-Range', f'bytes {offset+1 if fixture.bad_range else offset}-{size-1}/{size}')
                else:
                    self.send_response(200)
                self.send_header('Content-Length', str(size-offset)); self.end_headers()
                if fixture.interrupt and self.path == '/text':
                    fixture.interrupt = False
                    self.wfile.write(data[offset:offset+size//2]); self.wfile.flush()
                    self.connection.shutdown(socket.SHUT_RDWR); self.connection.close()
                else:
                    try:
                        self.wfile.write(data[offset:])
                    except (BrokenPipeError, ConnectionResetError, ssl.SSLEOFError):
                        pass  # Expected when a rejected range/redirect closes early.
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); tls.minimum_version = ssl.TLSVersion.TLSv1_2; tls.load_cert_chain(cert, key)
        self.server.socket = tls.wrap_socket(self.server.socket, server_side=True)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.url = f'https://127.0.0.1:{self.server.server_address[1]}'
        self.config = {'enabled': True, 'manifestUrl': self.url+'/manifest.json', 'channel': 'stable', 'trustedKeys': {'fixture': base64.b64encode(public).decode()}}
        self.opener = client(ssl.create_default_context(cafile=str(cert)))
        package = io.BytesIO()
        with zipfile.ZipFile(package, 'w') as archive:
            archive.writestr('YOEAI.exe', b'FIXTURE ONLY - NOT A REAL EXECUTABLE')
        self.blobs = {'/application': package.getvalue()}
        kinds = ['application', 'text', 'image', 'video', 'speechRecognition', 'speechSynthesis']
        assets = []
        for kind in kinds:
            data = self.blobs.setdefault('/'+kind, (kind.encode()+b' fixture ') * 16000)
            assets.append({'id': kind, 'kind': kind, 'version': 'fixture-1', 'format': 'zip' if kind=='application' else 'file', 'path': 'app' if kind=='application' else f'Models/{kind}.bin', 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(), 'url': self.url+'/'+kind, **({'unpackedBytes': 1024} if kind=='application' else {})})
        self.payload = {'schemaVersion': 1, 'product': 'YOEAI', 'channel': 'stable', 'version': '3.0.0-fixture', 'issuedAt': (now-timedelta(minutes=1)).isoformat(), 'expiresAt': (now+timedelta(hours=1)).isoformat(), 'entrypoint': 'app/YOEAI.exe', 'assets': assets}
        self.sign()
        self.cache, self.base = self.root/'cache', self.root/'install'

    def sign(self):
        self.envelope = {'keyId': 'fixture', 'signed': self.payload, 'signature': base64.b64encode(self.private.sign(canonical(self.payload))).decode()}

    def installer(self, **kwargs):
        return Installer(self.config, self.cache, self.events.append, self.opener, **kwargs)

    def test_disabled_configuration_makes_no_network_request(self):
        self.config['enabled'] = False
        network = Mock()
        with self.assertRaisesRegex(ReleaseError, 'disabled'):
            Installer(self.config, self.cache, opener=network).install(self.base)
        network.open.assert_not_called()

    def test_signed_versioned_release_installs_and_reports_progress(self):
        result = self.installer().install(self.base)
        self.assertTrue(Path(result['entrypoint']).is_file())
        self.assertTrue(result['signatureVerified'] and result['sha256Verified'])
        self.assertEqual(result['version'], '3.0.0-fixture')
        self.assertTrue(any(e['phase']=='download' and e['received']==e['total'] for e in self.events))
        self.assertEqual(self.requests[0][0], '/manifest.json')

    def test_interrupted_download_resumes_without_changing_old_install(self):
        old = self.base/'2.0'; old.mkdir(parents=True); (old/'personal.txt').write_text('preserve')
        self.interrupt = True
        with self.assertRaises(Exception):
            self.installer().install(self.base)
        self.assertFalse((self.base/self.payload['version']).exists())
        self.assertTrue(list(self.cache.glob('*.part')))
        self.assertEqual((old/'personal.txt').read_text(), 'preserve')
        self.installer().install(self.base)
        self.assertTrue(any(path=='/text' and value for path,value in self.requests))
        self.assertEqual((old/'personal.txt').read_text(), 'preserve')

    def test_server_ignoring_range_restarts_safely(self):
        asset = self.payload['assets'][1]
        self.cache.mkdir(); (self.cache/(asset['sha256']+'.part')).write_bytes(self.blobs['/text'][:100])
        self.ignore_range = True
        self.assertEqual(self.installer().download(asset).read_bytes(), self.blobs['/text'])

    def test_invalid_resume_range_rejected_without_appending(self):
        asset = self.payload['assets'][1]
        self.cache.mkdir(); part=self.cache/(asset['sha256']+'.part'); part.write_bytes(self.blobs['/text'][:100])
        self.bad_range = True
        with self.assertRaisesRegex(ReleaseError, 'resume range'):
            self.installer().download(asset)
        self.assertEqual(part.stat().st_size, 100)

    def test_tampered_signature_blocks_all_payload_requests(self):
        self.payload['version'] = '3.0.1'
        with self.assertRaisesRegex(ReleaseError, 'signature'):
            self.installer().install(self.base)
        self.assertEqual(len(self.requests), 1)

    def test_unknown_key_rejected(self):
        self.envelope['keyId'] = 'unknown'
        with self.assertRaisesRegex(ReleaseError, 'signature'):
            self.installer().install(self.base)

    def test_expired_release_rejected(self):
        self.payload['expiresAt'] = (datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat(); self.sign()
        with self.assertRaisesRegex(ReleaseError, 'expired'):
            self.installer().install(self.base)

    def test_hash_mismatch_preserves_existing_install(self):
        old = self.base/'3.0.0'; old.mkdir(parents=True); marker=old/'keep'; marker.write_text('keep')
        self.corrupt = True
        with self.assertRaisesRegex(ReleaseError, 'checksum'):
            self.installer().install(self.base)
        self.assertEqual(marker.read_text(), 'keep')
        self.assertFalse((self.base/self.payload['version']).exists())

    def test_legacy_release_and_missing_capability_rejected(self):
        self.payload['version'] = '2.1.0'; self.sign()
        with self.assertRaisesRegex(ReleaseError, 'legacy'):
            verify_manifest(self.envelope, self.config)
        self.payload['version']='3.0.0'; self.payload['assets'].pop(); self.sign()
        with self.assertRaisesRegex(ReleaseError, 'missing'):
            verify_manifest(self.envelope, self.config)

    def test_https_only_including_redirects(self):
        self.config['manifestUrl'] = 'http://127.0.0.1/unsafe'
        with self.assertRaisesRegex(ReleaseError, 'HTTPS'):
            self.installer().manifest()
        self.assertFalse(self.requests)
        self.config['manifestUrl'] = self.url+'/redirect'
        with self.assertRaisesRegex(ReleaseError, 'HTTPS'):
            self.installer().manifest()

    def test_cancelled_install_preserves_existing_files(self):
        cancel = threading.Event(); cancel.set()
        with self.assertRaisesRegex(ReleaseError, 'cancelled'):
            self.installer(cancel=cancel).install(self.base)
        self.assertFalse(self.base.exists())

    def test_mid_download_cancellation_keeps_recoverable_cache(self):
        cancel=threading.Event()
        def progress(event):
            self.events.append(event)
            if event['phase']=='download' and event['id']=='text':
                cancel.set()
        instance=Installer(self.config,self.cache,progress,self.opener,cancel)
        with self.assertRaisesRegex(ReleaseError,'cancelled'):
            instance.install(self.base)
        self.assertTrue(list(self.cache.glob('*.part')))
        self.assertFalse((self.base/self.payload['version']).exists())
        self.installer().install(self.base)
        self.assertTrue((self.base/self.payload['version']/'app/YOEAI.exe').is_file())

    def test_no_trusted_key_blocks_network(self):
        self.config['trustedKeys']={}
        network=Mock()
        with self.assertRaisesRegex(ReleaseError,'signing key'):
            Installer(self.config,self.cache,opener=network).install(self.base)
        network.open.assert_not_called()

    def test_archive_traversal_rejected_and_stage_cleaned(self):
        data=io.BytesIO()
        with zipfile.ZipFile(data,'w') as archive:
            archive.writestr('../escaped.txt','escape')
        blob=data.getvalue(); asset=self.payload['assets'][0]; self.blobs['/application']=blob; asset.update(bytes=len(blob),sha256=hashlib.sha256(blob).hexdigest()); self.sign()
        with self.assertRaisesRegex(ReleaseError, 'relative'):
            self.installer().install(self.base)
        self.assertFalse(list(self.base.glob('.yoeai-stage-*')))
        self.assertFalse(list(self.root.rglob('escaped.txt')))

    def test_existing_version_not_replaced(self):
        self.installer().install(self.base)
        entry=self.base/self.payload['version']/'app/YOEAI.exe'; before=entry.read_bytes()
        with self.assertRaisesRegex(ReleaseError, 'already exists'):
            self.installer().install(self.base)
        self.assertEqual(entry.read_bytes(),before)

    def test_windows_paths_reject_escapes_and_aliases(self):
        for path in ['../bad','C:/bad','a\\bad','/bad','a/./b','a//b','CON.txt','a/file.','a/ADS:data','a/NUL','a/LPT1.txt']:
            with self.subTest(path=path), self.assertRaises(ReleaseError):
                relative(path)

    def test_disjoint_archives_can_share_app_root(self):
        blob=io.BytesIO()
        with zipfile.ZipFile(blob,'w') as archive:
            archive.writestr('support.dll',b'support fixture')
        data=blob.getvalue();self.blobs['/support']=data
        self.payload['assets'].append({'id':'support','kind':'support','version':'fixture-1','format':'zip','path':'app','bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'url':self.url+'/support','unpackedBytes':1000})
        self.sign();result=self.installer().install(self.base)
        self.assertEqual((Path(result['destination'])/'app/support.dll').read_bytes(),b'support fixture')

    def test_offline_signed_assets_never_contact_network(self):
        from installer.offline import OfflineInstaller
        payload=self.root/'offline';payload.mkdir()
        for asset in self.payload['assets']:
            asset['offlinePath']=asset['id']+'.data'
            (payload/asset['offlinePath']).write_bytes(self.blobs['/'+asset['id']])
        self.sign();(payload/'manifest.json').write_bytes(canonical(self.envelope))
        config=dict(self.config,offlineInstallEnabled=True,enabled=False)
        instance=OfflineInstaller(config,self.cache,payload,self.events.append);instance.opener=Mock()
        result=instance.install(self.base)
        instance.opener.open.assert_not_called()
        self.assertTrue(Path(result['entrypoint']).is_file())

    def test_long_windows_archive_path(self):
        self.addCleanup(self.cleanup_long_fixture)
        from installer.releases import beneath
        name='deep/'*45+'file.txt';buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,'w') as archive:
            archive.writestr(name,b'long path fixture')
        data=buffer.getvalue();self.blobs['/application']=data
        asset=self.payload['assets'][0];asset.update(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
        self.payload['entrypoint']='app/'+name.replace('file.txt','YOEAI.exe')
        buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,'w') as archive:
            archive.writestr(name,b'long path fixture');archive.writestr(name.replace('file.txt','YOEAI.exe'),b'exe fixture')
        data=buffer.getvalue();self.blobs['/application']=data;asset.update(bytes=len(data),sha256=hashlib.sha256(data).hexdigest());self.sign()
        result=self.installer().install(self.base)
        self.assertEqual(beneath(Path(result['destination']),'app/'+name).read_bytes(),b'long path fixture')

    def cleanup_long_fixture(self):
        root=self.root.resolve()
        if root.parent != Path(tempfile.gettempdir()).resolve() or not root.name.startswith('tmp'):
            raise RuntimeError('Unexpected fixture cleanup path')
        if root.exists():
            shutil.rmtree('\\\\?\\'+str(root) if os.name=='nt' else str(root))

    def test_failed_long_archive_removes_only_owned_stage(self):
        name='deep/'*45+'file.txt';buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,'w') as archive:archive.writestr(name,b'fixture')
        data=buffer.getvalue();self.blobs['/application']=data
        self.payload['assets'][0].update(bytes=len(data),sha256=hashlib.sha256(data).hexdigest());self.sign()
        with self.assertRaisesRegex(ReleaseError,'entry point'):
            self.installer().install(self.base)
        self.assertFalse(list(self.base.glob('.yoeai-stage-*')))


if __name__ == '__main__':
    unittest.main(verbosity=2)
