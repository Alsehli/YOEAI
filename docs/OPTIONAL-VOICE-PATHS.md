# Portable Normal voice configuration

Normal dictation reads `SpeechInput/config.json`; interactive voice reads `SpeechInput/interactive-config.json` beside the application. Required `python`, `worker`, `model` and (for interactive voice) `speech` values may be absolute paths to existing external assets, or relative paths resolved beside the configuration file. This preserves existing installations while allowing a complete voice directory to move with the application. The interactive audio worker uses the same base for its model and synthesis assets, regardless of the application's working directory.

Example interactive configuration, with each referenced asset supplied separately:

```json
{"python":"Runtime/python.exe","worker":"interactive_worker.py","model":"Models/recognizer","speech":"../Speech"}
```

Dictation's optional `cache` value uses the same relative base. When omitted, the cache defaults to the current profile's `Dictation/Cache` directory. Resolving settings does not create a cache, download dependencies, start a worker or activate a microphone. Missing files and malformed configuration produce a local setup error. Reuse existing verified models rather than downloading another copy just to change paths.

This fixes configuration portability only. Runtime/model licenses, independent worker operation, offline behavior, microphone/speaker checks, resource use and clean-PC qualification remain open under issue #7. The Lite whisper.cpp dictation implementation uses its separate bundled `SpeechInput` layout and is unaffected by this Normal path fix.
