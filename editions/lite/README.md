# YOEAI Lite source

This directory contains the source corresponding to the Lite Image Turbo preview, revision 2.0.20261108.1. The application uses its existing Edge UI and native private-pipe chat worker. Image generation uses a separate fixed local stable-diffusion.cpp CLI, with the original upstream notices retained by the installer.

See [release notes and tests](../../docs/RELEASE-20261108-LITE-IMAGE.md). Git text whitespace is normalized; `SOURCE-INVENTORY.json` records both Git-source and original packaged-source hashes. The attached source archive retains the original bytes. `source/Installer-Image-20261108` contains the matching outer installer sources.

Build the application with the pinned Windows build environment and `source/build_native_setup.py` or its equivalent PyInstaller arguments. Supply the existing qualified NativeEngine/NativeRuntime, Speech, SearchRuntime and image CUDA tool files; do not substitute the Normal framework or download duplicate models. The legacy all-in-one build helper predates the new image payload: the image release additionally stages `ImageGeneration/Runtime/CUDA` and its licensing notices, and uses the outer updater in `Installer-Image-20261108`, which copies ImageGeneration into the installed app. Do not claim a source-only build includes those external runtime files automatically.

Use a new PyInstaller work directory for each source revision. The tested packaged runtime is Windows x64; portable source checks do not exercise CUDA or install applications. Do not execute developer deployment scripts against an existing installation without reviewing their paths. Image weights remain separately selected by the user.
