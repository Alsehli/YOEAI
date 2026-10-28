# Project roadmap

This is a living backlog, not a promise of release dates or completed security qualification. Use the linked GitHub issues and project board for evidence and status.

## Current verified baseline

- Windows Lite and Normal unsigned preview installers are published with checksums and matching source archives.
- The maintainer reports Lite other-PC and Normal current-PC installation/restart/offline chat qualification.
- Hosted Windows source checks, build and disposable-profile smoke tests pass. They do not test optional model workers, a physical microphone or every device.

## Next acceptance gates

1. **Reproducible installer pipeline:** build each edition from its matching tagged source on a documented clean runner, with source/payload hashes and artifacts. The older main source snapshot must not be represented as the matching installer source.
2. **Trusted code signing:** obtain an approved signing identity, sign release artifacts, verify signatures and timestamping, and update checksums. Current installers remain unsigned. A submitted application is not a certificate.
3. **Portable optional runtimes:** qualify voice, image, video, Ghidra/JDK and Unity integrations separately from the core installer, without copied developer-only paths or duplicate weights.
4. **Security findings:** triage real CodeQL/dependency findings, reproduce them and test repairs. A configured scanner is not a clean security audit.
5. **Accessibility and hardware matrix:** keyboard navigation, screen-reader coverage and actual Windows display scaling across supported editions. Simulated sizes alone do not certify hardware or assistive-technology compatibility.

## Contribution workflow

Open a reproducible bug or focused feature request. Link patches to their issue, supply actual test evidence and preserve user data, permissions and model files. See [Contributing](../CONTRIBUTING.md), [Security](../SECURITY.md) and [release qualification](RELEASE-CHECKLIST.md).
