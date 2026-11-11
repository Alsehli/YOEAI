# YOEAI 3.0 installer preparation

Kandinsky preparation update, 10 November 2026: offline transport and package
staging now exist in `offline.py` and `prepare_kandinsky_release.py`. Both online
and offline install controls remain disabled. No installer, app or inference
was executed for this update. Local manifests are unsigned and untested. Do not run the Local checks commands below until testing is explicitly authorized. See
`../docs/KANDINSKY-PREPARATION.md` for the current backend and packaging state.

Production downloads are disabled. The endpoint is reserved, not published:
https://downloads.yoeai.online/3.0/stable/manifest.json

The existing Lite installer, inference backend and data-home selection are not
replaced by this bootstrap. No Lite or Full fallback URL exists in it. The new
bootstrap installs a verified version to its own new directory, refuses to
overwrite an existing version, and does not migrate or remove personal data.
It does not register an uninstaller, replace a shortcut or activate a release.
Those steps belong to the remaining unified-product migration.

## Configuration and trust

`release-config.json` contains `enabled`, `manifestUrl`, `channel`, and
`trustedKeys`. URLs must use HTTPS. The command line accepts `--config PATH`,
`--destination PATH`, and `--cache PATH`. Keep the shipped config disabled until
the real endpoint, complete payload, licensing and target-PC qualification have
been verified. No production signing key is supplied. Do not ship fixture keys.

The endpoint returns an envelope:

```json
{
  "keyId": "production-key-id",
  "signed": {
    "schemaVersion": 1,
    "product": "YOEAI",
    "channel": "stable",
    "version": "3.0.0",
    "issuedAt": "2026-11-10T00:00:00Z",
    "expiresAt": "2026-11-17T00:00:00Z",
    "entrypoint": "app/YOEAI.exe",
    "assets": []
  },
  "signature": "BASE64_ED25519_SIGNATURE"
}
```

This is a schema example, not a usable manifest. `assets` must contain the
application plus text, image, video, speechRecognition and speechSynthesis
components. Support components may also be included. Every asset contains:

- `id`: unique ASCII letters, digits, `_` or `-` (1–100 characters).
- `kind`: one of the component names above or `support`.
- `version`: pinned component/model version, independent of the app version.
- `url`: HTTPS asset URL. Release metadata and assets may use different hosts.
- `bytes`: exact positive download size.
- `sha256`: lowercase SHA-256 of the downloaded asset.
- `format`: `file` or `zip`.
- `path`: normalized relative installation file path or archive directory.
- `unpackedBytes`: positive extraction budget, required for `zip`.

For example the app archive can use `path: "app"` and contain `YOEAI.exe`;
text weights can use `path: "Models/text/model.gguf"`. Archives reject Windows
device names, streams, path traversal, symlinks, duplicate files and extraction
above the signed size budget. Package and model versions are never inferred
from a filename or substituted from an old distribution.

Sign the UTF-8 bytes produced by `canonical(signed)` in `releases.py`: JSON with
sorted keys, no extra whitespace, literal Unicode and no NaN/Infinity. This is
the exact project encoding, not a claim of RFC 8785 compatibility. Use Ed25519
and base64-encode the 64-byte signature. `trustedKeys[keyId]` must be the base64
32-byte public key distributed through a trusted installer update. The private
key stays in the release signing system. The payload signature is checked
before any asset is requested; expired/not-yet-valid metadata is rejected.

## Recovery and installation

Partial downloads are retained under the signed SHA-256 in the cache. Retrying
uses HTTP Range. A server that ignores Range causes a clean restart; an invalid
Content-Range is rejected. Every asset is checked against signed size and SHA-256.
Checksum failures remove only the failed installer-owned partial download.
TLS certificate verification stays enabled, including in local HTTPS tests.

All assets finish verification before staging. Staging occurs beside the final
version and is renamed after extraction and entry-point checks. Failed downloads
do not delete or edit existing installations. Failed staging removes only the
newly created temporary stage. File locking prevents simultaneous writes through
the same installation flow/cache. No package code or postinstall script runs.

The graphical bootstrap displays component progress in MiB and percent, supports
cancellation, and explains disabled production downloads. CLI mode emits JSON
progress (`python -m installer.bootstrap --cli`). A packaged preview is unsigned;
signed release metadata does not mean the Windows installer has Authenticode.

## Local checks and build

From the existing Source directory, using the separate installer development
environment with `requirements-build.txt` installed:

```text
python -m unittest installer.test_releases -v
python -m installer.bootstrap --cli
```

The second command must exit nonzero without contacting the production endpoint
while disabled. Tests create short-lived TLS certificates, Ed25519 keys and dummy
packages. They neither download real models nor certify the production release.

Build a preview from Source:

```text
python -m PyInstaller --noconfirm --onefile --windowed --name YOEAI-3.0-Setup-Preview --add-data "installer/release-config.json;installer" installer_entry.py
```

Remaining release work includes the actual signed payload, offline installer,
user-data upgrade and rollback flow, license acceptance, Windows uninstall
registration, Authenticode/signing decisions and clean-PC qualification. No
YOEAI 3.0 production download or complete installation is claimed by these tests.
