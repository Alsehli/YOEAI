# YOEAI system audit — 11 November 2026

The audit found and fixed request-validation, native-worker shutdown, citation/export, and configuration issues. The rebuilt application is installed at `E:\YOEAI-Packages\YOEAI-3.0-Local`; existing Desktop shortcuts use that installation. This is bounded regression coverage, not a claim that the whole product is bug-free.

## Fixes

- Reject malformed chat payloads, unsupported attachments, nonfinite numbers and invalid generation settings with HTTP 400 before activating any model. Normalize text-only content arrays for the native text engine and detect incomplete HTTP bodies.
- Bound native-worker shutdown waits when another request holds its lock. Cancellation targets the captured worker rather than a replacement worker. Close owned process resources and remove a duplicate response close.
- Apply the verified-source allowlist to structured visual citations and PDF source footers. Preserve local heading links and open source links outside the app.
- Read UTF-8/BOM profiles correctly, including Arabic paths. Save context changes and rollback atomically. Explicit context reload can restart a manually unloaded model while automatic chat continues respecting manual unload.
- Supply frame protection, content-type protection and explicit JavaScript MIME types. Server handler threads no longer hold shutdown indefinitely.

## Results

| Coverage | Passed |
| --- | ---: |
| Core/profile/security/download/release fixture tests | 59 |
| New audit regressions | 31 |
| Scripted research scenarios | 150 |
| Search regressions | 36 |
| Search speed regressions | 27 |
| Model folder regressions | 35 |
| Citation rendering cases | 12 |
| External-link navigation cases | 8 |
| Chat keyboard/control cases | 6 |
| Media intent routing cases | 14 |
| Structured visual source/PDF policy cases | 3 |
| Installed app HTTP and settings checks | 14 |
| **Functional checks** | **395** |
| Python/JavaScript syntax and asset-reference checks, separately | 240 |

The 150 research scenarios use controlled model/network fixtures. They are not 150 live web answers. Media routing checks do not generate media. PDF policy checks exercise rendering logic with fixtures, not exported-document visual layout.

Baseline reproductions confirmed malformed requests previously reached HTTP 500 (including an empty-message request reaching activation) and shutdown could wait behind a held request lock. See `system-audit/reproductions.json`. Three pre-existing core test assumptions and the chat-control DOM fixture needed updating to match current interfaces; their original safety/control assertions were retained. `core-baseline.json` is an intermediate corrected run, not an untouched failure baseline.

## Installed application

All 14 installed checks passed: security headers, JavaScript MIME, foreign Origin/Host rejection, six invalid request cases, unchanged selected/unloaded model, automatic discovery of three models in `E:\YOEAI-Models`, research registration without startup searching, and unchanged profile/folder configuration hashes.

Installed executable SHA-256 matches the final candidate:
`F863A9FD4D5DEFEE23125C7E2DEA854BA8EE44C6BBC0B35935911BA4D13FBD97`.

Prior executable backup: `E:\YOEAI-Packages\YOEAI-3.0-Local\Before-system-audit-20261111\YOEAILite.exe`. The app was idle and unloaded before restart. Models, conversation history and user settings were preserved. No model inference was run in this audit. Runtime/model junctions still depend on the existing C: candidate store; the E: directory is not a self-contained portable distribution.

## Reproduction

Run from Lite/Source using the workspace Python environment:

```powershell
..\..\.venv\Scripts\python.exe tests_system/core_runner.py
..\..\.venv\Scripts\python.exe tests_system/test_audit.py
..\..\.venv\Scripts\python.exe tests_system/syntax_assets.py
node tests_system/visual_links.cjs
node tests_search/citations.cjs
node tests_search/link_navigation.cjs
node test_chat_controls.cjs ui.html
node test_media_intent.cjs
```

Core installer fixtures require test-only cryptography dependencies under `Lite/System-Audit/Dependencies` (cryptography 50.0.2, cffi 2.1.1, pycparser 3.12). These were isolated from the application's environment. Installer tests use temporary fake payloads and local TLS; no production installer was launched. Source checkpoint before changes: `checkpoint/system-audit-20261111`.

## Remaining verification and limitations

- Actual text inference, vision loading, image/2D/3D/video/voice generation and long GPU/driver/handle soak were not exercised in this round. Synthetic worker-lock tests do not prove every native hang can be recovered.
- GGUF discovery does not prove that each discovered model is compatible or fits available memory.
- No manual browser layout review or PDF layout review was performed this round. Existing Arabic/non-Latin PDF export remains unsupported.
- Production release hosting is not live/verified. Downloads remain disabled until signed metadata and payloads are published and verified; no public download availability is claimed.
- Research registration is confirmed; no fresh live research or full conversational answer was requested by the installed smoke checks. Their status remains separate from fixture regression results.
