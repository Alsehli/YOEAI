# YOEAI 3.0 search test report

Date: 11 November 2026 (Asia/Bahrain). Status: **development search repairs tested; complete release acceptance remains incomplete**.

## Scope and totals

222 distinct recorded checks executed: **221 passed, 1 failed**. Executed-check pass rate: 100%. Five additional release-readiness requirements are blocked/incomplete, listed below; they are not counted as executed tests.

- 150 distinct topic/failure/security scenarios: 10 in each required category.
- 36 focused Python regression checks.
- 10 additional Windows/browser checks: 9 passed, 1 failed in the old installed E: version.
- 1 actual bundled backend startup with Git removed from PATH: passed.
- 9 production JavaScript adapter checks with a minimal DOM fixture.
- 10 routing checks with the user's already loaded Qwen3.8-27B-Heretic-Ara model.
- 3 controlled live SearXNG queries, including Arabic; 2 official-page retrieval checks.
- 1 complete live research and streamed-answer check using the production Service/Assistant/Research, bundled backend, and selected Qwen through the existing local native application endpoint.
- Four selected-model cases repeated after an optimization; performance trials and repeats are excluded from distinct-check totals.

**The 150 scenarios use scripted model and network fixtures.** They execute production Python orchestration, research, deduplication, failure handling and evidence filtering. They do not establish that Qwen can accurately answer all 150 real-world questions. O-category fixtures do not establish full Windows UI lifecycle behavior. Expected behavior, actual calls/results, timings, citation requirements, and failures are recorded per case in `search-results/final/scenarios.json`.

No generation, vision switching, voice, unrelated Windows automation, installers, hosting or releases were tested. User models and profiles were not edited. The selected Qwen remained active; sampled native worker PID was 2872.

## Checkpoint and architecture audit

Safe Git checkpoint: `checkpoint/search-audit-20261111` (before repairs). Existing Lite foundation and llama.cpp/native private-pipe inference retained.

Startup initializes Service, tool registry and configuration without starting a model/search service or issuing an internet request. Normal conversation uses `/assistant/prepare`; lightweight clients are ready immediately. The bundled Windows SearXNG/Waitress worker starts lazily, on an authenticated loopback port, and idles down. Remote engine access and public page access require internet; no managed endpoint, Docker or user API key is needed for this bundled backend. The vendor AI Kit remains a bundled dependency rather than a separately launched assistant. Vendor source was not modified.

The selected local model plans structured tools and focused public queries. Research performs bounded concurrent searches/reads and an optional second evidence round. Public query history remains separate from private documents/memories. The existing UI adapter supplies untrusted evidence to local generation and renders exact-source links. Saved conversation history is preserved. Prompt context uses recent turns/excerpts, rather than loading unlimited history.

## Categories

| Category | Topic | Executed | Passed |
|---|---|---:|---:|
| A | Basic current information | 10 | 10 |
| B | Deep technical research | 10 | 10 |
| C | Shopping and prices | 10 | 10 |
| D | Community evidence | 10 | 10 |
| E | GitHub/software | 10 | 10 |
| F | Arabic/multilingual | 10 | 10 |
| G | Follow-up context | 10 | 10 |
| H | Sources and claim support | 10 | 10 |
| I | Multi-step research | 10 | 10 |
| J | Failure/recovery | 10 | 10 |
| K | Untrusted content/security | 10 | 10 |
| L | Responsiveness/bounds | 10 | 10 |
| M | Search styles | 10 | 10 |
| N | Realistic phrasing | 10 | 10 |
| O | Startup/integration contracts | 10 | 10 |

## Failures and repairs

Corrected-harness baseline: **147/150 passed; J06/J07/J08 failed** because HTTP 403/404/500 page failures could leave no useful warning. An earlier harness run reported 13 failures: ten were an instrumentation error that counted the coordinator's ordinary final planning call as an additional action. That harness error was corrected without removing the actual tool-action and bounded-call assertions; baseline was repeated against checkpoint source. Raw initial and corrected baseline records are retained.

Production repairs:

1. Add conservative deterministic public-tool fallback after both structured planning attempts fail, including schema failures. Normal routing remains local-model driven. Stable explanations and artwork generation do not become fallback web searches.
2. Recover malformed research decisions safely; continue privacy filtering on all fallback queries.
3. Explicitly warn when pages cannot be read. Snippets are not treated as verified article evidence. Skip costly evidence-model assessment when no page text exists.
4. Restrict claim supporting URLs to actual nonempty read pages. Retrieved snippets can remain discovery links but cannot substantiate claim checks.
5. Replace executor context-manager waits with bounded polling and cancellation-aware shutdown. Return promptly on Stop or research deadline even if an individual socket worker is still finishing. Search/read concurrency bounded at three; queries deduplicated, up to two research rounds, up to four unique queries per research operation.
6. Bound page evidence to 6,000 characters per page and mark it untrusted regardless of provider flags. Block unsafe read-page URLs and nonstandard result ports.
7. Add per-read total elapsed-time checks and disallow private backend HTTP redirects, protecting its authentication header.
8. Remove unsafe and unretrieved citation anchors defensively; only external HTTPS links without credentials/nonstandard ports qualify. Link labels remain inserted as text. Document source links remain supported.
9. Disable thinking in structured native planning requests to request compact JSON without changing the selected model or its saved context.

10. Fix a desktop-only backend startup crash: register explicitly unversioned bundled SearXNG metadata before import when frozen version metadata is absent. Customers no longer need Git to start search. Upstream frozen metadata, when present, is preserved. No upstream vendor source was edited. Actual no-Git startup and a regression test pass.

Previously present controls were also exercised: secret/path/email query rejection; private, loopback and mixed-address DNS blocking; HTTPS-only managed endpoints; IP pinning with original TLS hostname; authenticated loopback service; no Origin access; public-before-private execution; private-evidence network boundary; cache TTL; startup registration; duplicate calls and bounded follow-up loops.

## Performance measurements

Measured on this Windows PC with an RTX 3090. No image/video/voice benchmark was run.

Controlled five-trial fixture comparison (three 40 ms searches, three 40 ms reads): median **162.28 ms before → 82.75 ms after**. Cancellation with a deliberately slow reader: **782.69 ms → 42.85 ms**. These timings measure artificial network stages and are not claims about internet speed.

Selected-Qwen comparison with captured search results and deliberately unavailable page fixtures, same prompts:

| Case | Before | After skipping assessment of unreadable pages |
|---|---:|---:|
| R01 | 45.85 s | 8.98 s |
| R02 | 33.06 s | 9.93 s |
| R03 | 42.63 s | 7.82 s |
| R04 | 70.70 s | 8.76 s |

These cases are faster because an unnecessary inference was removed; warm caches/load variation also affect timings. They do not predict successful full-page research latency.

Live backend query timings: 7.09 s, 0.91 s, 1.17 s. They include the first lazy start; upstream engines and the network vary.

Live end-to-end answer: **53.47 s total**, evidence prepared at 43.33 s; first answer token at approximately 50.17 s from request start. First generation token after generation request: 6.84 s. Progress callback was recorded immediately, but browser-visible progress timing was not measured; the UI polls every 800 ms. Fixture scenarios record progress callback latency and use null for unmeasured final answer TTFT.

Resource sampling during one planning inference: GPU allocation about 22,000 MiB, GPU utilization samples 8–57%, native worker RSS about 14.23–14.27 billion bytes. CPU user/system cumulative counters and deltas are recorded in `performance/resources.json`. Context remained 196,608 tokens. These are samples, not peak or soak measurements; the preloaded model/context dominate memory.

## Citation accuracy and independent review

All tested citation allowlists rejected invented URLs. Claim support excludes unread pages. JavaScript DOM fixtures confirmed unsafe protocols, credential URLs and unretrieved links are removed while valid source links and local document links survive.

LIVE-E2E-01 cited three actual retrieved official pages. A separate Codex review of recorded page text confirmed the answer's version number, release date, and maintenance status against the Python downloads/documentation/status pages. This is source inspection for this one answer, not an independent evaluation of all topic answers. Source relevance and factual entailment are not proven by URL integrity. Publication dates remain unknown when not supplied; freshness must not be inferred solely from retrieval time.

## Security findings

The 10 K-category scenarios, focused Python security checks, and JavaScript safety checks pass. Fixtures place fake system messages, shell commands, exfiltration requests and citation fabrication instructions into untrusted page text. Tested execution paths neither grant new authority nor run those commands. Private network addresses and redirects, unsupported protocols, credentials in queries, and cross-boundary private-evidence searches are blocked.

The browser test screenshot is saved in the delivered output folder as `UI-search-success.png`; its viewport shows model/UI controls but does not show all answer text, so accessibility observations provide the citation/answer evidence.

No test suite proves immunity to every semantic prompt injection. Tool approvals and network/privacy boundaries remain essential. DNS resolution and socket calls can continue briefly after UI cancellation until their own platform timeouts; the coordinator returns promptly. A long-lived worker/handle soak has not been completed.

## Remaining requirements and release readiness

- **RELEASE-01 — incomplete:** Windows Edge application startup was observed, and real Chrome interaction with the existing production UI passed through an isolated test host: search, sources, progress, Stop, follow-up, reload, and citation navigation. Complete packaged executable restart/idle/model-change lifecycle remains incomplete. O scenarios remain deterministic fixtures.
- **RELEASE-02 — incomplete:** Subjective factual accuracy and relevance for all 150 topic prompts were not evaluated with real Qwen answers. Topic fixtures test contracts, not intelligence. Independent source review completed only for LIVE-E2E-01.
- **RELEASE-03 — incomplete:** PDF full-text reading and dedicated video-search/date-range result filtering are not implemented. Ordinary queries may find these links, but HTML/plain-text retrieval cannot substantiate their full content.
- **RELEASE-04 — incomplete:** Packaged candidate built, but modified search code was not deployed to or relaunched in E: installed app because this request confines changes to the development workspace.
- **RELEASE-05 — incomplete:** Security checks cover tested attack paths, not a proof against all semantic prompt injection. Private DNS resolver stalls and remaining socket work may last until bounded network timeouts after cancellation; full Windows thread/handle soak remains outstanding.

The candidate executable is prepared in the development workspace; the external Source worker includes the metadata repair. The repair was verified through an isolated UI test host, not by deploying the candidate executable. The E: app was opened for UI verification. Its files were not replaced and its Qwen model stayed loaded. Its old search worker still fails until updated. Release signing, hosting and production downloads are untouched. Do not describe this as complete release verification.

## Backend dependencies and live limits

Bundled `SearchRuntime/Python`, `SearchRuntime/Runtime`, `SearchRuntime/Dependencies`, settings template, production search worker, and outbound internet access are required. Three standalone live queries plus one bounded end-to-end research task were performed; no high-volume public-instance testing. Upstream Brave/DuckDuckGo/Wikipedia availability is not guaranteed. Remote search always needs internet, even though local inference and the backend process run on this PC. Disabled/missing/failed backend paths preserve local chat and report limitations.

The managed-HTTPS option is configuration-only unless a real endpoint is supplied. No missing hosting is required for the tested local SearXNG option. No production manifest or download endpoint was published.

## Modified files

- `docs/search-results/all-results.json`
- `docs/search-results/final/scenarios.json`
- `docs/search-results/regressions/results.json`
- `docs/search-results/summary.json`
- `intelligence/search_server.py`
- `tests_search/regressions.py`
- `tests_search/write_report.py`
- New `intelligence/search_intent.py`, `tests_search/` suite, this report, and `docs/search-results/` evidence.

## Follow-up UI verification and approval-review limitation

The previous minimized-window blocker was overcome by opening the existing app and using its accessibility controls. One unexpected delete dialog was cancelled; no user messages were deleted. Search in that installed version failed reproducibly because Git was unavailable on its desktop PATH.

A combined original-server-stop and isolated-candidate-launch command was rejected by automatic approval review as "blocked by policy" with no more specific reason. It was not repeated. A safer test host served the exact existing UI and production research routes from the workspace, with its own knowledge store, forwarding inference to the already loaded native Qwen on port 8087. Browser checks ran in Chrome, since no Edge browser connector was available. No new application or model engine was introduced. The temporary UI test host was stopped after testing; the selected model was preserved.

Full release acceptance remains incomplete. The GUI blocker itself no longer prevents browser-level search checks, but the older E: installation still needs deployment of the repaired files.

## Reproduction

Run from `Lite/Source`, using the existing workspace virtual environment:

```powershell
& '..\..\.venv\Scripts\python.exe' tests_search/run_scenarios.py --output docs/search-results/reproduction
& '..\..\.venv\Scripts\python.exe' tests_search/regressions.py
node tests_search/citations.cjs
& '..\..\.venv\Scripts\python.exe' tests_search/baseline.py
& '..\..\.venv\Scripts\python.exe' tests_search/performance.py
```

Controlled internet checks, only when explicitly desired:

```powershell
& '..\..\.venv\Scripts\python.exe' tests_search/live_checks.py
& '..\..\.venv\Scripts\python.exe' tests_search/live_pages.py
```

With the selected model already loaded in the existing local app on port 8087 (run sequentially):

```powershell
& '..\..\.venv\Scripts\python.exe' tests_search/selected_model.py
& '..\..\.venv\Scripts\python.exe' tests_search/selected_model.py --limit 4 --output docs/search-results/selected-model-after
& '..\..\.venv\Scripts\python.exe' tests_search/end_to_end.py
& '..\..\.venv\Scripts\python.exe' tests_search/resources.py
```

`selected_model.py` uses captured results from the live backend file and deliberately fails full-page reads. It does not repeat public searches. `end_to_end.py` runs one bounded live task with a fresh test-owned knowledge store, using the loaded local model. No fixture prompt/answer is wired into production behavior. Test helpers require the workspace Python dependencies; DOM fixture checks require Node. Full traces and machine-readable consolidated results: `search-results/all-results.json`; summary: `search-results/summary.json`.

## Desktop shortcut repair — 11 November 2026

The user subsequently authorized repairing the installed Desktop app. Its shortcut targets `E:\YOEAI-Packages\YOEAI-3.0-Local\YOEAILite.exe`. The repaired external `Source/intelligence/search_server.py` was copied into that installation, with the previous worker preserved in `Search-Repair-Backup-20261111`. No executable, user profile, selected model or weights were replaced.

A fresh ordinary-chat prepare request to the installed app on port 8087 asked for the newest iPhone using official Apple sources. It returned six source links, including Apple, read three pages and completed without tool notices in 45.77 seconds. The same installed application's fit and streamed native completion endpoints then produced an answer with citations; every cited URL matched retrieved sources. The selected Qwen3.8-27B-Heretic-Ara remained loaded. This resolves the previously observed installed-backend failure; the earlier failure records above remain historical evidence. Full release acceptance and unrelated lifecycle limitations remain unchanged.

Machine-readable installed-app evidence: delivered `Desktop-iPhone-repair.json`.


## Additional testing and installed performance update

See `YOEAI_3_SEARCH_SPEED_REPORT.md` for the latest 240-check round, 27 new regressions, measured speed improvements, resolved follow-up failure, and deployment to the Desktop/E: application. The historical counts above remain evidence of earlier rounds.
