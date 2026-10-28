# Published source and Windows preview

The verified developer source was merged through PR #1 and published as [v2.0.20261028-rc.1](https://github.com/Alsehli/YOEAI/releases/tag/v2.0.20261028-rc.1). Hosted Windows validation, 31 portable tests, compiled build and disposable-profile shell smoke passed for a1cbd79. These checks do not run models, physical microphones or clean-PC installation.

The [Windows preview](https://github.com/Alsehli/YOEAI/releases/tag/v2.0.20261028-windows-preview) separately distributes the unchanged tested Lite 2.0.2 and Normal 2.0.20261027.1 installers, matching edition sources, notices, qualification record and checksums. Those binaries are newer than the developer Git snapshot; their corresponding source is attached to the Windows release. Do not substitute the old source snapshot or earlier installers.

The maintainer reports Lite installation and online/offline chat passed on another PC, and Normal installation/chat/restart/offline checks passed on the current PC. These are accepted user-reported tests. Both installers are unsigned, and optional-runtime limits are documented. Signing, comprehensive lifecycle qualification and every optional engine/hardware combination are not certified.

Publication remains a maintainer-controlled action. The Windows CI workflow cannot automatically publish or install models. For a future full stable release, retain exact-asset hashes, matching source/notices and the remaining release-readiness checks.
