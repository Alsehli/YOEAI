---
title: YOEAI
emoji: 🦊
colorFrom: blue
colorTo: purple
sdk: static
app_file: index.html
pinned: false
license: gpl-3.0
short_description: Free browser AI chat, files, voice and creative tools
---

# YOEAI — Your space to think

A free browser companion to [YOEAI](https://github.com/Alsehli/YOEAI). Hosted as a Static Space: no paid hardware, subscriptions, API keys or billable inference providers are configured.

- **Chat:** WebLLM runs Qwen2.5 0.5B or 1.5B on the visitor's WebGPU device. Load, stop and unload controls; actual reported token usage. Initial model downloads use Hugging Face/MLC assets and the browser cache.
- **Attachments:** text/code/CSV/JSON and PDF excerpts stay in the browser; images are described by a browser caption model. Captions are not full vision reasoning. Long files are explicitly excerpted.
- **Voice:** Whisper tiny transcribes uploaded/recorded audio in the browser. Read aloud uses available device-local browser voices. Microphone access is requested only after clicking Record.
- **Images:** opt-in embedded Black Forest Labs FLUX.1-schnell community Space.

Creative tools are **external community services**, not privately hosted YOEAI models. Inputs entered there go to those Spaces; their queues, sign-in requirements, usage limits and availability apply. YOEAI does not buy credits, bypass quotas or silently fall back to paid providers. A new free account cannot host its own ZeroGPU Space until Hugging Face's eligibility requirements are met. Browser chat requires WebGPU; unsupported devices get a clear message rather than simulated answers.

Conversations are in memory by default. Optional local history is stored only in this browser. Clear history removes YOEAI's conversation entry, not unrelated site data. Browser/model downloads and host access logs are separate from conversation storage. Do not upload sensitive documents to external creative tools.

## Local preview

Serve this directory over localhost, e.g. `python -m http.server 19127 --bind 127.0.0.1`. Open `http://127.0.0.1:19127`. Model downloads need internet. This static app has no server-side shell, filesystem tools, global chat database, desktop controls or Windows runtime.

## Attribution

YOEAI source/UI GPL-3.0-only; see LICENSE. WebLLM Apache-2.0, Transformers.js Apache-2.0, PDF.js Apache-2.0; dependencies retain their licenses. Qwen2.5 0.5B/1.5B use Apache-2.0 model licenses; Whisper MIT; the caption model's upstream terms apply. Embedded Spaces and their model licenses remain with their respective authors. See NOTICE.md for pinned libraries and sources.

Website: https://yoeai.online · GitHub: https://github.com/Alsehli/YOEAI · Contact: yoeaionline@gmail.com
