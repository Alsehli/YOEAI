# Tagged-source installer candidates

The manual **Build tagged-source installer candidates** workflow addresses the reproducible source/extraction part of issues #5, #6 and #11. It does not close those issues or replace the current downloadable preview.

## Build and provenance

Both editions use one exact `candidate-*` Git tag and clean commit. Manual builds reject tags outside the reviewed main-branch history. PR validation uses an ephemeral CI tag solely to exercise the builder. Direct and edition build requirements are pinned, and each payload records the actual Python and installed dependency versions.

Each edition produces `Lite-Setup.exe` / `Normal-Setup.exe`, its matching `*-Payload.zip`, a `*-provenance.json` inventory and `SHA256SUMS.txt`. Keep the setup and ZIP together. The expected ZIP hash is compiled into its setup. Transport, archive paths, extraction budget and every file hash are checked before additive installation. CI runs each compiled setup's verification and extraction commands in disposable folders. It also exercises the frozen Lite server/HTML and Normal UI construction without loading models, using separate profiles and ports. Matching application source/build entry points, original project notices and available installed dependency license files are included. The bootstrap changes only the candidate process environment; it does not migrate user profiles.

These are **native-enabled source candidates**, not complete offline model/creative distributions. CI explicitly provisions the version-paired llama.cpp b11784/CUDA 13.4 DLLs from fixed upstream archives whose sizes and SHA-256 digests are committed in the provisioner. Only an allowlist of core DLLs and notices is extracted; server executables and RPC backends are excluded. Microsoft CRT files come from the pinned PySide6 6.12.0 build input, with individual hashes and carrier version recorded. No model weights or optional voice/media runtimes are silently fetched or inherited from a developer PC. See [runtime provenance and probe scope](NATIVE-RUNTIME-INPUTS.md).

Each compiled native worker runs a library/device-enumeration probe. GPU-less CI may use the explicit `--probe-cpu-ok` switch; its result retains `cuda: false` and `modelLoaded: false`. The existing default probe still requires CUDA. This verifies native DLL/ABI loading, not model inference or physical GPU compatibility. A local builder can also accept an existing verified `--native-runtime PATH` without downloading it.

For a configured Windows build environment:

```text
python -m pip install -r requirements-build.txt -r editions/lite/source/build-requirements.txt
python tools/provision_native_runtime.py --output artifacts/native-runtime --cache artifacts/native-input-cache
python tools/build_installer_candidates.py --tag candidate-YOUR_VERSION --output artifacts/installer-candidates --native-runtime artifacts/native-runtime
```

Output must be new. Installer destinations must also be new. No existing app, profile, model or shortcut is replaced, no post-install program runs, and no production endpoint is enabled. The application environment is isolated under `YOEAI-SourceCandidateData/<edition>/<tag>`; files install under `YOEAI-SourceCandidates/<edition>/<tag>` by default.

## Signing and publication

The maintainer reports SignPath approval. See [code-signing setup and approval boundaries](../CODE-SIGNING.md). Signing is off by default, requires an explicit manual request plus protected-environment approval, and uses only the artifact ID from the successful build in that same workflow run. Returned installer signatures, expected certificate thumbprint and timestamps must verify before signed artifacts are retained. New hashes describe the signed bytes; old public hashes remain immutable.

No automatic release publication exists. A signed installer is not evidence that models, optional runtimes or clean-PC behavior work.

## Remaining acceptance work

- #5: provision reviewed release runtime inputs, final tagged complete payloads, clean-runner build/extraction evidence and exact-byte target-PC checks.
- #6: configure the approved SignPath organization/project/policy/secret and protected environment, approve a real request, verify the resulting signatures and qualify those exact signed bytes.
- #11: inventory and replace every affected bundled dependency/runtime, including the historical Normal Pillow 11.3.0 payload. A source pin or new source-preview build does not alter old downloads.
- #7: independently qualify optional voice, image, video and other creative workers on a clean supported PC; retain explicit missing-runtime behavior and license notices.
- #8: observe keyboard-only and screen-reader workflows, real 100/125/150% Windows scaling and the claimed GPU/edition matrix.
- #20: retain completed source-remediation evidence; reconcile it with final installer sources and artifacts rather than closing on a source-only CI result.

The workflow's extraction tests are automated fixture/compiled-package checks, not physical hardware or screen-reader certification. No production deployment, signing token, new public download or completed hardware matrix is claimed by these files.
