# Developer source setup

Use Windows x64 and Python 3.13. Install `requirements-build.txt`, then run `python tools/test_portable.py`, `python tools/check_release.py`, and `python tools/check_docs.py`.

`python build.py` builds the desktop UI and private inference worker without downloading models or runtime libraries. This default build can run the UI smoke test but cannot infer until the runtime is supplied.

For native inference, use `python build.py --native-runtime PATH` with an existing, trusted b11784 directory containing its runtime-manifest.json and matching DLLs. The build verifies all hashes and the ABI before copying. Include the native license notices. Do not use random DLL replacements. Configure an existing compatible GGUF through Settings; model weights are not bundled.

Use a separate LOCALAPPDATA profile for development. Never copy production credentials, ownership records or private histories. Optional speech/image/video/Ghidra/Unity/Adobe components require separate supported configuration and are not installed by this build.

See [current preview limitations](RELEASE-20261107.md) and [Windows downloads](WINDOWS-DOWNLOADS.md). The desktop UI transport remains local HTTP; inference uses private pipes and embedded native libraries, not an HTTP model server.
