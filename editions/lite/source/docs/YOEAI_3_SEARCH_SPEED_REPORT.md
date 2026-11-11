# Desktop search speed and additional testing

11 November 2026. Optimized executable and matching runtime/source files are installed in `E:\YOEAI-Packages\YOEAI-3.0-Local`, which the Desktop, Start menu and E: shortcuts target. A previous executable is preserved in `Before-search-speed-20261111`. Model weights and history were not replaced. The selected Qwen model and profile hash are unchanged.

## Results

**240/240 checks pass in this round**, including reruns: 150 topic scenarios, 36 existing regressions, 27 new regressions, 9 DOM adapter checks, 10 real-Qwen routing checks and 8 installed-app checks. Before/after timing trials are recorded separately and excluded from these totals. Deterministic fixtures are not claims of real-world answer accuracy across all topics. The installed follow-up initially failed, was repaired and retested; original failure evidence remains in `desktop-initial.json` and each replaced case's `previousAttempt`.

## Changes

- The coordinator now sees a compact public research status/claim/source summary instead of receiving duplicate full webpage text. Original retrieved text remains available to final answer generation. Private/document tool evidence remains unchanged.
- The intermediate evidence model returns compact JSON with at most two short claims and short read-page IDs, within 240 tokens. IDs are mapped back to actual opened URLs; invented IDs are discarded. Important missing facts can still trigger the bounded second research round.
- Repeated exact questions reuse usable public research for up to 90 seconds, including after the research updates public session context. Retrieval timestamp and cache age remain available. Failed/empty research is not cached, enabling recovery after connectivity returns.
- A live follow-up revealed a valid-but-empty model tool plan for an explicit official-source request. Both routing stages now honor that explicit evidence request. The primary model still plans ordinary requests; stable explanations and provided-source summaries keep their direct path.
- When a thin client omits history, the coordinator receives the saved public query/source-title context. Supplied conversation history and selected-document context are preserved. Private memories/documents do not enter public query history.

## Controlled speed comparison

Same loaded Qwen and captured evidence, before/after production Service/Assistant/Research. No public searches were repeated for these comparisons. These measure research preparation, excluding final answer generation and model load. Warm caches and scheduling can influence results; this is a two-question comparison, not a universal speed guarantee.

| Question | Before | After | Reduction |
|---|---:|---:|---:|
| What is the latest stable Python version? Use official sources. | 38.31 s | 23.81 s | 37.9% |
| What is the newest iPhone model? Use official Apple sources. | 42.08 s | 23.48 s | 44.2% |

## Actual installed-app checks

| Check | Time | Result |
|---|---:|---|
| DESK01 | 22.58 s | passed |
| DESK02 | 7.06 s | passed |
| DESK03 | 2.56 s | passed |
| DESK04 | 20.32 s | passed |
| DESK05 | 20.67 s | passed |
| DESK06 | 36.15 s | passed |
| DESK07 | 7.02 s | passed |
| DESK08 | 9.91 s | passed |

DESK01: iPhone research; DESK02: identical immediate repeat; DESK03: direct local calculation routing; DESK04: Python research; DESK05: Arabic research; DESK06: context-dependent official-source follow-up after repair; DESK07: repeated follow-up; DESK08: final iPhone answer generation and citation integrity. All research checks required real sources and nonempty read pages. Claim supporting URLs were checked against read pages. DESK08's final cited URLs matched its supplied retrieved source list.

Simple live research preparation measured 20–23 seconds; the repaired follow-up took 36.15 seconds. Repeated questions took approximately 7 seconds. Final answer generation adds time; the tested iPhone final answer added 9.91 seconds. Initial model warmup took 7.95 seconds and was excluded from research timings. A second warmup after the follow-up repair is recorded separately.

## Deployment and remaining limits

The app was restarted to replace its frozen Python executable. One shutdown left background executable processes holding the file lock; after the server stopped, only the verified application processes were terminated to finish the update. No user files or models were deleted. Final checks ran against port 8087 in the actual installed app, not a test UI host.

The previous build-directory cleanup command was rejected by automatic approval review. Building in a fresh workspace directory safely avoided removing shared runtime junctions.

Only search was exercised; no image/video/voice/vision benchmarks, installer validation or production publishing. Broader release-readiness limitations from the main report remain; these results do not mark the entire product verified. Semantic claim truth across all topics still requires broader independent evaluation. The caching window means a repeat can use evidence retrieved up to 90 seconds earlier.

## Reproduce

From `Lite/Source`:

```powershell
& '..\..\.venv\Scripts\python.exe' tests_search/run_scenarios.py --output docs/search-results/speed/scenarios
& '..\..\.venv\Scripts\python.exe' tests_search/regressions.py
& '..\..\.venv\Scripts\python.exe' tests_search/speed_regressions.py
node tests_search/citations.cjs
& '..\..\.venv\Scripts\python.exe' tests_search/selected_model.py --output docs/search-results/speed/routing
& '..\..\.venv\Scripts\python.exe' tests_search/speed_comparison.py reproduction
```

The final two commands require the selected local model on port 8087 and captured public evidence. Run inference tests sequentially. Full machine-readable evidence is in `docs/search-results/speed/` and delivered `Desktop-speed-tests.json` / `Speed-summary.json`.
