# Release readiness

## Prepared
- Current YOEAI source and original assets; historical edition trees preserve provenance and compatibility.
- Current features, non-profit project description, build instructions and optional-runtime limits.
- Pinned direct build dependencies and source build entry point.
- Source inventory, source/privacy checks and portable regression runner.
- Scoped historical QA reports and current per-commit test/build evidence; old qualification does not certify a new package.
- CI validation/build workflow; publication is manual, not automatic.

## Windows preview completed — 28 October 2026
- Current tested installers: Lite 2.0.2 and Normal 2.0.20261027.1; exact hashes match the D: test kit.
- Matching application source archives and Normal outer-installer source are attached separately from the older developer Git snapshot.
- Maintainer-reported qualification accepted: Lite other-PC install/online/offline; Normal current-PC install/chat/restart/offline.
- Unsigned status is explicit. Available bundled notices, checksums and optional-component requirements accompany the downloads.
- Model weights are separate; optional engines are not represented as turnkey-installed.

## Before a full stable release
- Qualify the current YOEAI installer on supported clean PCs, including update/uninstall/recovery scenarios.
- Qualify portable setup for each optional runtime, or continue to mark it optional/unavailable.
- Maintain exact binary/source/dependency provenance and notices for each rebuilt artifact.
- Obtain trusted signing and verify timestamps/hashes of the exact signed YOEAI bytes; historical unsigned builds remain unsigned.
- Keep future release notes and hashes tied to the exact tested assets. Source-only CI does not certify all inference/media engines.
