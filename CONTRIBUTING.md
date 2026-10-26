# Contributing to YOEAI

YOEAI is a personal project. Useful contributions include reproducible bug reports, documentation corrections, accessibility feedback and focused patches.

## Report a problem

Use the bug-report form. Include the edition, build or commit, Windows version, GPU/VRAM, selected model and exact reproduction steps. Describe expected and actual behavior. Remove usernames, local paths, private conversation content, tokens and credentials from logs and screenshots. Never attach model weights or private profiles.

Use a separate issue for each problem. For security vulnerabilities, follow [SECURITY.md](SECURITY.md) rather than posting sensitive details publicly.

## Propose a change

Start from the relevant source branch and keep the change focused. Preserve existing histories, model configurations, permission checks and the fox identity. Do not add model downloads, telemetry, network transmission, new dependencies or automated execution without explaining their purpose and consent behavior.

Run `python tools/check_release.py` and `python tools/test_portable.py` from a configured Windows development environment. Include actual results, untested paths and any optional runtimes needed. For UI changes, include before/after screenshots and verify resizing, keyboard focus and the existing theme. Use a disposable profile rather than production user data.

Pull requests do not authorize deployment. The current source candidate and complete Windows installers have different readiness gates; see [the release checklist](docs/RELEASE-CHECKLIST.md).

## Optional project support

See [the project support page](https://yoeai.online/contribute). Financial support is optional and does not buy software, licensing, features or priority support. YOEAI is not represented as a registered charity, and no tax-deductible receipt is promised. Feedback and code contributions are equally welcome.
