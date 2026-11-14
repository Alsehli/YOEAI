# Code signing policy

## Current status
The current product is **YOEAI**, with one app and installer. Historical previews remain unsigned. A Foundation application has been submitted, and the YOEAI SignPath project has an approval-required, self-signed test policy. A manual test-signing request completed on 14 November 2026; the downloaded output hashes, signer and timestamp were checked. See the [exact test-signing record](docs/TEST-SIGNING-20261114.md). This certificate is not a trusted production identity. Account signup and application receipt do not establish production signing approval.

When Foundation signing is activated and verified, the required provider attribution will be: “Free code signing provided by SignPath.io, certificate by SignPath Foundation.” This conditional statement is not a claim that an existing download has been signed. See [SignPath's conditions](https://signpath.org/terms.html).

## Candidate pipeline

[Installer candidate builds](.github/workflows/installer-candidates.yml) build the single YOEAI app from an exact clean candidate tag and upload `YOEAI-Setup.exe`, `YOEAI-Payload.zip`, source/file inventories, dependency versions and transport hashes. PR builds use ephemeral CI tags. Historical Lite/Normal bytes and hashes remain immutable. Current candidates exclude models and optional voice/media runtimes. Pinned native/CUDA inputs and CRT provenance remain recorded; extraction/device enumeration is not complete functional qualification.

The workflow never publishes a release or replaces existing installers. A manual dispatch may request SignPath signing of that same run's artifact. The `release-signing` GitHub environment must require maintainer review and restrict eligible refs. The maintainer must also approve each request under the SignPath policy. Do not enable automatic approval. Fork/PR builds never receive signing credentials.

Configure `SIGNPATH_ORGANIZATION_ID`, `SIGNPATH_PROJECT_SLUG`, `SIGNPATH_SIGNING_POLICY_SLUG`, `SIGNPATH_ARTIFACT_CONFIGURATION_SLUG` and `SIGNPATH_CERTIFICATE_THUMBPRINT` in GitHub. Store `SIGNPATH_API_TOKEN` as a protected environment secret, never in source or chat. The current artifact configuration must sign only top-level `YOEAI-Setup.exe` and preserve its paired payload/inventories. Third-party libraries are not signing targets. The old two-installer test ZIP is superseded and must not be submitted as the current YOEAI artifact. See the [official integration guide](https://docs.signpath.io/trusted-build-systems/github).

The signing job rejects missing configuration, unexpected publisher certificates, invalid signatures and absent timestamps, then generates new signed-byte hashes. Per-file app provenance retains `signed: false` because signing the outer setup does not sign embedded application files. Signing and functional qualification remain separate gates. See [candidate scope and remaining qualification](docs/INSTALLER-CANDIDATES.md).

## People and responsibilities
Maintainer, committer, reviewer and release-signing approver: [Mohamed Yusuf Alsehli / Alsehli](https://github.com/Alsehli). External contributions and signing/build changes require maintainer review. Each release-signing request requires an explicit maintainer approval. Signing credentials must never be committed to this repository.

## Before signing is enabled
Verify account MFA, provider-approved roles, exact source/build provenance, artifact metadata and third-party eligibility. The current Windows installers were built locally; their matching source archives accompany the release. Existing source-shell GitHub CI does not prove those exact installers originated from a trusted CI build. No workflow may silently substitute or sign a different artifact.

CUDA redistributables and the authorized static reverse-engineering/security-review capability are disclosed for provider assessment. Acceptance is the provider's decision; these capabilities will not be hidden or silently removed to seek approval.

## Privacy and signature verification
Read [Privacy](PRIVACY.md) for local storage and network boundaries. Signing does not authorize telemetry or data uploads, change tool permissions, or guarantee absence of Windows warnings. Signed files, if approved later, must be timestamped, verified and published with new hashes while preserving prior release records.
