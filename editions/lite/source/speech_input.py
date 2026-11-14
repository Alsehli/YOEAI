"""Bounded offline whisper.cpp dictation. Audio is never sent to a remote API."""
import atexit
import base64
import binascii
import io
import json
import re
import subprocess
import threading
import uuid
import wave
from pathlib import Path

INSTANCE = None
INIT = threading.Lock()


def validate_audio(encoded):
    if not isinstance(encoded, str) or len(encoded) > 2600000:
        raise ValueError('Record up to 60 seconds of audio.')
    try:
        raw = base64.b64decode(encoded, validate=True)
        with wave.open(io.BytesIO(raw), 'rb') as audio:
            if audio.getnchannels() != 1 or audio.getsampwidth() != 2 or audio.getframerate() != 16000:
                raise ValueError('Use mono 16 kHz, 16-bit PCM WAV audio.')
            count = audio.getnframes()
            if not 1600 <= count <= 60 * 16000:
                raise ValueError('Record between 0.1 and 60 seconds.')
            if len(audio.readframes(count)) != count * 2:
                raise ValueError('The WAV audio is incomplete.')
    except (binascii.Error, wave.Error, EOFError) as error:
        raise ValueError('Invalid PCM WAV recording.') from error
    return raw


class Recognition:
    def __init__(self, root, home):
        self.root, self.home = Path(root), Path(home) / 'Dictation'
        self.lock = threading.RLock()
        self.process = None
        self.thread = None
        self.cancelled = threading.Event()
        self.state = {'status': 'idle'}
        atexit.register(self.close)

    def assets(self):
        runtime = self.root / 'SpeechInput/Runtime'
        executable = next((p for p in (runtime / 'Release/whisper-cli.exe', runtime / 'whisper-cli.exe') if p.is_file()), None)
        model = self.root / 'SpeechInput/Models/ggml-tiny.bin'
        if executable is None or not model.is_file():
            raise ValueError('The local dictation runtime or model is missing. Repair the installation.')
        return executable, model

    def status(self):
        with self.lock:
            return dict(self.state)

    def start(self, body):
        raw = validate_audio(body.get('audio'))
        language = body.get('language', 'auto')
        if language not in ('auto', 'en', 'ar'):
            raise ValueError('Unsupported dictation language.')
        executable, model = self.assets()
        with self.lock:
            if self.thread and self.thread.is_alive():
                raise ValueError('Wait for the current transcription or stop it first.')
            self.cancelled.clear()
            self.state = {'status': 'running', 'message': 'Transcribing locally…'}
            try:
                self.thread = threading.Thread(target=self.run, args=(raw, language, executable, model), daemon=True)
                self.thread.start()
            except (RuntimeError, OSError) as error:
                self.thread = None
                self.state = {'status': 'error', 'message': 'Transcription could not start. Try again.'}
                raise ValueError(self.state['message']) from error
        return self.status()

    def run(self, raw, language, executable, model):
        key = uuid.uuid4().hex
        source, output, log = (self.home / (key + suffix) for suffix in ('.wav', '.txt', '.log'))
        result = {'status': 'error', 'message': 'Transcription failed.'}
        try:
            self.home.mkdir(parents=True, exist_ok=True)
            source.write_bytes(raw)
            with log.open('wb') as stream:
                with self.lock:
                    if self.cancelled.is_set():
                        raise InterruptedError()
                    self.process = subprocess.Popen([str(executable), '-m', str(model), '-f', str(source), '-l', language, '-ng', '-t', '4', '-otxt', '-of', str(output.with_suffix(''))], stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                try:
                    code = self.process.wait(timeout=120)
                except subprocess.TimeoutExpired:
                    self.stop()
                    raise ValueError('Transcription timed out. Try a shorter recording.')
            if self.cancelled.is_set():
                raise InterruptedError()
            if code or not output.is_file():
                raise ValueError('The local speech engine failed. Repair the speech runtime.')
            text = output.read_text(encoding='utf-8-sig').strip()[:12000]
            result = {'status': 'complete', 'text': text, 'message': 'Review the transcript before sending.'}
        except InterruptedError:
            result = {'status': 'cancelled', 'message': 'Dictation stopped.'}
        except Exception as error:
            result = {'status': 'error', 'message': str(error)[:300]}
        finally:
            # These are the exact assistant-owned per-job files, never user audio.
            cleanup_failed = False
            for path in (source, output, log):
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    cleanup_failed = True
            if cleanup_failed:
                result = {'status': 'error', 'message': 'Temporary dictation files could not be removed. Check access to the Dictation folder and try again.'}
            with self.lock:
                self.process = None
                self.state = result

    def stop(self):
        self.cancelled.set()
        with self.lock:
            process = self.process
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        return self.status()

    def close(self):
        self.stop()
        if self.thread and self.thread is not threading.current_thread():
            self.thread.join(timeout=10)


def route(handler, post, root, home):
    global INSTANCE
    path = handler.path.split('?', 1)[0]
    if not path.startswith('/speech-input/'):
        return False
    if not handler.allowed() or post and handler.headers.get('Origin') != 'http://' + handler.headers.get('Host', ''):
        handler.reply(403, {'error': 'Use the local YOEAI interface.'})
        return True
    try:
        with INIT:
            if INSTANCE is None:
                INSTANCE = Recognition(root, home)
        if post:
            size = int(handler.headers.get('Content-Length', '0'))
            if handler.headers.get('Transfer-Encoding') or not 0 < size <= 2700000:
                raise ValueError('Invalid recording size.')
            handler.connection.settimeout(20)
            data = handler.rfile.read(size)
            if len(data) != size:
                raise ValueError('Incomplete recording request.')
            body = json.loads(data)
            if not isinstance(body, dict):
                raise ValueError('Invalid recording request.')
            if path == '/speech-input/create':
                result = INSTANCE.start(body)
            elif path == '/speech-input/stop':
                result = INSTANCE.stop()
            else:
                raise ValueError('Unknown dictation operation.')
        elif path == '/speech-input/status':
            result = INSTANCE.status()
        elif path == '/speech-input/models':
            INSTANCE.assets()
            result = {'ready': True, 'model': 'Whisper tiny multilingual', 'device': 'CPU'}
        else:
            raise ValueError('Unknown dictation endpoint.')
        handler.reply(200, result)
    except (OSError, ValueError, TypeError) as error:
        handler.reply(400, {'error': str(error)})
    return True
