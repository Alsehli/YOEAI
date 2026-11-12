# Version-paired native build inputs

The application bindings retain the existing `llama.cpp-b11784-win-x64` ABI. Runtime staging uses [upstream release b11784](https://github.com/ggml-org/llama.cpp/releases/tag/b11784), source commit `493253fe5a5af7e800b3c92a2452b5684a99e961`, without updating the inference API or downloading model weights.

The provisioner fixes archive names, HTTPS URLs, byte sizes and SHA-256 values in source. Downloaded inputs must match both pinned size and hash before extraction. Verified cache entries are reused; invalid existing entries are preserved and rejected. HTTPS redirects must stay on upstream GitHub/content hosts. The extraction budget is bounded and only the required DLL family and LLVM notice are selected. Network servers, CLI executables, unrelated DLLs and RPC backends are excluded. Existing runtime destinations are never overwritten.

The upstream MIT license is fetched from the immutable source commit and checked against its own pinned SHA-256. Original LLVM OpenMP and NVIDIA terms/notices remain with the package. The pinned PySide6 6.12.0 build wheel supplies app-local Microsoft CRT DLLs; its carrier identity and individual binary hashes are recorded. Available distribution notices accompany the candidate payload. These component inventories do not constitute third-party legal certification or signing-provider acceptance.

The resulting runtime has an integrity manifest consumed by the existing loader, plus `input-provenance.json`. Both edition payloads record exact file hashes. A frozen native worker enumerates available backends after loading the version-paired DLLs. Its default `--probe` still fails without CUDA. The additional explicit `--probe-cpu-ok` mode is intended for GPU-less CI and succeeds only when a native device is enumerated; the report retains the actual `cuda` value, `cudaRequired` and `modelLoaded: false`.

## Locally observed evidence — 12 November 2026

The two official archives passed the committed SHA-256/size checks. A newly staged 31-file runtime passed the unrelaxed default CUDA probe on Windows with an RTX 3090 24 GB and NVIDIA driver 621.01. Actual output:

```json
{"native":true,"devices":["CUDA0","CPU"],"cuda":true,"modelLoaded":false,"transport":"none","cudaRequired":true}
```

No model was loaded or answer generated for this check. It does not establish speed, model correctness, another GPU's compatibility, a clean-PC installation, optional voice/media behavior or exact signed-installer qualification. Those release gates remain separate under issues #5, #6, #7, #8, #11 and #20.

A separate disposable CPU-only DLL fixture was also tested with the same worker source: the default probe returned exit code 1 with `cudaRequired: true`, while explicit `--probe-cpu-ok` returned exit code 0 with `cuda: false`, `devices: ["CPU"]` and `modelLoaded: false`. This confirms that the CI option does not relax the normal CUDA requirement. Frozen-worker results are recorded separately by hosted CI.

## Archive pins

| Input | Bytes | SHA-256 |
| --- | ---: | --- |
| llama-b11784-bin-win-cuda-13.4-x64.zip | 159660562 | 28cc853ad9ffbaf801d09ef7435364bdf814c9dad831ba08c1c49c194e5cb29a |
| cudart-llama-bin-win-cuda-13.4-x64.zip | 423535356 | 738f8c251ac22b70c3ae6f83a10cf222725df0395246a2cf58f32bdb85fbe668 |
| upstream MIT LICENSE | 1078 | 94f29bbed6a22c35b992c5c6ebf0e7c92f13b836b90f36f461c9cf2f0f1d010d |
