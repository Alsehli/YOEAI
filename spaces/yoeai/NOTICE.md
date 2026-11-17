# Libraries and model sources

This is YOEAI's free web companion, GPL-3.0-only (LICENSE). It is a static app, not the Windows installer. No paid inference API or secret is included.

Libraries are downloaded only when their feature is opened:

- WebLLM **0.2.88**, Apache-2.0: https://github.com/mlc-ai/web-llm — https://webllm.mlc.ai/docs/user/get_started.html
- Transformers.js **4.3.2**, Apache-2.0: https://github.com/huggingface/transformers.js — https://huggingface.co/docs/transformers.js
- PDF.js **6.5.438**, Apache-2.0: https://github.com/mozilla/pdf.js

Browser model sources (weights downloaded on explicit use, not redistributed here):

- Qwen2.5 0.5B/1.5B Instruct, Apache-2.0; WebLLM MLC quantizations: https://huggingface.co/mlc-ai — upstream https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct and https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct
- Whisper tiny, MIT: https://huggingface.co/Xenova/whisper-tiny — upstream https://github.com/openai/whisper
- Image captions: https://huggingface.co/Xenova/vit-gpt2-image-captioning — upstream https://huggingface.co/nlpconnect/vit-gpt2-image-captioning (consult its model card/terms). Captions can be inaccurate.

External community tools, independently operated and subject to their own licenses, terms and free quotas:

- Black Forest Labs FLUX.1-schnell: https://huggingface.co/spaces/black-forest-labs/FLUX.1-schnell

The app clearly labels external execution and does not forward chat, attachments or stored history into those tools. Inputs the visitor enters directly into an embedded tool are processed by that service. Availability and quota cannot be guaranteed by YOEAI.

Free hosting documentation: https://huggingface.co/docs/hub/spaces-sdks-static . ZeroGPU eligibility/limits: https://huggingface.co/docs/hub/spaces-zerogpu . No paid subscription or hardware allocation is requested by this app.
