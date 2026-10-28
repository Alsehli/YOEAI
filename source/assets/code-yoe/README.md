# Code YOE animation assets

The supplied E:/Code YOE Fox Animation Sprite Sheet.png is a reference poster with baked backgrounds, labels and inconsistent cell dimensions. The four larger poses were cleaned/re-laid out by the built-in imagegen tool. They are reference-derived artwork, not exact extractions of all numbered frames. Disconnected background specks were removed during deterministic atlas preparation. Subject alpha edges are retained.

poses.png is the only runtime image: 1024x1024 RGBA, four normalized 512x512 cells. The same common scale and right/bottom anchor is used for each pose. The Code-only renderer is code-fox.js. It does not load models, send network requests or change task execution.

Eight states each have eight derived frames at 10 FPS: idle, thinking, typing, working, happy, success, error and sleeping. idle/thinking/typing/success use the four cleaned base poses. Blinks, breathing, typing paw motion, code effects, small tilts, bounces and sleeping eyelids are Canvas-derived. Happy, error and sleeping are not claimed as extracted reference rows.

Exports: STATE-sprites.png is a transparent 4096x512 sheet of eight 512x512 frames. STATE.webp is a transparent eight-frame animation with 100ms frame duration. Export files are deliverables; runtime does not load all sheets or WebPs. It shares one atlas (~0.74 MB compressed, 4 MB decoded) among visible Code canvases.

State mapping: queued/planning/approval/paused -> thinking; running streamed code -> typing; checks/tools or a running task before streaming -> working; review -> thinking; recent completion -> success then happy then idle; failure -> error; 90s of inactivity or an offline idle model -> sleeping. Pointer/keyboard interaction wakes idle. Old historical completions do not celebrate repeatedly on startup.

The 10-FPS timer skips hidden pages and offscreen/hidden canvases. Reduced motion draws a static pose only when state changes. The original main mascot and Research/Windows fox assets are untouched. Only the former Code drawing path is skipped when the new renderer is ready; its old fallback remains if loading fails.

Tests and provenance are in Documents/Code-YOE-Animation in the matching package. Use existing desktop build tooling; no new Python/runtime dependencies are required. Animation exports were created with the same Canvas drawing function used in the app, then packed/encoded with Pillow.
