# Interactive Voice — Fast / Advanced model selection

Added in the existing Voice settings: Fast Qwen3.5 9B and Advanced Qwen3.8 27B. Uses the existing shared model switcher; no model download or duplicate inference instance. Selection persists through the existing global model catalog. Switching requires ending voice first and the normal idle checks. The choice affects chat and agents as well as voice. Existing live dictation outside Interactive Voice remains Fast-only.

## Actual tests, 2026-10-25
15 existing Interactive Voice tests and 3 new selection tests passed. New tests cover accepting Fast/Advanced and rejecting unknown running models without granting microphone activation. JavaScript syntax check passed. Existing premium native Qt layout/control tests repeated at all three sizes; controlled API responses are used for UI states.

Real installed model backend and actual microphone/speaker service test:
- Advanced: E:/Qwen3.8-27B-UD-IQ3_S.gguf; switch 22.397 s; GPU sample before voice 13,956 MiB, with voice 15,259 / 16,311 MiB. Real generated response “Four.” was synthesized and playback completed. First model token 0.563 s in this short test.
- Fast: existing C:/AI/Models/DeepSeekV4/DeepSeek-V4-Pro-Qwen3.5-9B-MTP-Q6_K.gguf; return switch 11.281 s; GPU sample with voice 11,721 / 16,311 MiB. Real generated response “Two plus two equals four.” was synthesized and playback completed. First model token 0.170 s.
- Test question was programmatically supplied text, not a new human microphone transcription trial. Audio devices opened and replies played through the existing worker. Raw responseStartSeconds in the fixture are invalid because no real speech-origin event was supplied; do not interpret them as latency. GPU readings are samples, not continuous peaks. First-token numbers are a single short comparison during build activity, not a general performance benchmark.
- Both sessions ended and the backend was restored to Fast after testing. No CUDA OOM observed in these short tests. Advanced leaves limited headroom; longer requests and other GPU applications may change behavior.

Changed source: interactive_voice.py (accept verified running Fast/Advanced rather than invoking dictation's Fast-only restriction); assets/interactive-voice.js (existing settings selector, shared switch route, loading/errors). Existing backend ownership, permissions, speech model, TTS, microphone pipeline and premium styles preserved. Normal EXE rebuilt from the stable installed source; unrelated pending source work not included. C/D source, app and manifest sync included. Lite/installers unchanged.

## Installed build verification
The actual installed Normal Voice settings selected Advanced through the real selector; the backend loaded and microphone reached Listening. Mute, Unmute, Interrupt and End passed. Screenshot model-settings.png records the actual selector. Restored Fast as the previous default after testing; users can select Advanced in Voice settings. No new human transcription trial was performed.
