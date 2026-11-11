# Context presets and loading progress — 11 November 2026

Installed in the existing Desktop/E: application. Quick selects 16,384 tokens; Long selects 196,608 tokens. Both are capped at the model-declared context limit, or the existing conservative 16K limit when metadata is unknown. Users select a preset and use Apply & restart. Existing saved context remains 196,608; no automatic reduction or memory-fit guarantee is applied.

Loading status now reports engine initialization, combined weight reading/memory or GPU transfer, context preparation/compatibility checks, and readiness. A monotonic elapsed timer is shown while loading. The runtime does not separately expose disk reads and GPU transfer, so the interface uses one combined stage. The progress bar becomes indeterminate during context allocation rather than implying the model is ready at 100% of weight transfer. The loading banner stays visible even after the welcome banner was previously dismissed.

Validation: five new preset/stage regressions, three loading/recovery regressions, 31 audit regressions and 242 syntax/asset checks passed. Installed Chrome UI checks confirmed both preset selections and preservation of saved context/model path; screenshot inspected. Actual installed load of C: Qwen3.8-27B Q4_K_M completed in 11.484 seconds; polling observed initializing, weights, context and ready stages and elapsed text. No generation or live web research was run in this change.

Desktop model-folder shortcut remains C:\YOEAI-Models. Existing E: originals remain backups. Prior app executable backup: E:\YOEAI-Packages\YOEAI-3.0-Local\Before-context-presets-20261111. Raw UI/stage checks are in the task outputs/YOEAI-System-Audit directory.
