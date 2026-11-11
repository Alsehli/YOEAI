"""On-demand official Kandinsky Lite Distill worker. Do not execute during preparation."""
import argparse
import gc
import json
import os
import sys
from pathlib import Path


def event(stage, message):
    print('KANDINSKY_EVENT ' + json.dumps({'stage': stage, 'message': message}), flush=True)


def main(request_path):
    request_path = Path(request_path).resolve()
    request = json.loads(request_path.read_text(encoding='utf8'))
    if request.get('executionAuthorized') is not True:
        raise RuntimeError('Kandinsky is preparation-only. Explicit testing authorization is required.')
    if request.get('variant') != 'lite-distill' or request.get('seconds') != 5:
        raise ValueError('Only official Lite Distill five-second generation is configured.')
    root = Path(request['backendRoot']).resolve()
    weights = root / 'Models'
    source = root / 'Source'
    # Offline-only before importing any AI library. Paths below are all local.
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1', TOKENIZERS_PARALLELISM='false')
    sys.path.insert(0, str(source))
    import yaml
    import torch
    from kandinsky import get_pipeline
    from kandinsky.pipeline.config import load_config

    if not torch.cuda.is_available():
        raise RuntimeError('The prepared CUDA runtime cannot use the selected GPU.')
    torch.cuda.set_device(0)  # Parent binds exactly one physical GPU by UUID.
    small = request.get('quantizedQwen', request['memoryProfile'] == '16gb')
    device_preset = 'rtx-5060-ti' if request['memoryProfile'] == '16gb' else 'rtx-4090'
    # The device presets default to Pro: Lite Distill MUST be layered last.
    cfg = load_config([device_preset, 'lite-distill'])
    cfg = cfg.model_copy(update={
        'checkpoint': 'lite-distill',
        'paths': cfg.paths.model_copy(update={
            'dit': str(weights / 'transformer/diffusion_pytorch_model.safetensors'),
            'vae': str(weights / 'vae'), 'qwen': str(weights / 'text_encoder'),
            'clip': str(weights / 'text_encoder_2'), 'dit_export': None,
        }),
        'audio_vae': cfg.audio_vae.model_copy(update={'tod_vae_ckpt': str(weights / 'audio_vae')}),
        'vocoder': cfg.vocoder.model_copy(update={'ckpt': str(weights / 'vocoder')}),
        'offload': cfg.offload.model_copy(update={'strategy': 'module', 'pin_memory': request.get('pinMemory', False)}),
        'attention': cfg.attention.model_copy(update={'engine': 'sdpa'}),
        'compile': cfg.compile.model_copy(update={'strategy': 'none'}),
        'cache': cfg.cache.model_copy(update={'mode': 'none'}),
        'beautifier': cfg.beautifier.model_copy(update={'name': 'none'}),
        'text_embedder': cfg.text_embedder.model_copy(update={'quantized_qwen': small, 'release_after_encode': small}),
    })
    resolved = request_path.with_suffix('.resolved.yaml')
    resolved.write_text(yaml.safe_dump(cfg.model_dump(mode='json'), sort_keys=False), encoding='utf8')
    output = Path(request['output']).resolve()
    if output.parent != request_path.parent:
        raise ValueError('Output must stay in the assistant-owned job directory.')
    pipe = None
    try:
        event('loading', 'Loading Kandinsky 6.0 Lite Distill locally…')
        pipe = get_pipeline(resolved, device='cuda:0', attention_engine='sdpa', offload_strategy='module')
        # The upstream free-memory heuristic chooses full spatial tiles on a
        # 24GB WDDM device; convolution workspace can then spill into shared RAM.
        # Keep the official temporal/spatial tiling implementation, with bounded
        # spatial tiles and overlap instead of changing model precision/output.
        optimal_tiling = pipe.vae.get_enc_optimal_tiling
        def bounded_tiling(shape, device=None):
            tile, stride = optimal_tiling(shape, device=device)
            height, width = min(tile[2], 256), min(tile[3], 256)
            return (tile[0], tile[1], height, width), (stride[0], min(stride[1], 192 if height < tile[2] else height), min(stride[2], 192 if width < tile[3] else width))
        pipe.vae.get_enc_optimal_tiling = bounded_tiling
        decode = pipe.vae.decode
        def decode_with_progress(*args, **kwargs):
            event('decoding', 'Decoding video frames and synchronized audio…')
            return decode(*args, **kwargs)
        pipe.vae.decode = decode_with_progress
        event('generating', 'Generating video and synchronized audio locally…')
        result = pipe(
            text=request['prompt'], image=request.get('image'),
            visual_cond_scheme='tail_cond_first_frame' if request.get('image') else None,
            height=480, width=864, time_length=5,
            num_steps=10, guidance_weight=1.0, scheduler_scale=5.0,
            seed=request['seed'], sample_audio=True, show_progress=True, save_path=output,
        )
        if result.audio is None:
            raise RuntimeError('Kandinsky returned no synchronized audio track.')
        if not output.is_file():
            raise RuntimeError('Kandinsky returned no MP4 output.')
        event('exported', 'Video and audio exported; releasing the video model…')
    finally:
        if pipe is not None:
            del pipe
        gc.collect()
        torch.cuda.empty_cache()
        # Process exit releases the entire isolated CUDA context as well.


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', required=True, type=Path)
    args = parser.parse_args()
    main(args.request)
