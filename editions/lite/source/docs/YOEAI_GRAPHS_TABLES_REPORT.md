# YOEAI 3.0 — Interactive graphs and tables

Implemented directly in the existing Lite chat. Installed UI assets are updated in the E: application used by the existing Desktop/Start menu launchers. The executable was not rebuilt, the inference backend was not changed, and model/settings/history files were not replaced.

## Libraries and presentation

**Charts:** retained the locally bundled Apache ECharts 6.1.0, including its Apache license/notices. Its existing SVG renderer, tooltip/legend controls, zoom, resizing and image export fit the current Edge/HTML application. Replacing it with Plotly would duplicate an already working rendering dependency. No CDN or cloud rendering is used.

**Tables:** extended the existing YOEAI bounded DOM/virtual-scroll component (`YoeVisualTables`). No new editor, agent, app framework or table dependency was introduced. It renders 50 rows per page or a bounded virtual window.

Supported and tested: bar, horizontal bar, line, area, pie, donut, scatter and histogram charts; multiple compatible series; chronological ISO date/time series. Hover tooltips use trusted rich-text rendering rather than model HTML. Legends show/hide series; Cartesian charts support zoom and pan. Views resize, support light/dark themes and expand into an in-app dialog. Chart SVG/PNG and chart-data CSV export work locally.

Tables support ascending/descending and Shift+click multi-column sorting, search, text/numeric/date filters, ranges and missing-value filters, pagination, virtual scrolling, column widths/visibility/order, sticky headers, horizontal scrolling, focused-cell Ctrl+C, selected-row/full-table copying, CSV and XLSX. Missing values remain missing; BHD retains three decimals. Source URLs are included in sourced exports, and column units are retained in export headings.

## Normal conversation and shared data

The normal composer automatically requests structured data output when appropriate. Selected Qwen remains the intelligence for new data presentations and nontrivial operations. No chart mode or additional agent selection is needed. CSV/dataset attachments remain local.

A version 1.1 data view has stable view/dataset/row/source IDs and a revision. A table and its charts are projections of that same validated dataset. Table filtering updates linked charts; conversational changes update the relevant existing assistant message rather than regenerating other answers. Straightforward sort, filter, removal, chart, aggregation and ranking follow-ups run locally. Model-planned patches require the current target ID/revision and are applied transactionally.

Supported local calculations: sum, mean/average, min/max, median, count, percentage, percentage change, ratios/differences, competition ranking, grouping and a simple linear trend slope per supplied row position. The application computes these values; model-precomputed calculated columns are not accepted as a substitute. A denominator can be an explicitly supplied constant or a dataset aggregate. Division by zero and insufficient data yield missing values. Calculations are bounded finite JavaScript numbers, with compensated summation; they are not arbitrary-precision accounting calculations.

Standard SI/IEC byte-unit conversions are deterministic. Currency conversion requires an explicitly supplied rate and currencies, or matching retrieved rate evidence; no exchange rate is inferred. Original and converted columns retain separate units.

## Validation, research and privacy

`data-schema.json` documents version 1.1 data views/updates. Structural and semantic JavaScript validation enforces bounded sizes, unique IDs, known fields, typed cells, ISO calendar dates, finite values, compatible units, source references and allowed operations. Existing version 1.0 visual specifications remain supported. Model output never becomes executable JavaScript, HTML or arbitrary ECharts options.

Research uses the existing ordinary-chat preparation pipeline. Source URLs must belong to actual returned sources. Numeric measurements must appear in referenced retrieved page evidence with the declared unit; unsupported values become missing. Row/cell citations survive sorting, filtering and exports. These checks establish evidence consistency, not independent semantic verification of every product/measurement association. Pages remain untrusted data. Private and calculated local datasets are excluded from public research history.

Unfinished model JSON does not render as an approved data view. Invalid or stale updates leave the original dataset intact. There is no arbitrary formula evaluator or remotely executed chart code.

## Executed verification

| Group | Passed |
| --- | ---: |
| Deterministic validation, data, calculation, export and conversation cases | 166 |
| Real Chromium/ECharts/table interaction scenarios | 42 |
| Installed-chat research/model fixtures | 8 |
| Installed selected-Qwen chat checks | 7 |
| **Graph/table functional scenarios** | **223** |
| Python/JavaScript syntax and asset checks (separate) | 250 |

All 223 functional scenarios executed successfully. Existing citation (12), link-navigation (8) and keyboard-control (6) regressions also passed; those are separate from the 223 graph/table scenarios. JSON Schema validation accepted the actual Qwen data view. Three exported XLSX archives passed ZIP/XML inspection; exported SVG parsed, and PNG decoded successfully. Excel desktop was not opened.

The real selected model generated the supplied Jan/Feb/Mar values as a table and bar chart. Five normal-chat follow-ups sorted, switched chart type, removed a row, calculated an average and added a locally computed rank. The final run made one streamed chat-completion request; these follow-ups avoided further research/inference calls. Existing local preparation may perform its own planning. The model stayed selected and loaded at its existing context.

The eight research scenarios stub research/model responses with explicit fixture pages. They test exact values, citations, source-bearing XLSX, rejection of fabricated citations, missing unsupported prices and unjustified currency relabeling. They are not live Bahrain price searches.

The 10,000-row fixture kept DOM row counts bounded and passed a three-second mount guard; its recorded local mount was about 0.05 seconds and search about 0.17 seconds. These are fixture observations, not hardware-independent guarantees.

Reproduce from Lite/Source:

```powershell
node tests_visuals/data.cjs
..\..\.venv\Scripts\python.exe tests_visuals/browser.py
..\..\.venv\Scripts\python.exe tests_visuals/research_ui.py
# Requires the already-selected idle/loaded local model; does not load another model:
..\..\.venv\Scripts\python.exe tests_visuals/live_qwen.py
..\..\.venv\Scripts\python.exe tests_system/syntax_assets.py
```

Browser fixtures use installed Chrome and Playwright. Raw records, exported artifacts and screenshots are retained in the task output folder. Functional summary: `YOEAI_GRAPHS_TABLES_RESULTS.json`.

## Bugs found and fixed

- Existing visual preparation/payload hooks were not connected to the normal Lite submit path.
- Follow-ups had no stable transactional data-view target or row/source identity.
- Numeric/date filters were substring searches and sorting supported one column only.
- Filtering a table did not update its chart, and short charts lacked zoom controls.
- BHD and XLSX currency formats forced two decimals; small numeric values could display as zero.
- Source metadata/units could be lost in exports. New views preserve source URLs and units.
- Model-generated precomputed ranks could pass as measured columns. Ranking now executes deterministically; unsupported supplied values are withheld.
- Missing dates could interrupt chronological chart ordering; date sorting now puts missing dates last.
- Streamed or rejected model data could briefly appear before validation. Views are now approved before rendering.
- A metadata lookup could repeat filtering for each row; the lookup is built once, keeping large-table rendering bounded.
- Axis labels could overlap the zoom slider, and dark-theme source links needed more contrast.

## Files created and modified

Created:

- `assets/visual-engine/data.js` — protocol validation, deterministic transforms/calculations, sources and exports.
- `assets/visual-engine/conversation.js` — history targeting, Qwen protocol, safe view approval/rendering and conversational updates.
- `assets/visual-engine/data-schema.json` — versioned data/operation schema.
- `tests_visuals/data.cjs`, `browser.py`, `research_ui.py`, `live_qwen.py`, `fixture.html`, `write_schema.py`, `.gitignore`.
- This report and `docs/YOEAI_GRAPHS_TABLES_RESULTS.json`.

Modified:

- `ui.html` — normal-chat hooks and locally loaded modules.
- `assets/web-search.js` — bounded page evidence and private-data history exclusion.
- `assets/visual-engine/core.js`, `tables.js`, `charts.js`, `exports.js`, `renderer.js`, `integration.js`, `visual-engine.css`.
- `.gitignore` and the recorded syntax-check results.

## Limits and remaining qualification

- Dataset limits: 1 MB, 10,000 rows and 32 columns; individual charts have existing bounds of 5,000 points, 500 bars and 30 pie categories. Aggregate/filter large data instead of silently truncating it.
- Complex joins, arbitrary spreadsheet formulas, predictive statistics and arbitrary code execution are not implemented. Ambiguous model requests can require clarification; invalid output is rejected.
- Retrieved-number/unit matching is conservative and can omit valid values whose formatting/units differ from the extracted evidence. It does not prove semantic association or source truth, and no live market-price accuracy qualification was performed.
- SI/IEC byte conversions are built in; other physical conversions need supported explicit data. Currency rates must be supplied or evidenced. No automatic currency-rate service was added.
- Normal chat retains current model/context limits. Very large files or long responses may need a smaller dataset or aggregation.
- No model-memory benchmark, long-duration GPU soak, fresh-PC installer validation or Excel desktop interoperability run was performed. No photograph, image generation, video or voice generation was exercised.
- Existing app windows load JavaScript at page load; reopening/refreshing displays the updated UI. Future installer builds can package these files, but this task did not rebuild installers or publish new GitHub/download artifacts.
