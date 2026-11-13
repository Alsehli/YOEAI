# Moving existing image runtimes

Both Lite and Normal resolve Image Turbo's `executable`, `diffusion`, `encoder` and `vae` paths beside `ImageGeneration/config.json`. Existing absolute paths remain supported. Missing assets or malformed values produce a setup error before launching a worker. Reading these settings never downloads models or creates an output folder.

Normal's optional Design engine resolves `python` and `modelDirectory` beside its own `Design/config.json`. Moving files does not bypass the existing revision/backend verification or model-manifest size checks. The resolved model directory is passed to the worker as part of the existing job.

This repairs discovery after moving a complete configured package. It does not supply missing executables or weights, grant model licenses, or establish clean-PC image/GPU qualification. Keep the original manifests/notices with existing assets and use separate output/profile directories for qualification.
