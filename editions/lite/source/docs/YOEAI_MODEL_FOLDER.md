# Linked models folder

YOEAI now keeps a persistent local model-folder link. On this E: installation the default is E:\YOEAI-Models; Desktop and E: folder shortcuts open it.

In Settings → Local AI model, choose or paste a folder and click Link folder. Add complete single-file GGUF models. A lightweight background scanner refreshes every five seconds, waits for files to stop changing, and lists them by name and size. Choose a detected file, then click Load selected model. Existing loading validation, task gating and rollback are retained. Discovery itself never loads a model or changes profile.json.

Model-folder settings are stored separately in model-folder.json in the application profile. The chosen folder survives restarts. Open folder and Refresh are available. Missing drives produce a recoverable status. Projectors, incomplete headers, partial-download suffixes, unsupported split sets and nested symlinks/junctions are excluded. Detection checks only the small GGUF header; complete structure and runtime compatibility are checked by the existing loader when requested. Safetensors folders are not supported by the existing GGUF engine.

Limits: 200 models, four nested levels, 1,000 directories, 10,000 entries, and a three-second traversal budget per scan. Very large folders show a notice; use a dedicated models folder. No weights are copied, moved, downloaded or deleted.

Verification: 35 deterministic tests cover detection, growth/deletion, persistence, invalid/network paths, bounded traversal, no automatic loading, and endpoint authorization. Reproduce from Lite/Source:

    ..\..\.venv\Scripts\python.exe tests_models/test_library.py

Installed-app/UI verification is recorded separately after deployment.


Installed verification: the Desktop/E: application reports E:\YOEAI-Models and detected three real files. Its list grew automatically from two to three while the UI was open. Choosing the detected Qwen file filled its path without loading it; the input was restored to the current selected model. The saved model profile hash is unchanged. Full runtime loading of those newly discovered files was not part of this folder-discovery test. The app was restarted after the user-requested wait for the earlier load; its selected model is retained with normal on-demand loading.
