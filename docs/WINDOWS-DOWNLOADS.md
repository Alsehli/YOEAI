# Installing the native Windows preview

Download from the [7 November unsigned prerelease](https://github.com/Alsehli/YOEAI/releases/tag/v2.0.20261107-native-preview). Lite targets compatible NVIDIA 8GB systems; Normal targets 16GB. Hardware and model architecture compatibility still apply.

1. Download the edition installer and SHA256SUMS.txt. Lite is ZIP-compressed because its EXE exceeds GitHub's per-file limit. Extract it before running.
2. Verify the downloaded file using `Get-FileHash -Algorithm SHA256` and compare against the same release's checksum file.
3. Back up your profile and preserve existing model files. Run setup, choose an existing compatible GGUF, and open the edition shortcut. You can change GGUF later in Settings.
4. The installer bundles the native inference runtime and private worker. No separate llama-server is needed. Chat/image/video model weights are not bundled; optional engines require their own supported configuration.
5. Do not bypass Windows security warnings blindly. These builds are unsigned; signing and comprehensive clean-PC qualification remain pending.

Read [actual tests and limitations](RELEASE-20261107.md). Older user-reported online/offline installation tests do not qualify newly rebuilt installers. Matching edition sources are attached to the release; preserve the included licenses and third-party notices.

[Report a reproducible bug](https://github.com/Alsehli/YOEAI/issues/new/choose) with edition, filename, Windows/GPU details and sanitized errors. Never publish private documents or credentials.
