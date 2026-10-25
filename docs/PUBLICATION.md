# Publication plan

Review this source candidate in a draft pull request before merging main. The Windows workflow validates source, runs 31 portable contract tests, builds an unsigned launcher and checks shell construction without loading a model.

The separate local qualification ran 384 tests against an installed Normal source snapshot. Neither result substitutes for a clean-PC test of rebuilt setup executables. Do not publish the old Normal/Lite setup binaries with this candidate.

Suggested source candidate label: `v2.0.20261025.4-rc.1`. No tag/release is automatically created by this workflow. Source archives and SHA-256 checksums can be generated from the reviewed commit with `git archive`; model weights remain external. Final binary publication waits for docs/RELEASE-CHECKLIST.md gates.
