# Code signing policy

## Current status
YOEAI's published Windows previews are unsigned. A SignPath Foundation eligibility application is being prepared. No acceptance, certificate, SignPath account access or signing coverage is claimed.

If accepted and activated, the required provider attribution will be: “Free code signing provided by SignPath.io, certificate by SignPath Foundation.” This conditional statement is not a current sponsorship claim. See [SignPath's conditions](https://signpath.org/terms.html).

## People and responsibilities
Maintainer, committer, reviewer and release-signing approver: [Mohamed Yusuf Alsehli / Alsehli](https://github.com/Alsehli). External contributions and signing/build changes require maintainer review. Each release-signing request requires an explicit maintainer approval. Signing credentials must never be committed to this repository.

## Before signing is enabled
Verify account MFA, provider-approved roles, exact source/build provenance, artifact metadata and third-party eligibility. The current Windows installers were built locally; their matching source archives accompany the release. Existing source-shell GitHub CI does not prove those exact installers originated from a trusted CI build. No workflow may silently substitute or sign a different artifact.

CUDA redistributables and the authorized static reverse-engineering/security-review capability are disclosed for provider assessment. Acceptance is the provider's decision; these capabilities will not be hidden or silently removed to seek approval.

## Privacy and signature verification
Read [Privacy](PRIVACY.md) for local storage and network boundaries. Signing does not authorize telemetry or data uploads, change tool permissions, or guarantee absence of Windows warnings. Signed files, if approved later, must be timestamped, verified and published with new hashes while preserving prior release records.
