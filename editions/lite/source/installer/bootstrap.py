"""Small YOEAI installer. Production downloads remain disabled until publication."""
import argparse
import json
import os
import queue
import sys
import threading
from pathlib import Path

from installer.releases import DEFAULT_CONFIG, Installer


def main(default_offline=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    parser.add_argument('--destination', type=Path)
    parser.add_argument('--cache', type=Path)
    parser.add_argument('--offline-folder', type=Path, default=default_offline)
    parser.add_argument('--cli', action='store_true')
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding='utf-8-sig'))
    base = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'YOEAI'
    destination, cache = args.destination or base / 'App', args.cache or base / 'Downloads'
    def make_installer(progress, cancel=None):
        if args.offline_folder is not None:
            from installer.offline import OfflineInstaller
            return OfflineInstaller(config, cache, args.offline_folder, progress, cancel)
        return Installer(config, cache, progress, cancel=cancel)
    if args.cli:
        installer = make_installer(lambda event: print(json.dumps(event), flush=True))
        try:
            result = installer.install(destination)
            print(json.dumps(result))
        except Exception as error:
            print(str(error), file=sys.stderr)
            return 1
        return 0
    import tkinter as tk
    from tkinter import ttk
    window = tk.Tk()
    window.title('YOEAI 3.0 Setup')
    window.geometry('650x330')
    window.resizable(False, False)
    ttk.Label(window, text='YOEAI 3.0', font=('Segoe UI', 20, 'bold')).pack(pady=20)
    ready = config.get('offlineInstallEnabled' if args.offline_folder is not None else 'enabled') is True and bool(config.get('trustedKeys'))
    disabled = 'Offline artifacts are prepared but untested. Installation has not been enabled.' if args.offline_folder is not None else config.get('disabledReason', 'Production downloads are disabled.')
    status = tk.StringVar(value='Ready to verify the signed release.' if ready else disabled)
    ttk.Label(window, textvariable=status, wraplength=580, justify='left').pack(padx=24, pady=10)
    progress = ttk.Progressbar(window, length=580, maximum=100)
    progress.pack(pady=10)
    ttk.Label(window, text='Existing installations and personal data are preserved.\nDownloads use HTTPS, signed metadata and SHA-256 verification.', justify='left').pack(pady=8)
    events, cancelled = queue.Queue(), threading.Event()
    running = False

    def begin():
        nonlocal running
        running = True
        install.config(state='disabled'); cancel.config(state='normal')
        cancelled.clear()
        def task():
            try:
                value = make_installer(events.put, cancelled).install(destination)
                events.put({'phase': 'done', 'message': 'Installed verified files at ' + value['destination']})
            except Exception as error:
                events.put({'phase': 'error', 'message': str(error)})
        threading.Thread(target=task, daemon=True).start()

    def poll():
        nonlocal running
        try:
            for _ in range(200):
                event = events.get_nowait()
                if event['phase'] == 'download':
                    percent = event['received'] / event['total'] * 100
                    progress['value'] = percent
                    status.set(f"{event['id']}: {event['received'] / 1048576:.1f} / {event['total'] / 1048576:.1f} MiB ({percent:.0f}%)")
                elif event.get('message'):
                    status.set(event['message'])
                if event['phase'] in ('done', 'error'):
                    running = False; cancel.config(state='disabled'); install.config(state='normal' if ready else 'disabled')
        except queue.Empty:
            pass
        window.after(100, poll)

    def close():
        if running:
            cancelled.set(); status.set('Stopping safely. Download progress will be kept.'); window.after(200, close)
        else:
            window.destroy()

    install = ttk.Button(window, text='Download and install', command=begin, state='normal' if ready else 'disabled')
    install.pack(pady=6)
    cancel = ttk.Button(window, text='Cancel download', command=cancelled.set, state='disabled')
    cancel.pack()
    window.protocol('WM_DELETE_WINDOW', close)
    window.after(100, poll)
    window.mainloop()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
