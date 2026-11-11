"""Preparation only: download pinned official Lite Distill assets; never import AI runtimes."""
import argparse
import concurrent.futures
import hashlib
import json
import time
import urllib.request
from pathlib import Path

REPO = 'kandinskylab/Kandinsky-6.0-Lite-distill-5s-Diffusers'
REVISION = '4c487e8b4aeeb9059e5a77905aa2ddb59ec28f81'


def prepare(metadata, destination):
    meta = json.loads(Path(metadata).read_text(encoding='utf-8-sig'))
    if meta['sha'] != REVISION or meta['id'] != REPO:
        raise ValueError('Unexpected upstream model snapshot. Never substitute Pro weights.')
    root = Path(destination).resolve(); root.mkdir(parents=True, exist_ok=True)
    selected = [row for row in meta['siblings'] if not row['rfilename'].startswith('assets/')]
    def download(row):
        name = row['rfilename']; target = (root / name).resolve()
        if not target.is_relative_to(root):
            raise ValueError('Unsafe upstream filename.')
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_name(target.name + '.part')
        expected = row.get('lfs', {}).get('sha256')
        def valid(path):
            if not path.is_file() or path.stat().st_size != row['size']:
                return False
            if expected:
                with path.open('rb') as stream:
                    return hashlib.file_digest(stream, 'sha256').hexdigest() == expected
            data = path.read_bytes()
            return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() == row['blobId']
        if not valid(target):
            url = f'https://huggingface.co/{REPO}/resolve/{REVISION}/{name}'
            for attempt in range(5):
                try:
                    offset = partial.stat().st_size if partial.is_file() else 0
                    if offset >= row['size']:
                        if valid(partial):
                            partial.replace(target); break
                        # Truncate only this exact preparer's partial file.
                        with partial.open('wb'):
                            pass
                        offset = 0
                    headers = {'Accept-Encoding': 'identity'}
                    if offset:
                        headers['Range'] = f'bytes={offset}-'
                    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=90) as response:
                        if not response.geturl().startswith('https://'):
                            raise ValueError('HTTPS download required.')
                        if response.status == 206:
                            if not response.headers.get('Content-Range', '').startswith(f'bytes {offset}-'):
                                raise ValueError('Invalid resumed download.')
                        elif response.status == 200:
                            offset = 0
                        else:
                            raise ValueError('Unexpected download response.')
                        received = offset; announced = offset
                        with partial.open('ab' if offset else 'wb') as output:
                            while chunk := response.read(8 * 1024 * 1024):
                                received += len(chunk)
                                if received > row['size']:
                                    raise ValueError('Asset exceeds published size.')
                                output.write(chunk)
                                if received - announced >= 256 * 1024 * 1024:
                                    print(json.dumps({'file': name, 'received': received, 'total': row['size']}), flush=True); announced = received
                    if not valid(partial):
                        raise ValueError('Downloaded asset failed upstream integrity check.')
                    partial.replace(target); break
                except Exception:
                    if attempt == 4:
                        raise
                    time.sleep(min(2 ** attempt, 8))
        with target.open('rb') as stream:
            sha256 = hashlib.file_digest(stream, 'sha256').hexdigest()
        result = {'path': name, 'bytes': target.stat().st_size, 'sha256': sha256, 'upstreamSHA256': expected, 'upstreamGitBlob': row['blobId'], 'url': f'https://huggingface.co/{REPO}/resolve/{REVISION}/{name}'}
        print(json.dumps({'completed': name, 'bytes': result['bytes']}), flush=True)
        return result
    records = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for record in pool.map(download, selected):
            records.append(record)
    manifest = {'repository': REPO, 'revision': REVISION, 'variant': 'Lite Distill 5s', 'preparationOnly': True, 'inferenceRun': False, 'files': records, 'totalBytes': sum(row['bytes'] for row in records)}
    (root.parent / 'model-assets.json').write_text(json.dumps(manifest, indent=2), encoding='utf8')
    print(json.dumps({'downloadComplete': True, 'files': len(records), 'bytes': manifest['totalBytes']}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('upstream_metadata', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    prepare(args.upstream_metadata, args.destination)
