# Release readiness audit — 27 October 2026

Reviewed repository main, PR #1 and current candidate 852a485, source/build scripts, CI, setup, publication, validation, QA, changelog, license, notices, privacy, security and contribution files.

| Area | Baseline | Work required |
|---|---|---|
| Public homepage | main remains October 16 preview; candidate README is plain | Branded README and precise feature/dependency table |
| Branding | Original fox and licensed fonts present | Reproducible 1280×640 social banner |
| Source integrity | 298-entry source inventory; candidate source preserved | Verify inventory before and after documentation changes |
| CI | Previous head 85477e8 passed hosted Windows checks | Validate updated head; retain test/build/smoke gates |
| Source safety | Existing heuristic scan covers only source/tests/tools | Expand public-text scan across tracked release metadata/docs |
| Security/privacy | Present but brief; external research behavior omitted | Explain local boundaries, web/audio, tools and reporting |
| Community | Contribution/bug/PR templates present | Feature-request template and conduct policy |
| Maintainer profile | Requires live inspection | Use accurate project identity; no invented credentials |
| Installers | Complete Normal/Lite candidate installers not qualified | No public binary upload until exact-asset tests/notices pass |
| Optional runtimes | External developer paths remain | Capability matrix; avoid turnkey/offline-all claims |
| Latest installed improvements | Newer than this source candidate | Preserve candidate, document unsynchronized specialist integration |
| Publication | Draft PR; no complete new release authorized by evidence | Source-only release preparation; keep binary gate explicit |

This checklist precedes implementation. Tests and screenshots are recorded separately; historical QA is not a new execution result.
