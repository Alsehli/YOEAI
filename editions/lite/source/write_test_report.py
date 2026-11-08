import json
from pathlib import Path
ROOT=Path(__file__).parents[2];P=ROOT/'YOEAI-Lite';results=json.loads((ROOT/'lite-development/functional-results.json').read_text(encoding='utf8'));stream=next(x['evidence'] for x in results if x['test']=='Streaming');state=json.loads((ROOT/'lite-development/engine-test-state.json').read_text())
rows='\n'.join('| '+x['test']+' | '+x['status']+' | Actual Q4_K_M request test on this PC. |' for x in results)
text=f'''# YOEAI Lite - test and release report

Date: 13 October 2026, Bahrain. Edition: text and image. Release status: **BLOCKED for public sale** pending actual 8 GB clean-PC validation, trusted signing and final native redistribution review. This is a complete offline development package, not a cleared release candidate.

## Test environment

RTX 5060 Ti 16 GB, Intel i5-10400, 64 GB RAM, NVIDIA driver 616.92. Existing Q6_K Alsehli AI remained running. To avoid GPU-memory contention, Lite used **18 GPU layers**, CPU vision projector, 2,048 context, batch 256, microbatch 128, Flash Attention and q8 KV cache. The intended clean-PC profile uses GPU layers 99 with the CPU projector. That full-offload profile has not been validated on an 8 GB card.

| Check | Result | Evidence |
|---|---|---|
{rows}
| GUI and branding | PASS | Lite heading, Q4_K_M, 2,048 context, model Ready, image attachment and measured token-speed field verified. |
| Model integrity | PASS | Q4_K_M 5,780,092,000 bytes; SHA-256 afa0567da6353443c40b2560c20f52ed743a7a105dedf288fb26be00fb78e176. |
| Vision projector | PASS | Reused mmproj-F32 1,824,061,952 bytes; actual image request recognized test code 7429 and red shape. |
| Original app preservation | PASS | Original server-state JSON remained identical before/after inference tests; original service stayed healthy. |
| Voice exclusion | PASS | No speech code/models or Piper/Qt dependency imported by Lite. Voice remains in the separate personal app. |
| Reopen behavior | Development fix; validation pending | Source reuses its own running UI rather than binding a second server. |
| Graceful engine/UI shutdown and restart | BLOCKED pending confirmation | Automatic approval review blocked this test. Owner was asked to approve only Lite services; original services are excluded. |
| Offline installer on clean PC | BLOCKED | The complete offline payload is prepared, but no second-PC installation was run from this session. |
| 8 GB GPU memory/stability | BLOCKED | This PC has 16 GB. Partial GPU tests cannot certify the target GPU or driver. |
| Code signing | BLOCKED | Owned EXE is NotSigned; no trusted signing credential supplied. |
| Native distribution compliance | Review required | Python/Tcl/Tk/OpenSSL/PyInstaller/model/backend notices included; CUDA/MSVC/version review remains. |

## Measured performance - limited test profile

- Engine load: {state['loadSeconds']:.2f} seconds.
- Streaming generation: {stream['timings']['predicted_per_second']:.2f} tokens/s for {stream['timings']['predicted_n']} generated tokens.
- First-token latency: {stream['firstTokenSeconds']:.3f} seconds.
- Prompt processing: {stream['timings']['prompt_per_second']:.2f} tokens/s for {stream['timings']['prompt_n']} prompt tokens.
- GUI marker test displayed 9.8 tokens/s; total device memory about 12.9/15.9 GiB including the separate original model. This is not Lite-only VRAM usage or an 8 GB benchmark.

Do not use these partial-offload speeds as guaranteed customer performance. CPU generation is slower here because the original app was preserved and remained on the GPU. No 4,096 context, memory-limit emulation, prolonged soak, fresh installer, disconnected cold-start or all-hardware tests were claimed. AI output and OCR can be incorrect; privacy is not a guarantee against all software/security risks.

## Package contents and review

Application EXE, installer/start/stop scripts, Q4_K_M, projector, official CUDA runtime archives, quick-start guide, support guidance, draft sales copy, source/build instructions, notices and checksum manifest are included. All files must stay together for offline setup. No second CUDA toolkit or duplicate backend installation was made on this PC. Runtime/projector staging files use local hardlinks to existing verified assets; copying the complete folder to another drive copies their contents.

The old temporary Lite test host was preserved after an automatic approval rejection. It is unrelated to the original application. Do not call this package sale-ready until blocked tests and signing are completed. No website or PayPal product changes were published.
'''
(P/'Documents/TEST-REPORT.md').write_text(text,encoding='utf8')
(P/'Documents/FUNCTIONAL-RESULTS.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
print('Lite test report written')
