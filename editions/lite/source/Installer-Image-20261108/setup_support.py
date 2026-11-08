"""Installer-owned staging only; existing apps, profiles and models are never removed."""
import os, shutil, tempfile
from pathlib import Path

def check_path(path):
    for part in (Path(path), *Path(path).parents):
        if part.is_symlink() or (os.name == 'nt' and part.exists() and getattr(part.lstat(), 'st_file_attributes', 0) & 0x400):
            raise ValueError('Choose a folder without redirected links.')

class StagedInstall:
    def __init__(self, app, state, state_file=False):
        self.app, self.state = Path(app).absolute(), Path(state).absolute()
        self.state_file, self.committed = state_file, False
        self.app_stage = self.state_stage = None
        self.promoted_state = False
    def __enter__(self):
        check_path(self.app); check_path(self.state)
        if self.app.exists() or self.state.exists():
            raise ValueError('An existing installation or profile was preserved. Open the existing app, or choose a new installation location.')
        if self.app == self.state or self.app.is_relative_to(self.state) or self.state.is_relative_to(self.app):
            raise ValueError('Application and profile locations must be separate.')
        self.app.parent.mkdir(parents=True, exist_ok=True)
        self.state.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.app_stage = Path(tempfile.mkdtemp(prefix='.yoeai-setup-', dir=self.app.parent))
            self.state_stage = Path(tempfile.mkdtemp(prefix='.yoeai-profile-', dir=self.state.parent))
        except Exception:
            self.cleanup(); raise
        return self
    def commit(self):
        check_path(self.app); check_path(self.state)
        if self.app.exists() or self.state.exists():
            raise ValueError('The destination appeared during setup. Existing data was preserved.')
        staged = self.state_stage / self.state.name if self.state_file else self.state_stage
        staged.rename(self.state); self.promoted_state = True
        try:
            self.app_stage.rename(self.app)
        except Exception:
            # Move only the state we just created back into our private staging.
            self.state.rename(staged); self.promoted_state = False
            raise
        self.committed = True
    def cleanup(self):
        for path in (self.app_stage, self.state_stage):
            if path is not None and path.exists():
                check_path(path)
                shutil.rmtree(path)
    def __exit__(self, kind, value, traceback):
        try: self.cleanup()
        except OSError:
            if kind is None: raise
        return False
