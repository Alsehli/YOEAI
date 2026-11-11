from pathlib import Path
import json,statistics,shutil
root=Path(r'C:\Users\developer\Documents\Codex\2026-11-09\do\work\intelligent-upgrade');src=root/'Lite/Source';results=src/'docs/search-results/speed';out=Path(r'C:\Users\developer\Documents\Codex\2026-11-10\files-pasted-by-the-user-codex\outputs\YOEAI-Search-Testing');live=json.loads((out/'Desktop-speed-tests.json').read_text(encoding='utf8'));before=json.loads((results/'before.json').read_text(encoding='utf8'));after=json.loads((results/'after.json').read_text(encoding='utf8'))
shutil.copy2(out/'Desktop-speed-tests.json',results/'desktop-final.json');shutil.copy2(out/'Desktop-speed-initial.json',results/'desktop-initial.json')
suites={'scenarios':json.loads((results/'scenarios/scenarios.json').read_text(encoding='utf8')),'existingRegressions':json.loads((src/'docs/search-results/regressions/results.json').read_text(encoding='utf8')),'newRegressions':json.loads((results/'regressions.json').read_text(encoding='utf8')),'domChecks':json.loads((src/'docs/search-results/ui/results.json').read_text(encoding='utf8')),'realModelRouting':json.loads((results/'routing/results.json').read_text(encoding='utf8')),'installedApp':live['cases']}
summary={'executedChecksThisRound':sum(len(rows) for rows in suites.values()),'passed':sum(row['status']=='passed' for rows in suites.values() for row in rows),'failed':sum(row['status']=='failed' for rows in suites.values() for row in rows),'newRegressionChecks':27,'profileUnchanged':live['profileUnchanged'],'desktopUpdated':True,'selectedModel':'Qwen3.8-27B-Heretic-Ara-iq4_xs-3.0-mtp','cacheTtlSeconds':90,'fullReleaseVerified':False,'controlledComparison':[]}
for b,a in zip(before,after):summary['controlledComparison'].append({'prompt':a['prompt'],'beforeSeconds':b['seconds'],'afterSeconds':a['seconds'],'reductionPercent':100*(1-a['seconds']/b['seconds'])})
(results/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf8');(out/'Speed-summary.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
rows='\n'.join(f"| {r['id']} | {r['seconds']:.2f} s | {r['status']} |" for r in live['cases'])
comparison='\n'.join(f"| {r['prompt']} | {r['beforeSeconds']:.2f} s | {r['afterSeconds']:.2f} s | {r['reductionPercent']:.1f}% |" for r in summary['controlledComparison'])
report=f'''# Desktop search speed and additional testing

11 November 2026. Optimized executable and matching runtime/source files are installed in `E:\\YOEAI-Packages\\YOEAI-3.0-Local`, which the Desktop, Start menu and E: shortcuts target. A previous executable is preserved in `Before-search-speed-20261111`. Model weights and history were not replaced. The selected Qwen model and profile hash are unchanged.

## Results

**{summary['passed']}/{summary['executedChecksThisRound']} checks pass in this round**, including reruns: 150 topic scenarios, 36 existing regressions, 27 new regressions, 9 DOM adapter checks, 10 real-Qwen routing checks and 8 installed-app checks. Before/after timing trials are recorded separately and excluded from these totals. Deterministic fixtures are not claims of real-world answer accuracy across all topics. The installed follow-up initially failed, was repaired and retested; original failure evidence remains in `desktop-initial.json` and each replaced case's `previousAttempt`.

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
{comparison}

## Actual installed-app checks

| Check | Time | Result |
|---|---:|---|
{rows}

DESK01: iPhone research; DESK02: identical immediate repeat; DESK03: direct local calculation routing; DESK04: Python research; DESK05: Arabic research; DESK06: context-dependent official-source follow-up after repair; DESK07: repeated follow-up; DESK08: final iPhone answer generation and citation integrity. All research checks required real sources and nonempty read pages. Claim supporting URLs were checked against read pages. DESK08's final cited URLs matched its supplied retrieved source list.

Simple live research preparation measured 20–23 seconds; the repaired follow-up took {live['cases'][5]['seconds']:.2f} seconds. Repeated questions took approximately 7 seconds. Final answer generation adds time; the tested iPhone final answer added {live['cases'][-1]['seconds']:.2f} seconds. Initial model warmup took {live['warmupSeconds']:.2f} seconds and was excluded from research timings. A second warmup after the follow-up repair is recorded separately.

## Deployment and remaining limits

The app was restarted to replace its frozen Python executable. One shutdown left background executable processes holding the file lock; after the server stopped, only the verified application processes were terminated to finish the update. No user files or models were deleted. Final checks ran against port 8087 in the actual installed app, not a test UI host.

The previous build-directory cleanup command was rejected by automatic approval review. Building in a fresh workspace directory safely avoided removing shared runtime junctions.

Only search was exercised; no image/video/voice/vision benchmarks, installer validation or production publishing. Broader release-readiness limitations from the main report remain; these results do not mark the entire product verified. Semantic claim truth across all topics still requires broader independent evaluation. The caching window means a repeat can use evidence retrieved up to 90 seconds earlier.

## Reproduce

From `Lite/Source`:

```powershell
& '..\\..\\.venv\\Scripts\\python.exe' tests_search/run_scenarios.py --output docs/search-results/speed/scenarios
& '..\\..\\.venv\\Scripts\\python.exe' tests_search/regressions.py
& '..\\..\\.venv\\Scripts\\python.exe' tests_search/speed_regressions.py
node tests_search/citations.cjs
& '..\\..\\.venv\\Scripts\\python.exe' tests_search/selected_model.py --output docs/search-results/speed/routing
& '..\\..\\.venv\\Scripts\\python.exe' tests_search/speed_comparison.py reproduction
```

The final two commands require the selected local model on port 8087 and captured public evidence. Run inference tests sequentially. Full machine-readable evidence is in `docs/search-results/speed/` and delivered `Desktop-speed-tests.json` / `Speed-summary.json`.
'''
(src/'docs/YOEAI_3_SEARCH_SPEED_REPORT.md').write_text(report,encoding='utf8');(out/'YOEAI_3_SEARCH_SPEED_REPORT.md').write_text(report,encoding='utf8')
with (src/'docs/YOEAI_3_SEARCH_TEST_REPORT.md').open('a',encoding='utf8') as f:f.write('\n\n## Additional testing and installed performance update\n\nSee `YOEAI_3_SEARCH_SPEED_REPORT.md` for the latest 240-check round, 27 new regressions, measured speed improvements, resolved follow-up failure, and deployment to the Desktop/E: application. The historical counts above remain evidence of earlier rounds.\n')
shutil.copy2(src/'docs/YOEAI_3_SEARCH_TEST_REPORT.md',out/'YOEAI_3_SEARCH_TEST_REPORT.md')
Path(r'E:\YOEAI-Packages\YOEAI-3.0-Local\SEARCH-SPEED-STATUS.json').write_text(json.dumps(summary,indent=2),encoding='utf8');print(json.dumps({k:v for k,v in summary.items() if k!='controlledComparison'},indent=2))
