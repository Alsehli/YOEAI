# Installing the Windows preview

Download one edition from the [Windows release](https://github.com/Alsehli/YOEAI/releases/tag/v2.0.20261028-windows-preview): Lite for the compatible NVIDIA 8GB configuration, Normal for the 16GB configuration. These are unsigned Windows x64 personal-project previews. They are free to download; optional support does not purchase access.

1. Download the complete setup EXE and `SHA256SUMS-WINDOWS.txt` from the same release.
2. Check the file hash with PowerShell: `Get-FileHash -Algorithm SHA256 .\YOEAI-Lite-Setup-2.0.2.exe` (use the Normal filename if applicable). Compare the value with the checksum file.
3. Run setup and use the resulting edition shortcut. Preserve existing profiles/model folders and keep a backup of important data.
4. Initial setup requires matching offline model/runtime files or an internet connection for setup downloads. Chat/image/video weights are not included in the installer download. Core chat can run offline once configured.
5. Optional Advanced 27B, Interactive Voice, image/Design/video, Ghidra/JDK, Unity and Adobe integrations need their own supported installation/configuration. Read `OPTIONAL-COMPONENTS.json` and `INSTALL-WINDOWS.md` attached to the release.

Lite 2.0.2 and Normal 2.0.20261027.1 are the unchanged tested installer files. The maintainer reports Lite installed and chat worked online/offline on another PC, and Normal installation/chat/restart/offline checks passed on the current PC. These results are user-reported. Older preview/pending labels inside the installers were retained to preserve tested bytes. Signing/certification and comprehensive optional-engine qualification are not claimed.

The three source archives attached to the Windows release correspond to these newer installers. The earlier developer Git tag is a separate snapshot; do not treat a passing source-only CI run as proof that the Windows installer was built from that older source. Preserve each edition's application and bundled third-party notices.

For reproducible problems, [report a bug](https://github.com/Alsehli/YOEAI/issues/new/choose) with the edition, installer filename, Windows version, hardware and error message. Do not include passwords, keys or private documents.
