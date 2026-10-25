# Setup and portability

The source build is a launcher/UI, not a bundled offline model distribution. The existing configuration.py reads LOCALAPPDATA/AlsehliAI-Preview/config.json. Back up your profile before testing a new build; use a separate LOCALAPPDATA directory for development.

Required for local chat: Windows x64, an installed compatible llama.cpp CUDA server, a compatible GGUF model, and an appropriate configuration containing model, projector (where supported), apiPort, uiPort, context and externalBackend. Keep UI and inference on loopback. Default paths are placeholders under the profile; source does not contain your working configuration.

Normal model switching uses its existing model catalog and backend ownership records. The current local 27B file was tested at 8192 context; developer defaults/reference paths are not portable discovery guarantees. Never copy another PC's ownership/PID files.

Optional components need separate configuration: Image Turbo/Design, LTX video, local speech, SearXNG, Ghidra/JDK, Unity and Adobe applications. They are not downloaded by build.py. Some adapters preserve development-machine paths; absence must be reported, not silently advertised as working. Interactive Voice needs SpeechInput/interactive-config.json referring to the external speech environment, worker, speech model and Kokoro/eSpeak directory. No private config is distributed here.

Do not point setup at a working installation. Installation policy drafts and activation services are not release-qualified in this source candidate. Existing setup binaries predate the latest source. A source-built preview requires its own dependency/notices audit before redistribution as a complete binary bundle.
