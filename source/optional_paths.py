"""Resolve explicitly configured optional-runtime files beside their configuration."""
import json
from pathlib import Path


def load_paths(config, required, defaults=None):
    config = Path(config).resolve()
    try:
        value = json.loads(config.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError) as error:
        raise ValueError('Cannot read the local voice configuration.') from error
    if not isinstance(value, dict):
        raise ValueError('The local voice configuration must be an object.')
    result = dict(value)
    for key, default in (defaults or {}).items():
        result.setdefault(key, str(default))
    for key in (*required, *(defaults or {})):
        raw = result.get(key)
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError('Local voice configuration is missing ' + key + '.')
        path = Path(raw)
        result[key] = str((path if path.is_absolute() else config.parent / path).resolve())
        if key in required and not Path(result[key]).exists():
            raise ValueError('Local voice files are missing: ' + key + '.')
    return result
