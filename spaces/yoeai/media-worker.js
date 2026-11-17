// No hosted inference endpoint: model downloads and inference run in this worker.
import { pipeline, env } from 'https://cdn.jsdelivr.net/npm/@huggingface/transformers@4.3.2';
env.allowLocalModels = false;
env.backends.onnx.wasm.numThreads = 1;
self.onmessage = async ({data}) => {
  let model;
  try {
    const progress_callback = info => self.postMessage({type:'progress',text:info.status+(info.progress ? ' '+Math.round(info.progress)+'%' : '')});
    if(data.kind === 'caption') {
      model = await pipeline('image-to-text','Xenova/vit-gpt2-image-captioning',{device:'wasm',dtype:'q8',progress_callback});
      const result = await model(data.image,{max_new_tokens:60});
      self.postMessage({type:'result',text:result[0].generated_text});
    } else if(data.kind === 'transcribe') {
      model = await pipeline('automatic-speech-recognition','Xenova/whisper-tiny',{device:'wasm',dtype:'q8',progress_callback});
      const result = await model(data.audio,{language:data.language,task:'transcribe',chunk_length_s:30,stride_length_s:5});
      self.postMessage({type:'result',text:result.text});
    } else throw Error('Unsupported media task.');
  } catch(error) { self.postMessage({type:'error',text:error.message||String(error)}); }
  finally { if(model) await model.dispose(); }
};
