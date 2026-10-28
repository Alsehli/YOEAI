<p align="center"><img src="docs/images/social-preview.png" alt="YOEAI 2.0 — Your AI. Your PC. Your Rules." width="100%"></p>

# YOEAI 2.0

**Your AI. Your PC. Your Rules.** A local-first AI assistant for Windows.

[![Windows](https://img.shields.io/badge/Windows-x64-2465ed)](docs/SETUP.md) [![Python](https://img.shields.io/badge/Python-3.13-2465ed)](requirements-build.txt) [![GPL](https://img.shields.io/badge/License-GPL--3.0--only-2465ed)](LICENSE) [![Windows checks](https://github.com/Alsehli/YOEAI/actions/workflows/windows-preview.yml/badge.svg?branch=main)](https://github.com/Alsehli/YOEAI/actions/workflows/windows-preview.yml) [![Status](https://img.shields.io/badge/Release-Windows_preview-blue)](docs/RELEASE-CHECKLIST.md)

[Website](https://yoeai.online) · [Setup](docs/SETUP.md) · [Release readiness](docs/RELEASE-CHECKLIST.md) · [Report a bug](https://github.com/Alsehli/YOEAI/issues/new/choose) · [Contribute](CONTRIBUTING.md)

YOEAI combines local language models, practical Windows tools and specialized Mini YOE agents in one desktop workspace. It is a personal, non-profit project created and maintained by **[Mohamed Yusuf Alsehli](https://github.com/Alsehli)**. The cream-white YOE fox is its own visual identity.

## Download for Windows

| Edition | Installer | Size |
|---|---|---|
| **Lite · 8GB GPU** | [Download Lite setup](https://github.com/Alsehli/YOEAI/releases/download/v2.0.20261028-windows-preview/YOEAI-Lite-Setup-2.0.2.exe) | 1.27 GB |
| **Normal · 16GB GPU** | [Download Normal setup](https://github.com/Alsehli/YOEAI/releases/download/v2.0.20261028-windows-preview/YOEAI-Normal-Setup-2.0.20261027.1.exe) | 1.54 GB |

[Windows release, matching source and checksums](https://github.com/Alsehli/YOEAI/releases/tag/v2.0.20261028-windows-preview) · [Installation guide](docs/WINDOWS-DOWNLOADS.md) · [Developer source prerelease](https://github.com/Alsehli/YOEAI/releases/tag/v2.0.20261028-rc.1)

> **Unsigned Windows preview.** Choose the edition for your hardware and read the release notes. Chat/image/video weights are not bundled; initial setup needs matching offline files or internet access for setup downloads. Optional voice/creative/application engines require separate configuration. The maintainer reports Lite other-PC installation and online/offline chat passed, and Normal installation/chat/restart/offline checks passed on the current PC. These are user-reported results, not certification of every feature or device.

The Git source tree below is the verified Normal developer snapshot based on build 2.0.20261025.4. The Windows installers are newer: **use their attached matching source archives**, not this older snapshot, for binary correspondence. See [publication record](docs/RELEASE-PUBLICATION-20261028.md). Models and private profiles remain excluded from source publication.

## What is included?

| Workspace | Implemented capability | Requirements and limits |
|---|---|---|
| Conversation | Shared Fast Qwen3.5 9B / Advanced Qwen3.8 27B selection, history, local memory, Markdown, document/image interactions | Compatible local llama.cpp backend, model and configuration; vision needs a compatible projector |
| Interactive Voice | Local speech recognition and responses, interruption, microphone/speaker controls, transcript | External Python 3.11 Bark Pro and Kokoro/eSpeak runtime; developer paths are not portable setup; Arabic ASR is unavailable in this candidate |
| Windows YOE | File browsing/storage analysis, diagnostics, supported desktop automation | Windows tool adapters, authorized locations and approval for sensitive actions; application-specific support varies |
| Code YOE | Code explanation, debugging, patch proposals and live previews | Uses the selected shared model; running code or applying changes follows tool approvals |
| Research YOE | Local-document analysis, source-linked web research, reports and PDF preparation | Offline analysis uses provided evidence; online search sends queries to the configured provider and needs network access |
| Reverse YOE | Authorized static binary/JavaScript inspection and decompiled-code explanations | Ghidra/JDK and configured adapters for native analysis. The newer LLM4Decompile work is **not included in this candidate** |
| Update YOE | Maintenance proposals, evidence review, staged changes, approval and rollback infrastructure | Execution depends on available isolation; source inspection and tests do not grant permission to deploy changes |
| Game Studio | Conversation-led Unity 2D project workflows and existing project tools | Separately installed/configured Unity; template/contract tests do not certify arbitrary generated games |
| Creative tools | Image Turbo/Design adapters, editable precision typography, video adapter, image-to-PDF and report tools | Image/video workers, models and dependencies are separately configured; not installed by the source build |

Tools operate through their existing permission system. Model output is fallible; generated code, research and pseudocode need review. No claim of unattended operation while the PC is off is made.

## Build and run on Windows

The tested shell build uses **Python 3.13 x64**. Speech uses a separate external Python 3.11 environment. Start in a fresh checkout and install the pinned direct build dependencies:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe tools/check_release.py
.\.venv\Scripts\python.exe tools/test_portable.py
.\.venv\Scripts\python.exe tools/check_docs.py
.\.venv\Scripts\python.exe build.py
```

Output: `dist/YOEAI/YOEAI.exe` and supporting files. Keep the directory intact. This builds the shell; it does not provision models, CUDA or optional runtimes. Follow [setup and portability](docs/SETUP.md) to configure your local backend. Test against a disposable profile before using existing history. Do not copy developer process-ownership records or private configuration.

**Hardware:** Windows x64 and a compatible NVIDIA CUDA backend for the documented Normal GPU configuration. Fast and Advanced performance depends on the selected weights, offload/context settings and free VRAM. A 16GB GPU is the development target, not a guarantee that every model and media engine can run together. Lite uses a different framework/package and is not built by this tree.

## Verification, with scope

- Historical qualification: **384 regression tests passed** on 25 October 2026. [Detailed QA](docs/QA-20261025.md) identifies mocks, external-runtime limits and untested scenarios.
- The preserved application source passed GitHub-hosted Windows validation, build and compiled-shell smoke checks: [recorded run](https://github.com/Alsehli/YOEAI/actions/runs/40535799989). The badge above shows the current branch result.
- CI runs a **31-test portable subset** and constructs the compiled UI in a disposable profile without loading models. It does not run a physical microphone or clean-PC installation test.
- [Current release audit](docs/RELEASE-AUDIT-20261027.md) and [validation record](docs/RELEASE-VALIDATION.md) separate new checks from historical evidence.

The Windows preview has separately documented maintainer-reported qualification. Source CI does not qualify every optional runtime or hardware configuration.

## Privacy and security

Local chat uses the configured loopback backend. Web research, external links and optional downloads have network boundaries; local-first does not mean every feature is offline. Microphone use is explicit. Read [Privacy](PRIVACY.md) and [Security](SECURITY.md) before configuring automation or exposing services.

## Contribute and support

Reproducible bugs, documentation fixes, accessibility feedback and focused patches are welcome. See [Contributing](CONTRIBUTING.md), the [conduct policy](CODE_OF_CONDUCT.md) and [issue templates](https://github.com/Alsehli/YOEAI/issues/new/choose).

[Optional project support](https://yoeai.online/contribute) does not buy software, access or priority service. YOEAI is a personal non-profit project, not represented as a registered charity.

## License and credits

Application source: **GPL-3.0-only**, [LICENSE](LICENSE). Preserve [NOTICE](NOTICE) and [third-party notices](THIRD-PARTY.md). Optional models, fonts, runtimes and external applications retain their separate terms; source publication is not a blanket redistribution clearance. Builds are unsigned unless explicitly documented otherwise in [Code signing policy](CODE-SIGNING.md).

© 2026 Mohamed Yusuf Alsehli — YOEAI
