"""Additive, offline installer for tagged source candidates, not a production updater."""
import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def archive_entries(archive, limit):
    entries = archive.infolist()
    if len(entries) > 100000 or sum(x.file_size for x in entries) > limit:
        raise ValueError('Payload exceeds the compiled extraction budget.')
    seen = set()
    for entry in entries:
        name = entry.orig_filename
        path = PurePosixPath(name)
        parts = path.parts
        if not parts or path.is_absolute() or path.as_posix() != name.rstrip('/') or '\\' in name or any(
            part in ('.', '..') or part.endswith((' ', '.')) or re.search(r'[<>:"|?*\x00-\x1f]', part)
            or re.fullmatch(r'(?i)(CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])(?:\..*)?', part)
            for part in parts
        ):
            raise ValueError('Unsafe payload path.')
        key = name.rstrip('/').casefold()
        if key in seen or stat.S_ISLNK(entry.external_attr >> 16):
            raise ValueError('Duplicate or linked payload entry.')
        seen.add(key)
    return entries


def verify(package, expected, budget):
    if digest(package) != expected:
        raise ValueError('Payload checksum failed. Keep the matching setup and ZIP together.')
    with zipfile.ZipFile(package) as archive:
        entries = archive_entries(archive, budget)
        manifest = json.loads(archive.read('candidate-provenance.json'))
        rows = manifest['files']
        names = {entry.filename for entry in entries if not entry.is_dir()}
        if names != {row['path'] for row in rows} | {'candidate-provenance.json'}:
            raise ValueError('Payload inventory differs from the build manifest.')
        for row in rows:
            entry = archive.getinfo(row['path'])
            if entry.file_size != row['bytes']:
                raise ValueError('Payload size differs from the build manifest.')
            with archive.open(entry) as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != row['sha256']:
                    raise ValueError('Payload file checksum failed.')
    return manifest


def install(package, expected, budget, destination):
    manifest = verify(package, expected, budget)
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError('Destination already exists and was preserved. Choose a new folder.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.yoeai-candidate-', dir=destination.parent))
    try:
        with zipfile.ZipFile(package) as archive:
            for entry in archive_entries(archive, budget):
                target = stage.joinpath(*PurePosixPath(entry.filename).parts)
                if not target.resolve().is_relative_to(stage.resolve()):
                    raise ValueError('Payload path escapes the new stage.')
                if entry.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(entry) as source, target.open('xb') as output:
                        shutil.copyfileobj(source, output)
        for row in manifest['files']:
            if digest(stage / row['path']) != row['sha256']:
                raise ValueError('Installed file verification failed.')
        stage.rename(destination)
    finally:
        if stage.exists():
            # stage is the exact directory created by mkdtemp, never a payload path.
            shutil.rmtree(stage)
    return {'installed': str(destination), 'sourceCommit': manifest['sourceCommit'],
            'verifiedFiles': len(manifest['files']), 'functionallyQualified': False}


def main(edition, version, package_name, expected, budget):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true')
    parser.add_argument('--destination', type=Path)
    parser.add_argument('--test-install', type=Path, help='Additive extraction test; does not launch the app')
    args = parser.parse_args()
    root = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path.cwd()
    package = root / package_name
    if args.verify:
        value = verify(package, expected, budget)
        print(json.dumps({'verified': True, 'sourceCommit': value['sourceCommit']}))
        return
    if args.test_install:
        print(json.dumps(install(package, expected, budget, args.test_install)))
        return
    destination = args.destination or Path(os.environ['LOCALAPPDATA']) / 'YOEAI-SourceCandidates' / edition / version
    import tkinter as tk
    from tkinter import messagebox
    window = tk.Tk()
    window.title('YOEAI ' + edition + ' source-candidate setup')
    window.geometry('630x300')
    tk.Label(window, text='Tagged-source candidate — not a qualified production release', font=('Segoe UI', 13, 'bold')).pack(pady=15)
    tk.Label(window, text='Installs into a new folder. Existing apps, shortcuts, profiles and models are preserved.\nNo models are downloaded. Optional voice/media engines are not bundled.\nNative inference is available only when verified runtime inputs accompanied the build.\nInstallation does not launch the app or run model inference.', justify='left').pack(pady=10)
    label = tk.Label(window, text=str(destination), wraplength=600)
    label.pack(pady=10)
    def begin():
        button.config(state='disabled')
        window.update_idletasks()
        try:
            result = install(package, expected, budget, destination)
            label.config(text='Files installed and verified: ' + result['installed'])
        except Exception as error:
            messagebox.showerror('Installation stopped', str(error))
    button = tk.Button(window, text='Install separate source candidate', command=begin)
    button.pack()
    window.mainloop()
