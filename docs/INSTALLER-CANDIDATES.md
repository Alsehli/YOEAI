# Tagged-source installer candidates

The manual **Build tagged-source installer candidates** workflow addresses the reproducible source/extraction part of issues #5, #6 and #11. It does not close those issues or replace the current downloadable preview.

## Build and provenance

The single current YOEAI product uses one exact `candidate-*` Git tag and clean commit. Manual builds require reviewed main-branch history. PR validation uses an ephemeral CI tag. Build inputs are pinned and actual dependency versions are recorded. `editions/lite/source` remains an internal compatibility path; old edition release records are historical.

The build produces `YOEAI-Setup.exe`, `YOEAI-Payload.zip`, `YOEAI-provenance.json` and `SHA256SUMS.txt`. The installed app is `YOEAI.exe`. Setup binds the matching payload hash; archive paths, extraction budgets and every file hash are checked before additive installation. CI verifies/extracts the compiled setup and exercises the frozen server, assistant and document workers without inference. Corresponding source/build entries and dependency notices accompany the payload.

These are **native-enabled source candidates**, not complete offline model/creative distributions. CI explicitly provisions the version-paired llama.cpp b11784/CUDA 13.4 DLLs from fixed upstream archives whose sizes and SHA-256 digests are committed in the provisioner. Only an allowlist of core DLLs and notices is extracted; server executables and RPC backends are excluded. Microsoft CRT files come from the pinned PySide6 6.12.0 build input, with individual hashes and carrier version recorded. No model weights or optional voice/media runtimes are silently fetched or inherited from a developer PC. See [runtime provenance and probe scope](NATIVE-RUNTIME-INPUTS.md).

Each compiled native worker runs a library/device-enumeration probe. GPU-less CI may use the explicit `--probe-cpu-ok` switch; its result retains `cuda: false` and `modelLoaded: false`. The existing default probe still requires CUDA. This verifies native DLL/ABI loading, not model inference or physical GPU compatibility. A local builder can also accept an existing verified `--native-runtime PATH` without downloading it.

The frozen YOEAI check opens its local assistant-state endpoint and runs its private document worker against generated PDF, DOCX, XLSX and RTF fixtures. The document/XML/schema libraries are pinned. These checks use no private documents, model inference or public network requests.

For a configured Windows build environment:

```text
python -m pip install -r requirements-build.txt -r editions/lite/source/build-requirements.txt
python tools/provision_native_runtime.py --output artifacts/native-runtime --cache artifacts/native-input-cache
python tools/build_installer_candidates.py --tag candidate-YOUR_VERSION --output artifacts/installer-candidates --native-runtime artifacts/native-runtime
```

Output and installation destinations must be new. Existing apps, profiles, models and shortcuts are preserved. Candidate files use `YOEAI-SourceCandidates/YOEAI/<tag>` and profiles use `YOEAI-SourceCandidateData/YOEAI/<tag>`. The internal `YOEAILite` profile subdirectory is retained for compatibility; no profile migration is performed.

Extraction uses Windows extended-length filesystem paths for its new destination/staging directory. This supports long Qt asset names even when the parent folder is deeply nested, without modifying the Windows long-path policy. Archive traversal, reserved-name, alias, duplicate and hash checks remain enforced. Failed extractions remove only their newly created staging directory.

## Signing and publication

The maintainer reports SignPath approval. See [code-signing setup and approval boundaries](../CODE-SIGNING.md). Signing is off by default, requires an explicit manual request plus protected-environment approval, and uses only the artifact ID from the successful build in that same workflow run. Returned installer signatures, expected certificate thumbprint and timestamps must verify before signed artifacts are retained. New hashes describe the signed bytes; old public hashes remain immutable.

The [14 November test-signing record](TEST-SIGNING-20261114.md) documents a completed manual request for the reviewed PR #32 setup, with exact input/output hashes and an untrusted self-signed certificate. It does not cover later fixes or establish production signing.

No automatic release publication exists. A signed installer is not evidence that models, optional runtimes or clean-PC behavior work.

## Remaining acceptance work

- #5: provision reviewed release runtime inputs, final tagged complete payloads, clean-runner build/extraction evidence and exact-byte target-PC checks.
- #6: configure the approved SignPath organization/project/policy/secret and protected environment, approve a real request, verify the resulting signatures and qualify those exact signed bytes.
- #11: inventory and replace every affected bundled dependency/runtime, including the historical Normal Pillow 11.3.0 payload. A source pin or new source-preview build does not alter old downloads.
- #7: independently qualify optional voice, image, video and other creative workers on a clean supported PC; retain explicit missing-runtime behavior and license notices.
- #8: observe keyboard-only and screen-reader workflows, real 100/125/150% Windows scaling and the claimed GPU/edition matrix.
- #20: retain completed source-remediation evidence; reconcile it with final installer sources and artifacts rather than closing on a source-only CI result.

The workflow's extraction tests are automated fixture/compiled-package checks, not physical hardware or screen-reader certification. No production deployment, signing token, new public download or completed hardware matrix is claimed by these files.
