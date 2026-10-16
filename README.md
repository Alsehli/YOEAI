# YOEAI

Windows desktop source preview for local text and image AI.

Maintainer: Mohamed Yusuf Alsehli ([Alsehli](https://github.com/Alsehli)).
Product information: https://bahraini.online/yoeai

## Release status

Development source snapshot, 16 October 2026. This is **not a signed installer or a customer-ready release**. It is not certified by Microsoft Store or approved by SignPath. Publishing source does not grant either approval.

This snapshot contains the existing normal desktop UI and local launcher modules. It is not a representation that an existing commercial binary was built from this public tree. Lite, commercial activation services, private configuration, model weights, backend executables, and unapproved policy drafts are excluded.

## Build on Windows 11 x64

Use Python 3.11 x64 and a virtual environment:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe build.py
```

The result is `dist/YOEAI/YOEAI.exe` with its supporting files. A launcher alone is not a single-file offline model distribution. The build does not download a model or backend. A local build and UI smoke check do not verify a clean-PC install or GPU inference.

The original source expects local per-user configuration and a separately installed compatible llama.cpp backend, model and vision projector. Existing legacy paths remain in the snapshot. Do not run setup against your working installation: policy drafts are deliberately absent, so the installer agreement remains unavailable. Deployment/setup portability is pending release work.

## Features represented by the source

Local chat UI, Markdown/code formatting, structured charts, requested PDF export, image prompts, local performance displays, startup mascot, custom GGUF workspace and confirmation-based fixed Windows commands. Feature availability depends on backend configuration. No speech or microphone feature is included.

## Licenses and privacy

Original application source is offered under GPL-3.0-only; see LICENSE. Bundled third-party fonts and JavaScript retain their own included notices; see THIRD-PARTY.md. Model weights and NVIDIA runtime files are not included and have separate terms. Brand use does not imply affiliation or endorsement.

Read [PRIVACY.md](PRIVACY.md), [SECURITY.md](SECURITY.md) and [Code signing policy](CODE-SIGNING.md).
