# Release readiness

## Prepared
- Current verified Normal source and original assets; no duplicate model weights.
- Current features, non-profit project description, build instructions and optional-runtime limits.
- Pinned direct build dependencies and source build entry point.
- Source inventory, source/privacy checks and portable regression runner.
- Actual 384-test local QA report; native voice and Fast/Advanced verification.
- CI validation/build workflow; publication is manual, not automatic.

## Windows preview completed — 28 October 2026
- Current tested installers: Lite 2.0.2 and Normal 2.0.20261027.1; exact hashes match the D: test kit.
- Matching application source archives and Normal outer-installer source are attached separately from the older developer Git snapshot.
- Maintainer-reported qualification accepted: Lite other-PC install/online/offline; Normal current-PC install/chat/restart/offline.
- Unsigned status is explicit. Available bundled notices, checksums and optional-component requirements accompany the downloads.
- Model weights are separate; optional engines are not represented as turnkey-installed.

## Before a full stable release
- Extend independent target-PC coverage, including Normal on another PC and complete update/uninstall/recovery scenarios.
- Qualify portable setup for each optional runtime, or continue to mark it optional/unavailable.
- Maintain exact binary/source/dependency provenance and notices for each rebuilt artifact.
- Sign with a verified certificate if desired; never imply existing unsigned builds are signed or certified.
- Keep future release notes and hashes tied to the exact tested assets. Source-only CI does not certify all inference/media engines.
