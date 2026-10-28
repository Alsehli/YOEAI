# Security policy

## Supported scope
This repository is an unsigned development source candidate, not a certified security product. No production support SLA or guaranteed remediation schedule is offered. Use the current candidate and report the exact commit/build when filing a report.

## Report privately
Email **hello@bahraini.online** for suspected vulnerabilities. Include minimal reproduction steps, affected commit, impact and a redacted diagnostic sample. Do not publish credentials, private conversation data, device identifiers or an exploit containing someone else's files. Private vulnerability reporting is enabled: [report a vulnerability](https://github.com/Alsehli/YOEAI/security/advisories/new).

## Operational boundaries
- Keep the UI/inference API on loopback. Do not expose an unauthenticated endpoint to the internet or an untrusted LAN.
- Treat model output, web pages, extracted strings, documents and generated code as untrusted.
- Preserve scoped permissions and explicit approvals for sensitive actions. An agent may not grant itself additional permissions.
- Never automatically execute an unknown binary or arbitrary generated shell command. Update isolation must fail closed when its required sandbox is unavailable.
- Back up user data and retain rollback material before approved changes. A source directory is not an execution sandbox.
- Verify download origin, integrity and license. Do not bypass Windows security prompts, disable Defender/firewall, or claim unsigned binaries are signed.

A passing unit test or credential-pattern scan is useful evidence, not a security certification. Optional runtimes and third-party applications require separate review and updates. See PRIVACY.md, THIRD-PARTY.md and docs/RELEASE-CHECKLIST.md.
