# YOEAI Fox visual assets

Generated using the built-in image-generation tool from the user-approved fennec fox reference, 15 October 2026. Original PNG preserved byte-for-byte. Four rows: walk, think, idle, happy wave. Eight phases per row.

The generated sheet has uneven cell spacing. frames.json and frames.js contain individual opaque-character bounds plus a 2px gutter. Never divide this sheet into uniform cells. Native and web renderers use the same rectangles and stable baseline. Canvas uses no remote assets.

Rates: startup/model initialization 5 fps; thinking/processing/completion 4 fps; idle/error 2 fps. The web animation pauses drawing when hidden and honors reduced motion. State detection only reads existing UI status and request controls. It does not change model calls, history, settings or PC commands.
