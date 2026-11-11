# YOEAI 3.0 development source (Lite foundation)

This directory now contains the 11 November 2026 development source from the existing Lite application. The Normal source at the repository root is preserved separately. The 8 November Image Turbo notes describe the prior released source, not this new revision.

Current changes include automatic web research in normal chat, automatic matching bundled vision routing, linked GGUF model discovery, native-worker reuse during model changes, Quick/Long context presets, staged loading with elapsed time, separate normal-image/2D/3D views and blank composer inputs. See [release scope and verification](../../docs/RELEASE-20261111-YOEAI-3.md).

The source does not include models, CUDA/native libraries, SearXNG runtime assets, speech/media runtimes, private profiles or local conversation logs. Supply those separately under their original licenses. Production manifest downloads remain disabled. Do not treat model-file detection as compatibility validation or preparation code as tested generation.

`source/BUILD.md` and `source/docs/KANDINSKY-PREPARATION.md` explain preparation constraints. Existing source build helpers and the historical `Installer-Image-20261108` snapshot are retained for reference. The complete 3.0 offline/online distributions still require external runtime staging, signed metadata, hosting and installer qualification; this update does not publish new installer binaries or certify a fresh-PC build.

`SOURCE-INVENTORY.json` records SHA-256 hashes of the current public source bytes. Machine-specific launcher/deployment helpers and raw installed-machine logs are excluded. Local usernames in retained development notes are generalized. Preserve the GPL license and third-party notices.
