"""Prepared Kandinsky service using the existing chat job contract and GPU gate."""
import atexit
import csv
import io
import json
import os
import re
import subprocess
import struct
import threading
import time
import uuid
from pathlib import Path
from video_inputs import normalise_image

ACTIVE = {'running', 'restoring'}
MODEL = 'Kandinsky 6.0 Lite Distill'


def memory_policy(gpu, available_ram):
    small_gpu = gpu['totalMiB'] < 20000
    return {'memoryProfile': '16gb' if small_gpu else '24gb',
            'quantizedQwen': small_gpu or available_ram < 40 * 1024**3,
            'pinMemory': available_ram >= 64 * 1024**3}


class VideoGenerator:
    def __init__(self, config, home, pause=None, resume=None, gpu_lock=None):
        self.path, self.home = Path(config), Path(home)
        self.pause, self.resume, self.gpu_lock = pause, resume, gpu_lock
        self.lock = threading.RLock(); self.cancelled = threading.Event()
        self.process = self.worker = None; self.closing = False
        self.state = {'status': 'idle', 'message': 'Local video service idle.', 'model': MODEL, 'verified': False}
        atexit.register(self.shutdown)

    def config(self):
        value = json.loads(self.path.read_text(encoding='utf-8-sig'))
        if value.get('engine') != 'kandinsky6-lite-distill':
            raise ValueError('The configured backend must be Kandinsky 6.0 Lite Distill. No legacy fallback is used.')
        for key in ('python', 'worker', 'backendRoot', 'ffmpeg', 'license', 'gpuLock'):
            value[key] = str((self.path.parent / value[key]).resolve())
        for key in ('python', 'worker', 'ffmpeg', 'license'):
            if not Path(value[key]).is_file():
                raise ValueError('Prepared Kandinsky component is missing: ' + key)
        if self.gpu_lock is not None:
            value['gpuLock'] = str(self.gpu_lock)
        return value

    def status(self):
        with self.lock:
            value = dict(self.state)
        if value.get('id') and value['status'] == 'running' and value.get('stage') != 'encoding':
            log = self.home / (value['id'] + '.log')
            if log.is_file():
                with log.open('rb') as stream:
                    stream.seek(max(0, log.stat().st_size - 16000)); tail = stream.read().decode('utf8', 'replace')
                for line in tail.splitlines():
                    if line.startswith('KANDINSKY_EVENT '):
                        try:
                            event = json.loads(line[len('KANDINSKY_EVENT '):]); value.update(stage=event['stage'], message=event['message'])
                        except (ValueError, KeyError):
                            pass
                steps = re.findall(r'Denoising[^\n]*?(\d+)\s*/\s*(\d+)', tail)
                if steps and value.get('stage') == 'generating':
                    step, total = map(int, steps[-1]); value.update(step=step, steps=total, message=f'Creating video and audio locally · step {step} of {total}')
        if value.get('started'):
            value['elapsed'] = round(time.time() - value['started'], 1)
        return value

    def start(self, body):
        cfg = self.config()
        if cfg.get('testingAuthorized') is not True:
            raise ValueError('Kandinsky is prepared but untested. Explicit authorization is required before enabling generation.')
        prompt, seconds = body.get('prompt'), body.get('seconds', 5)
        if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 2000:
            raise ValueError('Describe the video in 1–2,000 characters.')
        if type(seconds) is not int or seconds != 5:
            raise ValueError('The official Lite Distill setup generates five-second clips.')
        image = None; source = body.get('sourceJob')
        if source is not None:
            if not isinstance(source, str) or not re.fullmatch('[0-9a-f]{32}', source) or body.get('image') is not None:
                raise ValueError('Invalid image source.')
            source=bytes.fromhex(source).hex()  # Canonical hex IDs cannot introduce path separators.
            photo = self.home / (source + '.input.png')
            if not photo.is_file():
                raise ValueError('Attach the original image again to regenerate this video.')
            image = photo.read_bytes()
        elif body.get('image') is not None:
            image = normalise_image(body['image'])
        with self.lock:
            if self.worker and self.worker.is_alive():
                raise ValueError('Finish or stop the current video first.')
            self.cancelled.clear(); job = uuid.uuid4().hex
            self.state = {'status': 'running', 'id': job, 'started': time.time(), 'message': 'Preparing Kandinsky…', 'imageGuided': image is not None, 'model': MODEL, 'verified': False}
            self.worker = threading.Thread(target=self.run, args=(cfg, prompt.strip(), job, image), daemon=True)
            self.worker.start()
        return self.status()

    def select_gpu(self, cfg):
        raw = subprocess.check_output(['nvidia-smi', '--query-gpu=index,uuid,name,memory.total,memory.free', '--format=csv,noheader,nounits'], text=True, timeout=10, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        devices = []
        for index, identity, name, total, free in csv.reader(io.StringIO(raw)):
            device = {'index': int(index), 'uuid': identity.strip(), 'name': name.strip(), 'totalMiB': int(total), 'freeMiB': int(free)}
            if device['totalMiB'] >= 15000 and device['freeMiB'] >= cfg.get('minimumFreeMiB', 12000):
                devices.append(device)
        preferred = cfg.get('gpuIndex')
        if preferred is not None:
            devices = [d for d in devices if d['index'] == preferred]
        if not devices:
            raise ValueError('No selected GPU has the configured free-memory budget. Close other GPU jobs; memory pools are not combined.')
        return max(devices, key=lambda d: (d['freeMiB'], d['totalMiB']))

    def execute(self, arguments, log, timeout, env=None):
        with log.open('a', encoding='utf8') as stream:
            with self.lock:
                if self.cancelled.is_set():
                    raise InterruptedError('Video stopped.')
                self.process = subprocess.Popen(arguments, stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT, env=env, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                process = self.process
            try:
                code = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self.stop_process(); raise ValueError('The video job timed out; no substitute video was created.')
        if self.cancelled.is_set():
            raise InterruptedError('Video stopped.')
        if code:
            raise ValueError('The local Kandinsky job failed. See its job log; no legacy backend was substituted.')

    def stop_process(self):
        with self.lock:
            process = self.process
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait(timeout=5)

    def cancel(self):
        self.cancelled.set(); self.stop_process(); return self.status()

    def shutdown(self):
        self.closing = True; self.cancel()
        if self.worker and self.worker is not threading.current_thread():
            self.worker.join(timeout=30)

    def run(self, cfg, prompt, job, image):
        log = self.home / (job + '.log'); request_path = self.home / (job + '.request.json')
        raw = self.home / (job + '.kandinsky.partial.mp4'); encoded = self.home / (job + '.encoded.partial.mp4')
        output = self.home / (job + '.mp4'); photo = self.home / (job + '.input.png')
        lock = Path(cfg['gpuLock']); handle = None; paused = False; started = time.monotonic()
        result = {'id': job, 'model': MODEL, 'verified': False}
        try:
            self.home.mkdir(parents=True, exist_ok=True)
            lock.parent.mkdir(parents=True, exist_ok=True)
            try:
                handle = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                raise ValueError('An image or video job already owns the GPU.')
            os.write(handle, str(os.getpid()).encode())
            if self.pause:
                paused = bool(self.pause())
            gpu = self.select_gpu(cfg)
            import psutil
            policy = memory_policy(gpu, psutil.virtual_memory().available)
            self.state.update(gpu=gpu['name'], memoryPolicy=policy, message='Loading the selected video model…')
            if image is not None:
                photo.write_bytes(image)
            seed = int.from_bytes(os.urandom(4), 'little')
            request = {'executionAuthorized': True, 'variant': 'lite-distill', 'seconds': 5, 'backendRoot': cfg['backendRoot'], 'prompt': prompt, 'image': str(photo) if image is not None else None, 'output': str(raw), 'seed': seed, **policy}
            request_path.write_text(json.dumps(request), encoding='utf8')
            env = dict(os.environ, CUDA_VISIBLE_DEVICES=gpu['uuid'], CUDA_DEVICE_ORDER='PCI_BUS_ID', PYTHONNOUSERSITE='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1')
            self.execute([cfg['python'], '-u', cfg['worker'], '--request', str(request_path)], log, cfg.get('timeoutSeconds', 3600), env)
            if not raw.is_file():
                raise ValueError('The video worker returned no MP4.')
            self.state.update(stage='encoding', message='Saving the five-second MP4 with audio…')
            self.execute([cfg['ffmpeg'], '-hide_banner', '-y', '-i', str(raw), '-map', '0:v:0', '-map', '0:a:0', '-t', '5', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-movflags', '+faststart', str(encoded)], log, 180)
            self.execute([cfg['ffmpeg'], '-hide_banner', '-y', '-i', str(encoded), '-frames:v', '1', str(self.home / (job + '.poster.png'))], log, 60)
            if self.cancelled.is_set():
                raise InterruptedError('Video stopped.')
            poster = self.home / (job + ".poster.png")
            # Exported dimensions can differ from the requested model canvas.
            width, height = struct.unpack(">II", poster.read_bytes()[16:24])
            encoded.replace(output)
            result.update(status='complete', message='Video ready.', url='/videogen/output/' + job, seconds=5, width=width, height=height, fps=24, seed=seed, audio=True, imageGuided=image is not None, textPipeline=False, generationSeconds=round(time.monotonic() - started, 1))
        except InterruptedError as error:
            result.update(status='cancelled', message=str(error))
        except Exception as error:
            result.update(status='error', message=str(error))
        finally:
            # Completed videos and all historical user outputs are untouched.
            for partial in (raw, encoded):
                try:
                    partial.unlink(missing_ok=True)
                except OSError as error:
                    result.setdefault('cleanupWarnings', []).append(str(error))
            with self.lock:
                self.process = None
            if paused and self.resume:
                self.state.update(status='restoring', message='Restoring your chat model…')
                try:
                    self.resume(restore=not self.closing)
                except Exception as error:
                    result.update(chatRestartFailed=True, message=result.get('message', '') + ' Chat restore failed: ' + str(error))
            if handle is not None:
                try:
                    os.close(handle); lock.unlink(missing_ok=True)
                except OSError as error:
                    result.setdefault('cleanupWarnings', []).append(str(error))
            result['totalSeconds'] = round(time.monotonic() - started, 1)
            try:
                (self.home / (job + '.json')).write_text(json.dumps(result, indent=2), encoding='utf8')
            except OSError as error:
                result['persistenceError'] = str(error)
            with self.lock:
                self.state = result
