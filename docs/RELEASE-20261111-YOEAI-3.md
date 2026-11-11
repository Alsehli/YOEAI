# YOEAI 3.0 development source — 11 November 2026

This updates the existing Lite codebase under `editions/lite/source`. It is source preparation and maintenance, not a published YOEAI 3.0 download. Earlier 2.0 preview releases remain historical artifacts.

## Changes

- Automatic research through ordinary chat, lazy bundled SearXNG integration, HTTPS retrieval, verified-source citation filtering and source links that leave the app open.
- Automatic bundled matching vision routing for images while the selected local language model handles text. Separate normal-image, 2D and TripoSR 3D object views; prepared additional image/video integrations.
- Persistent linked GGUF folder discovery, explicit model selection, shared native-worker reuse and stat-keyed metadata caching.
- Quick (16K) and Long (up to 196K) context presets capped at declared model limits; users apply changes explicitly. Engine, weight/memory transfer and context stages display elapsed time.
- Blank message composer across chat/image/2D/3D/video; accessibility label and editing retained.
- Strict chat payload validation before model activation, bounded worker cleanup, atomic context settings, UTF-8/BOM profiles, frame protection and citation checks in visual/PDF exports.
- Configurable signed-manifest installer preparation, interrupted-download recovery and SHA-256 checks. Production downloads remain disabled until metadata and payloads are published and verified.

## Evidence and limits

Maintainer-local audit recorded 395 functional checks (including 150 scripted research scenarios and 14 installed HTTP/settings checks), plus 240 syntax/asset checks at that checkpoint. Later changes passed five preset/stage regressions, three loading/recovery regressions, 31 audit regressions and 242 syntax/asset checks. These overlapping suites must not be added together as unique tests. Installed browser checks confirmed seven blank-composer transitions and working preset selections.

On one RTX 3090 development machine, moving a 27B Q4 model from USB storage to NVMe reduced the observed load from about 173 seconds to 12.5 seconds with the same 196K context. Cache and free-VRAM conditions were not controlled; this is not a general speed guarantee. Later observed loads were approximately 6–12 seconds.

The 150 scenarios use model/network fixtures, not 150 live answers. No new vision/media-generation, long GPU soak, clean-PC installer or public download qualification is claimed here. GGUF discovery does not establish model compatibility. Arabic/non-Latin PDF layout remains an existing limitation. Raw local profiles, private documents, browser data and machine logs are not included.

## Publication checks

The staged public source passed 58 repository portable tests, 43 Lite Python tests (presets, model loading/recovery and folder discovery), 12 citation cases, eight link cases and six keyboard-control cases. Source credential/payload and documentation checks passed. The existing portable chat test now resolves Node from PATH instead of a fixed Windows installation path. Windows CI includes these focused Lite contracts; hosted results are separate from the maintainer-local checks.

## Distribution status

The planned production endpoint is `https://downloads.yoeai.online/3.0/stable/manifest.json`; it is not live/verified. No model weights, application binaries or new release assets are uploaded by this source update. External bundled services and runtimes still require explicit package staging and license review.

## Security review follow-up

Hosted CodeQL review prompted a packaged-file asset index with fixed MIME values, a TLS 1.2 minimum in local installer fixtures, and canonical hex-only generated job IDs. Local model-folder selection deliberately accepts the user's absolute local folder through same-origin settings; that single intentional path is documented inline rather than disabling the security query. The legacy scan uses the same local-folder validation. All 31 request/shutdown audit regressions and 35 folder regressions passed after these changes.

## Interactive graphs and tables

The current Lite source now includes versioned, shared data views, normal-chat Qwen integration, transactional follow-ups, deterministic calculations and sourced exports. It retains the bundled ECharts 6.1.0 and bounded/virtualized table engine. [Detailed implementation and local evidence](../editions/lite/source/docs/YOEAI_GRAPHS_TABLES_REPORT.md) records 223 graph/table scenarios and 250 syntax/asset checks, with live-model checks distinguished from research fixtures. No application or installer binary is released by this source publication.
