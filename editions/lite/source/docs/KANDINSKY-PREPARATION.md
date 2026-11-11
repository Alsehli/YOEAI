# Kandinsky 6.0 Lite Distill — preparation only

10 November 2026. No unit/integration/smoke tests, inference, sample video/audio,
GPU benchmark, app startup, installer execution or installation validation was
performed for this change. Executables are packaging outputs only; producing
them is not evidence that they run. The running installed RC3 app is unchanged.

## Provenance and assets

Official source: https://github.com/kandinskylab/kandinsky-6 at
`73b892b730885e02ab58fbf7fc5cb10b78e1e3da`.
Only the official Lite Distill five-second model snapshot was downloaded:
https://huggingface.co/kandinskylab/Kandinsky-6.0-Lite-distill-5s-Diffusers/tree/4c487e8b4aeeb9059e5a77905aa2ddb59ec28f81 .
No Pro checkpoint or super-resolution weights were downloaded.

The 36 selected files total **26,670,725,000 bytes**. They include the 6,381,599,096
byte diffusion transformer, five Qwen text-encoder shards, the second CLIP text
encoder, video VAE, audio VAE, vocoder, tokenizers, configs and model cards.
`VideoGeneration/Kandinsky/model-assets.json` records every path, byte count,
download URL, local SHA-256, published LFS SHA-256 and Git blob ID. All published
LFS hashes matched. Small Git files were matched against their pinned Git blobs.
File hashing is integrity preparation, not model execution or a functional test.

Assets live under workspace `VideoGeneration/Kandinsky`. Python 3.13.18 Windows
x64 is isolated there, with CUDA 13.0 PyTorch 2.14.1+cu130, torchvision
0.29.1+cu130 and the installed upstream dependency closure. The inventory is
`dependencies.json`; `requirements-lock.txt` pins all versions and immutable
source commits. Important packages include diffusers, transformers, accelerate,
bitsandbytes, safetensors, PyAV, librosa and the upstream SR support package
(needed by the config schema, without downloading SR weights). Python package
imports were not probed. Installation success is not GPU compatibility evidence.

MIT notices, the upstream/model cards, Qwen Apache-2.0 attribution, CLIP MIT
notice, FFmpeg license/build information and Python distribution notices are
retained under `Kandinsky/Licenses`. The model card's MIT label does not replace
the distinct licenses of encoders and dependencies. Redistribution review is
still necessary before a production release.

## Integration

`kandinsky_video.py` implements the existing asynchronous job contract.
`lite_video_generation.py` preserves `/videogen/create`, `/status`, `/stop`,
`/models`, `/license`, `/output/<id>` and `/poster/<id>`. The old native
Hunyuan/text-to-image-to-video implementation was replaced in this source file;
no silent backend fallback remains. Historical user outputs are still served.

`kandinsky_worker.py` uses the public official pipeline/config API. It explicitly
layers `lite-distill` after the device preset, since upstream device presets
default to Pro. Every weight path is rebound to the pinned local snapshot. Hub
and Transformers offline flags are set before AI imports. Missing components
fail rather than downloading a model or calling a cloud service.

Prepared generation uses the official 10-step PiFlow settings, guidance 1.0,
scheduler shift 5.0, 864×480, 121 model frames and 24 fps. Text-to-video generates
directly; image-to-video uses `tail_cond_first_frame`. The synchronized audio
stream is required, not discarded. The MP4 export path trims/muxes five seconds
with H.264/AAC and makes a poster. This code was not executed.

The chat UI retains natural video intent routing, attachment input, playback,
progress, Stop, regeneration and MP4 saving. Generated-image cards now offer
Animate image. The video length control is five seconds only. Progress is
prepared from worker phase events and official denoising step logs.

## Resource policy and activation gate

`VideoGeneration/config.json` selects `kandinsky6-lite-distill` as primary and
sets `testingAuthorized: false`, `preparedOnly: true`, `verified: false`.
The service and worker both guard execution. Do not flip this flag without
explicit authorization to test. Nothing was activated in the user's installed
application, and no new app instance was launched.

At a future authorized request the host takes the existing image/chat gate and
shared image-generation lock, pauses the chat model, then selects one eligible
NVIDIA GPU using free/total memory and optional `gpuIndex`. GPU UUID binding
isolates one device. Separate VRAM pools are never added together.

The 24 GB policy uses BF16 and module CPU offload, with SDPA attention. It draws
on upstream's 24 GB preset but is not a verified RTX 3090 profile. The 16 GB
policy uses the official NF4 Qwen option, release-after-encode and module
offload. SDPA is supported in the official code; SageAttention/FlashAttention
were deliberately not assumed available on Windows. Driver compatibility,
Blackwell bitsandbytes kernels, actual memory peaks, speed and quality on either
requested GPU remain unknown until authorized testing. Adequate CPU RAM and a
CUDA-13-compatible driver are prerequisites whose sufficiency was not measured.

Weights load only in a dedicated subprocess. Cancellation terminates/waits for
that worker; exit releases its CUDA context. Normal completion also drops the
pipeline and empties PyTorch's cache before process exit. Chat restoration
occurs afterward. Existing completed videos, conversations and model weights
are not removed by the new job flow. These lifecycle paths need future testing.

## Packaging and downloads

`installer/prepare_kandinsky_release.py` stages the existing Lite foundation with
the freshly packaged app, current source, baseline models/runtimes, voice and
speech-input assets, plus Kandinsky. Legacy video weights are excluded from the
new payload but preserved on disk. Immutable model files may use NTFS hard links
in local staging; runtime/code files are copied. Copying the prepared payload to
another drive must preserve its complete contents. Windows extended paths are
used for deep dependency/license paths without changing OS settings.

The online contract remains configurable at
https://downloads.yoeai.online/3.0/stable/manifest.json . It remains unpublished,
disabled and without a production signing key. Local metadata contains real
asset sizes and SHA-256 values, pinned official model URLs, and planned HTTPS
package URLs. Planned YOEAI URLs are not evidence that files are hosted there.
The local manifest is **unsigned preparation metadata** and is intentionally
rejected as an installable production release. No private signing key was made.

Online/offline installers share the Ed25519/HTTPS/hash/version contract. The
offline transport reads only signed local assets. Both install controls remain
disabled. Resume, progress, conservative cache+staging disk budgets, signed
archive extraction limits and preservation of existing installs on download
failure are implemented but were not tested in this turn. Different signed
archives may share the app root; duplicate extracted files still fail safely.

Actual runtime, expanded payload and artifact byte counts are emitted into the
prepared release's `preparation.json`. Model bytes alone are not the complete
install requirement. Temporary download cache, extraction/staging and existing
retained legacy weights also consume disk space.

## Controlled retirement and future work

Source checkpoint: tag `pre-kandinsky-20261110` at `1c43337` in `Lite/Source`.
Outer packaging/config checkpoint: `e12ccd5` in the workspace root repository.
The old Hunyuan config and four obsolete video preparation/report scripts are
removed through Git after their active callers were replaced. Their contents
are recoverable from history. Old Hunyuan/Wan weights, binaries, historical
reports/benchmarks and user-generated videos remain untouched pending validation.

Future explicit authorization is required before any tests, app/installer
execution, model load or generated sample. Required checks include syntax and
dependency compatibility; CUDA/driver/NF4/SDPA on RTX 3090 and RTX 5060 Ti; peak
RAM/VRAM and restoration; T2AV/I2AV audio synchronization and five-second MP4;
cancellation/timeouts/error recovery; generated-image selection; old video
playback; offline startup; signed/unsigned/expired release handling; resumable
downloads; long paths; upgrade preservation and Windows install/uninstall.
Only after validation should old model/runtime binaries be irreversibly removed.
