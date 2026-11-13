# YOEAI source setup

YOEAI is now one product. Use Windows x64 and Python 3.13. Install both `requirements-build.txt` and `editions/lite/source/build-requirements.txt`, then run `python tools/test_portable.py`, `python tools/check_release.py` and `python tools/check_docs.py`.

The active source remains under `editions/lite/source` for compatibility. The historical root app and old build helpers are preserved as references, not as another current edition.

Use an exact clean reviewed `candidate-*` tag with `tools/build_installer_candidates.py`. The [candidate build guide](INSTALLER-CANDIDATES.md) gives the complete commands, runtime provisioning and validation scope. Output is `YOEAI-Setup.exe`, its paired `YOEAI-Payload.zip`, provenance and hashes; the app is `YOEAI.exe`. Native inputs must match the pinned b11784 ABI and integrity manifest. Preserve notices and use existing compatible models rather than copying private profiles or duplicate weights.

Use a separate LOCALAPPDATA profile for development. Never copy production credentials, ownership records or private histories. Optional speech/image/video/Ghidra/Unity/Adobe components require separate supported configuration and are not installed by this build.

See [current and historical downloads](WINDOWS-DOWNLOADS.md). Candidate extraction, clean-PC behavior, physical devices and exact signed bytes have separate qualification gates. The UI uses local HTTP; inference uses private pipes and native libraries rather than an external model server.
