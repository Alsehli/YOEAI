# Release readiness

## Prepared
- Current verified Normal source and original assets; no duplicate model weights.
- Current features, non-profit project description, build instructions and optional-runtime limits.
- Pinned direct build dependencies and source build entry point.
- Source inventory, source/privacy checks and portable regression runner.
- Actual 384-test local QA report; native voice and Fast/Advanced verification.
- CI validation/build workflow; publication is manual, not automatic.

## Before publishing a complete Windows binary release
- Rebuild Normal and Lite installers from the final corresponding source; old setup executables are dated 24 October and do not include the newest voice/model fixes.
- Provision optional runtimes with portable paths or document them as unavailable; current voice setup depends on the developer PC's E:/C: locations.
- Test the exact rebuilt installers on a clean target PC, including VC++ runtime bootstrap, uninstall/update/restart and offline behavior.
- Verify full bundled dependency notices and corresponding-source requirements for those exact binaries.
- Verify unsigned status clearly or sign with a verified publisher certificate; do not claim signing/certification that has not occurred.
- Attach hashes for the exact final assets, review release notes, and publish manually.

The source candidate can be reviewed independently of the unfinished complete installer release. Do not attach stale installers as though they were rebuilt from this tree.
