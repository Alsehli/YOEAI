# YOEAI test-signing record — 14 November 2026

The maintainer explicitly requested and approved a manual test signature through the existing SignPath `test-signing` policy. Request `bc69f2d3-b958-45b8-a5e0-d2bcb9196336` completed at 06:50:23 UTC after malware scanning. This uses the self-signed test certificate, not an approved production identity.

## Exact input and output

The setup-only input is artifact **14034986527** from [Windows candidate run 43421842100](https://github.com/Alsehli/YOEAI/actions/runs/43421842100), head `41e50c4f8faaf9337db0cb0d8fcf17503d6c8256` (PR #32). That PR was reviewed and merged at `a5a919229ab4ef490338527f8f0cb446fe9982a4`. The artifact contains only top-level `YOEAI-Setup.exe`; its paired payload is retained with the complete artifact from that same CI run. The signature does not include subsequent changes in PRs #33 or #34.

| Artifact | SHA-256 |
| --- | --- |
| Unsigned input ZIP | `6c256ff5ba7b74df8d7d868115fcff010c63a67bf280b06209c955c4d5515756` |
| Unsigned setup | `bfd9b82dabf33852f6a51954b7286260562cfe5d627b2ea81dcde7723d9e9ffc` |
| Signed output ZIP | `9676a1c4a8cccfbe55ee73e6cd6e136a34dc24a0435b290917414d16996c6a1d` |
| Signed setup (11,632,912 bytes) | `b01b3cf1f27a99a502f960254b21cecfe7039839dbef708a5982109b69353c0b` |

The downloaded output ZIP and its sole setup entry independently matched SignPath's output hashes. Windows Authenticode inspection reported signer `CN=YOEAI Test Signing Only`, expected certificate thumbprint `F59BE440AA487F2F2D5328350B13196AA4E71E31`, and timestamp signer `DigiCert SHA256 RSA4096 Timestamp Responder 2026 1`.

Windows reported `UnknownError`: the certificate chain terminates in an untrusted root. This is the expected test-certificate limitation. It is not a trusted Windows release signature or evidence of SmartScreen reputation. No trust certificate was installed, approval rules weakened, API credential created, signed installer executed or public release replaced.

## Remaining release requirements

Issue [#6](https://github.com/Alsehli/YOEAI/issues/6) remains open for a provider-approved production identity, protected trusted build/signing integration, exact signed-byte clean-PC qualification and truthful versioned publication. The Foundation application receipt alone does not establish approval. Complete offline models, optional runtimes and device/accessibility qualification remain separate requirements in #5, #7, #8 and #11.

See [code-signing policy](../CODE-SIGNING.md) and [candidate scope](INSTALLER-CANDIDATES.md). This record publishes evidence and hashes, not a new supported installer download.
