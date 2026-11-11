# YOEAI 3.0 — Kandinsky preparation packaging

This source remains based on the existing Lite project. Kandinsky 6.0 Lite Distill is the configured development video backend. It has not been tested. Do not execute inference, app/installer startup checks, benchmarks or test suites without explicit authorization.

See docs/KANDINSKY-PREPARATION.md for pinned source/model revisions, dependencies, resource policies, activation guards and remaining qualification work.

Preparation order:
1. Use installer/prepare_kandinsky_assets.py with the pinned upstream metadata to download the Lite Distill snapshot and check file hashes. Never substitute a Pro checkpoint.
2. Prepare the isolated Python 3.13.18/CUDA 13.0 runtime under VideoGeneration/Kandinsky. Record dependencies using the pinned installer/kandinsky-requirements-lock.txt.
3. Produce the application and offline/online bootstrap packaging outputs without launching them. The existing root build_candidates.py Lite command packages the application; PyInstaller entry files are installer_entry.py and offline_installer_entry.py.
4. Run installer/prepare_kandinsky_release.py for filesystem-only staging and unsigned local manifest creation. Keep the complete Payload directory beside the offline preparation bootstrap.
5. Leave testingAuthorized, enabled, and offlineInstallEnabled false. No signing key or production publication is provided by this preparation workflow.

Root stage_candidates.py and finalize_lite.py now delegate to the unified preparation recipe. The old Hunyuan/Wan preparers were retired in Git. Historical weights, outputs and reports are retained pending authorized validation.

Model-file presence, package installation and successful compilation are not evidence of generation, GPU compatibility, offline installation or upgrade correctness. All such checks remain pending.
