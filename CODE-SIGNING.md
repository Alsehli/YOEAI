# Code signing policy

## Current status
YOEAI's published Windows previews are unsigned. On 12 November 2026, the maintainer reported SignPath approval. Organization/project/policy configuration and an observed signed artifact are still required; approval alone does not sign existing downloads. No certificate or completed signing coverage is claimed by this source update.

When Foundation signing is activated and verified, the required provider attribution will be: “Free code signing provided by SignPath.io, certificate by SignPath Foundation.” This conditional statement is not a claim that an existing download has been signed. See [SignPath's conditions](https://signpath.org/terms.html).

## Candidate pipeline

[Installer candidate builds](.github/workflows/installer-candidates.yml) build Lite and Normal from one exact clean candidate tag and upload matching source/file inventories, dependency versions and transport hashes. Pull-request builds use an ephemeral CI tag and are not published release tags. These source-candidate installers are separate from the complete historical distributions: models and optional voice/media runtimes are excluded. CI explicitly provisions checksum-pinned, ABI-paired native/CUDA runtime inputs with notices and an allowlist that excludes server/RPC programs. Microsoft CRT carrier versions/hashes are recorded. Successful extraction or native library enumeration is not clean-PC or inference qualification.

The workflow never publishes a release or replaces existing installers. A manual dispatch may request SignPath signing of that same run's artifact. The `release-signing` GitHub environment must require maintainer review and restrict eligible refs. The maintainer must also approve each request under the SignPath policy. Do not enable automatic approval. Fork/PR builds never receive signing credentials.

Configure these environment variables in GitHub: `SIGNPATH_ORGANIZATION_ID`, `SIGNPATH_PROJECT_SLUG`, `SIGNPATH_SIGNING_POLICY_SLUG`, `SIGNPATH_ARTIFACT_CONFIGURATION_SLUG` and `SIGNPATH_CERTIFICATE_THUMBPRINT`. Store `SIGNPATH_API_TOKEN` as an environment secret, not in source, issues or chat. The SignPath artifact configuration must sign the two top-level `Lite-Setup.exe` and `Normal-Setup.exe` files and preserve the paired payloads/inventories; it must not sign third-party bundled libraries. See the [official integration guide](https://docs.signpath.io/trusted-build-systems/github).

The signing job rejects missing configuration, unexpected publisher certificates, invalid signatures and absent timestamps, then generates new signed-byte hashes. Per-file app provenance retains `signed: false` because signing the outer setup does not sign embedded application files. Signing and functional qualification remain separate gates. See [candidate scope and remaining qualification](docs/INSTALLER-CANDIDATES.md).

## People and responsibilities
Maintainer, committer, reviewer and release-signing approver: [Mohamed Yusuf Alsehli / Alsehli](https://github.com/Alsehli). External contributions and signing/build changes require maintainer review. Each release-signing request requires an explicit maintainer approval. Signing credentials must never be committed to this repository.

## Before signing is enabled
Verify account MFA, provider-approved roles, exact source/build provenance, artifact metadata and third-party eligibility. The current Windows installers were built locally; their matching source archives accompany the release. Existing source-shell GitHub CI does not prove those exact installers originated from a trusted CI build. No workflow may silently substitute or sign a different artifact.

CUDA redistributables and the authorized static reverse-engineering/security-review capability are disclosed for provider assessment. Acceptance is the provider's decision; these capabilities will not be hidden or silently removed to seek approval.

## Privacy and signature verification
Read [Privacy](PRIVACY.md) for local storage and network boundaries. Signing does not authorize telemetry or data uploads, change tool permissions, or guarantee absence of Windows warnings. Signed files, if approved later, must be timestamped, verified and published with new hashes while preserving prior release records.
