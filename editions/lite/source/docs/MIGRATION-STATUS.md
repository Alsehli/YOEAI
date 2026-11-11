# YOEAI 3.0 development status — 10 November 2026

This is an initial implementation checkpoint, not a completed YOEAI 3.0 release.
The active Lite source remains the foundation. Its source directory was not
moved, the Full project was not merged, and existing user profiles were not
migrated or deleted. No production download is available or claimed.

## Protected foundation

Workspace: `C:\Users\developer\Documents\Codex\2026-11-09\do\work\intelligent-upgrade`.
Active source: `Lite/Source`. The initial recoverable Git commit is
`16b807506fb50744f40b71872fd00192c31c190c` in that source repository.
The workspace previously had no Git repository. The checkpoint covers source,
assets and dated installer source snapshots; model/runtime binaries outside
Source are not part of that Git checkpoint.

The existing native private-worker inference backend, document extraction,
SQLite/FTS/vector retrieval, consented memory, Windows permission policy and
AppContainer qualification mechanism remain the foundation. Shared code,
packaging scripts and runtime assets also exist outside Source. They must be
accounted for before final consolidation or removal of Lite/Full directories.

## Implemented changes

- Ordinary chat recognizes explicit video requests and animation requests,
  routes them to the existing local video job path, and avoids intercepting
  explanations or requests for pictures containing video-related objects.
- Explicit local dictation uses upstream whisper.cpp Windows CPU build b5454
  and the pinned multilingual Whisper tiny model. The user starts/stops the
  microphone and reviews the transcript before sending. Audio is limited to
  mono 16 kHz PCM, 0.1–60 seconds. Per-job temporary audio and logs are removed.
- Hardware reporting enumerates NVIDIA devices independently and reports CPU,
  RAM and free storage. Existing primary-GPU offload behavior is preserved;
  VRAM is not combined and new tensor-splitting support is not claimed.
- Main UI and development metadata identify YOEAI 3.0 development. A misleading
  unconditional image-model readiness message was removed. Complete branding
  and build metadata consolidation remain unfinished.
- Missing-model context changes now produce a clear 400 response. A stale
  offline-installer test fixture was updated to include two required folders.
- A read-only offline payload audit distinguishes asset presence from actual
  functional/release qualification. It reports the existing RC3 payload as
  not ready for a complete 3.0 offline release.

## Installer preparation requested in the follow-up

`installer/` is a separate preparation module within the same source tree.
The original Lite installer is retained. Its production manifest URL is
configurable and defaults to
`https://downloads.yoeai.online/3.0/stable/manifest.json`.

Production downloads are disabled, and no production public key is configured.
No request to the production endpoint was required for the fixture tests.
The bootstrap supports pinned versions for application and model components,
Ed25519 signed metadata, validity dates, SHA-256 and size checks, HTTPS-only
requests and redirects, interrupted-download recovery, component progress,
cancellation and installation into a new version directory. Existing versions
are never deleted or overwritten on download failure. Archive extraction is
bounded and rejects unsafe Windows paths, traversal and symlinks.

A 15,501,089-byte unsigned Windows preview was built with downloads disabled.
It is a preparation artifact, not the complete application installer. The
packaged disabled CLI exits with status 1 and leaves requested install/cache
directories absent. See `installer/README.md` for the manifest schema and exact
trust/signing contract. No production private signing key was generated.

## Verification performed

- 17 installer tests passed using temporary Ed25519 keys, dummy packages and a
  local HTTPS server with certificate verification enabled. They cover disabled
  networking, missing/untrusted keys, signature tampering, expiry, HTTPS-only
  redirects, SHA-256 failure, resumed/interrupted downloads, invalid ranges,
  servers ignoring Range, cancellation, traversal, Windows paths, required
  unified capabilities, old release rejection and preservation of old installs.
- 32 selected application tests passed: dictation input validation, offline
  readiness, resource inventory, native migration, first-launch behavior,
  existing installer/profile preservation and relevant HTTP security checks.
- 14 media intent cases passed in Node. Real browser send-button checks routed
  ordinary-chat requests to image/video endpoints with no JavaScript errors.
  These routing checks mocked generation responses and did not regenerate media.
- Real HTTP dictation transcribed the upstream JFK sample correctly, rejected
  foreign-origin requests and removed its assistant-owned temporary files.
  The browser controls were checked. Live microphone capture and Arabic speech
  accuracy were not certified by these checks.
- Existing core and format regression scripts passed: English/Arabic retrieval,
  memory/document deletion, managed backup behavior, ten extraction formats and
  malicious-input guards. The native-model orchestration script passed with the
  existing Lite text model and document search. Prior image/video reports were
  inspected; their old results are not new 3.0 end-to-end certification.
- 94 Python files parsed and 53 HTML asset references resolved. Diff whitespace
  checks passed. This is not a claim that every legacy test suite was run.

## Controlled deletion

50 checkpointed files were removed: 17 unreferenced duplicate source/config
files in `Installer-20261107` and `Installer-Image-20261108`, plus 33 tracked
bytecode cache files. Active source had no references to those dated installer
paths; current installer/profile regression tests passed afterward. A Git ignore
file prevents regenerated bytecode from being tracked.

This does not mean the entire dated directories disappeared: untracked caches
may remain. Full source/build trees, old binary installers and outputs were not
deleted. Models, runtimes, license notices, conversations, memories and personal
documents were not deleted. The external deletion report lists every removed
tracked file. Full workspace cleanup still requires dependency migration,
replacement verification and explicit approval for non-version-controlled
destructive changes, as required by the original request.

## Preliminary model evaluation

The selected whisper.cpp Windows runtime was hash-checked against the upstream
release digest. Its model revision, file hashes and MIT notices are recorded in
`speech-input-assets.json`; runtime files are under workspace `SpeechInput`.
[whisper.cpp releases](https://github.com/ggml-org/whisper.cpp/releases/tag/b5454).

MOSS-Image's standalone pipeline code is Apache-2.0 according to its upstream
repository; that does not establish all model-weight redistribution terms or
qualify this application's runtime integration. No MOSS adapter was added.
[MOSS-Image](https://github.com/OpenMOSS/MOSS-Image).

The original Qwen-Image model card identifies Apache-2.0, while Qwen-Image-2.1
has a separate license requiring a commercial license request. A model-family
name is therefore insufficient for redistribution approval. No Qwen-Image
replacement was silently selected. [Qwen-Image](https://huggingface.co/Qwen/Qwen-Image),
[Qwen-Image-2.1 license](https://github.com/QwenLM/Qwen-Image-2.1/blob/main/LICENSE).

LTX's upstream repository lists quantized community runtime paths; these are
evaluation candidates, not verified integrations here. Existing Hunyuan code
was preserved. Bark's upstream describes roughly 12 GB VRAM for its full models
and smaller/offload alternatives. Existing Kokoro read-aloud was preserved
rather than adding another unqualified voice dependency.
[LTX-Video](https://github.com/Lightricks/LTX-Video),
[Bark](https://github.com/suno-ai/bark).

## Work still required

The full original migration remains incomplete. Required work includes a single
consolidated source/build tree; remaining natural-language media/voice/document
workflows; qualified model scheduling and shutdown; final model license and
redistribution review; full data-upgrade tests; real signed release assets;
complete offline packaging; activation/rollback, Windows shortcuts and uninstall
integration; clean-PC installation/uninstallation and offline end-to-end tests;
and final approved legacy cleanup. No signing, publication, activation or
replacement of the user's working installation was performed.
