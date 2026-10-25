# Third-party notices

The application code is GPL-3.0-only. Existing third-party materials keep their original notices:

- PySide6 / Qt: GPL/LGPL options and component-specific terms; not vendored in this source tree. Binary redistribution needs the full appropriate notices and corresponding-source obligations.
- PyInstaller: GPL with its bootloader exception; installed as a build dependency, not vendored here.
- Manrope, Inter, JetBrains Mono: SIL OFL; license texts and pinned provenance in source/assets/fonts.
- markdown-it and included dependencies: license texts and provenance in source/assets/vendor.
- highlight.js: BSD notice in source/assets/vendor/highlight-LICENSE.txt.
- pdfmake: MIT; Roboto font: Apache-2.0; notices/provenance in source/assets/vendor.
- YOEAI visual branding includes user-approved AI-generated mascot assets. Trademark claims do not represent registered rights or clearance. Third-party marks remain with their owners.

llama.cpp, NVIDIA runtime components, GGUF model weights and vision projectors are external and excluded. This source publication does not certify their redistribution eligibility or compatibility. Shipping binaries requires a separate full dependency/license audit.

Current adapters also use separately installed Pillow, ReportLab, psutil, pywin32, pywinauto, comtypes, Playwright, ddgs, primp and lxml. Their own distribution licenses apply; pinned direct application/build dependencies are in requirements-build.txt. Optional worker source is included, but PyTorch, Transformers, sounddevice, Kokoro/eSpeak, model weights, Ghidra/JDK, Unity and Adobe software are not vendored. Font, rendering and preview-vendor directories retain their packaged license/provenance files. Do not infer binary redistribution clearance from a successful source build.
