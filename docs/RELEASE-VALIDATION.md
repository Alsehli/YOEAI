# Source candidate validation — 25 October 2026

- Source/credential-pattern check: 352 candidate files checked, no findings. This heuristic is not a guarantee against every possible secret.
- Portable CI contract subset: 31 tests passed locally in 1.925 seconds.
- `python build.py` completed against this public candidate tree with the pinned direct dependency versions already installed in the development environment. This was not a fresh dependency-environment resolution test.
- Newly built `dist/YOEAI/YOEAI.exe --smoke-test`: PASS, expected Windows commands/Settings menus. Native shell construction only; no model/microphone loaded and a disposable LOCALAPPDATA profile used.
- Full installed-source qualification: 384 tests passed; see QA-20261025.md for scope and exclusions.
- GitHub-hosted CI has not yet run at preparation time. Its actual result must be checked on the pull request before merging.
- Existing bundled third-party notices and the exact original source line endings retained. Cosmetic whitespace in original notices/source was not rewritten for this release.

Complete Normal/Lite installer rebuilding and clean-PC qualification remain outstanding. The locally generated source preview launcher is not represented as a complete end-user offline installer.
