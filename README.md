# YOEAI 2.0

A personal, non-profit Windows AI assistant with local models and the YOE fox identity.

Maintainer: [Mohamed Yusuf Alsehli](https://github.com/Alsehli). [Project website](https://yoeai.online).

## Release candidate — 25 October 2026

This is the current **Normal 16GB source release candidate**, based on installed build 2.0.20261025.4 plus the verified voice error-display fix. It is an unsigned development release, not a new clean-PC-qualified installer. Purchases are not offered by this repository.

The tree includes the current desktop interface, six Mini YOE agents (Research, Code, Windows, Update, Reverse and Game Studio), local memory, visual components, PDF tools, web-search integration, optional media adapters and Interactive Voice. Availability depends on separately configured runtimes and models. No weights, customer data, passwords, payment service, private profile or GPU backend executable is included.

### Voice
Interactive Voice is below Create Video. Its settings select the shared Fast Qwen3.5 9B or Advanced Qwen3.8 27B backend. End voice before switching. Microphone activation is explicit; recognized words do not directly authorize tools. Speech requires the existing external Python 3.11/Bark Pro/Kokoro runtime and local model files; downloading source alone does not install them.

## Build on Windows

The verified local build environment uses Python 3.13 x64; speech workers use a separate Python 3.11 environment. Install pinned application/build requirements:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe tools/check_release.py
.\.venv\Scripts\python.exe tools/test_portable.py
.\.venv\Scripts\python.exe build.py
```

The result is `dist/YOEAI/YOEAI.exe` plus supporting files. This build does not install models, CUDA, optional runtimes or production settings. Configure a compatible local llama.cpp backend and GGUF/projector files using the existing application configuration. Legacy developer paths still exist in optional adapters; see [setup and limits](docs/SETUP.md).

## Verification

- Full installed-source regression qualification: **384 tests passed** on Windows on 25 October 2026.
- 87 Python source files and 57 JavaScript assets passed syntax checks in that audit.
- Voice model switching and real local playback verified with both installed models.
- Native voice layout tested at 1366×768, 1920×1080 and 2560×1440.

Many regression tests use mocks/disposable fixtures. This does not certify every real Adobe/Unity workflow, hardware configuration or media generation request. CI runs a portable subset; machine-specific tests are retained for appropriately configured Windows machines. Read [QA results](docs/QA-20261025.md) and [release checklist](docs/RELEASE-CHECKLIST.md).

## Contribute and support

[Contribution guide](CONTRIBUTING.md) � [Report a bug](https://github.com/Alsehli/YOEAI/issues/new/choose) � [Optional project support](https://yoeai.online/contribute). Support does not buy software or priority access.

## License and privacy

Application source: GPL-3.0-only, [LICENSE](LICENSE). Third-party assets retain their notices; see [THIRD-PARTY.md](THIRD-PARTY.md). Optional models, runtimes and applications have separate terms. [Privacy](PRIVACY.md) · [Security](SECURITY.md) · [Code signing](CODE-SIGNING.md).

Lite has a different packaging/framework configuration and is not replaced by this Normal source tree. The existing Normal/Lite setup executables predate this candidate and are not attached as current installers.

© 2026 Mohamed Yusuf Alsehli — YOEAI

See [NOTICE](NOTICE) and [LICENSE](LICENSE).
