import {HISTORY_KEY,attachmentText,buildMessages,usageLabel,restoreHistory} from './core.js';
const $=id=>document.getElementById(id);
let engine=null,chatWorker=null,busy=false,attaching=false,history=[],attachments=[],stopping=false,generating=false;
const mediaJobs=new Map();
const error=message=>{$('error').textContent=String(message);$('error').hidden=false;};
$('error').onclick=()=>{$('error').hidden=true;};
function controls(){
 $('load').disabled=busy||!!engine;$('unload').disabled=busy||!engine;$('model').disabled=busy||!!engine;
 $('send').disabled=busy||attaching||!engine;$('stop').disabled=!generating||!engine;$('clear').disabled=busy;
}
function status(text){$('model-status').textContent=text;}
function persist(){try{if($('remember').checked)localStorage.setItem(HISTORY_KEY,JSON.stringify(history.slice(-80)));else localStorage.removeItem(HISTORY_KEY);}catch{error('Browser storage is unavailable. This conversation remains in memory.');}}
function bubble(role,text){
 const box=document.createElement('div');box.className='message '+role;
 const label=document.createElement('div');label.className='label';label.textContent=role==='user'?'You':'YOEAI';
 const body=document.createElement('div');body.className='body';body.textContent=text;box.append(label,body);
 if(role==='assistant'){const read=document.createElement('button');read.textContent='Read aloud';read.onclick=()=>{$('read-text').value=body.textContent.slice(0,6000);speak();};box.append(read);}
 $('chat-log').append(box);$('chat-log').scrollTop=$('chat-log').scrollHeight;return body;
}
try{const saved=localStorage.getItem(HISTORY_KEY);if(saved){history=restoreHistory(saved);$('remember').checked=true;$('chat-log').replaceChildren();history.forEach(x=>bubble(x.role,x.content));}}catch{error('Saved history could not be read. Clear chat to remove this app’s saved entry.');}
$('remember').onchange=persist;
$('clear').onclick=()=>{if(busy)return;history=[];attachments=[];$('chat-log').replaceChildren();chips();persist();$('usage').textContent='Conversation cleared.';};
document.querySelectorAll('[data-prompt]').forEach(button=>button.onclick=()=>{$('prompt').value=button.dataset.prompt;$('prompt').focus();});
function tab(name){
 document.querySelectorAll('.panel').forEach(x=>x.hidden=x.id!==name);
 document.querySelectorAll('[data-tab]').forEach(x=>x.classList.toggle('selected',x.dataset.tab===name));
 $('section-name').textContent=({chat:'Conversation',images:'Create image',voice:'Voice studio',about:'About & privacy'})[name];
}
document.querySelectorAll('[data-tab]').forEach(x=>x.onclick=()=>tab(x.dataset.tab));
$('load').onclick=async()=>{
 if(busy||engine)return;busy=true;controls();status('Checking your browser GPU…');
 try{
  if(!navigator.gpu)throw Error('WebGPU is unavailable. Open this Space in a current Chrome or Edge browser on a compatible device. No simulated answer was generated.');
  const adapter=await navigator.gpu.requestAdapter();if(!adapter)throw Error('No usable browser GPU was found. Check browser hardware acceleration.');
  let model=$('model').value;
  if(!adapter.features.has('shader-f16')){if(model.includes('0.5B'))model=model.replace('q4f16','q4f32');else throw Error('This GPU lacks shader-f16. Select the Fast model instead.');}
  const webllm=await import('https://esm.run/@mlc-ai/web-llm@0.2.88');
  chatWorker=new Worker(new URL('./chat-worker.js',import.meta.url),{type:'module'});
  engine=await webllm.CreateWebWorkerMLCEngine(chatWorker,model,{initProgressCallback:info=>status(info.text)},{context_window_size:4096});
  status('Model loaded on this device. Ready to chat.');
 }catch(e){engine=null;chatWorker?.terminate();chatWorker=null;status('Model is not loaded.');error(e.message);}
 finally{busy=false;controls();}
};
async function unload(){
 if(busy)throw Error('Stop or finish the current model task first.');
 busy=true;controls();status('Unloading model…');
 try{if(engine)await engine.unload();}finally{engine=null;chatWorker?.terminate();chatWorker=null;busy=false;status('Model unloaded. Browser cache may retain downloaded weights.');controls();}
}
$('unload').onclick=()=>unload().catch(e=>error(e.message));
$('stop').onclick=()=>{if(engine&&generating){stopping=true;engine.interruptGenerate();status('Stopping the reply…');}};
$('composer').onsubmit=async event=>{
 event.preventDefault();if(busy||attaching)return;if(!engine){error('Load a chat model first.');return;}
 const prompt=$('prompt').value.trim();if(!prompt)return;
 let messages;try{messages=buildMessages(history,prompt,attachments);}catch(e){error(e.message);return;}
 busy=true;generating=true;stopping=false;controls();$('error').hidden=true;
 if(!history.length)$('chat-log').replaceChildren();bubble('user',prompt+(attachments.length?'\n[Attachments: '+attachments.map(x=>x.name).join(', ')+']':''));
 const body=bubble('assistant','');let answer='',usage;const started=performance.now();
 try{
  const stream=await engine.chat.completions.create({messages,temperature:.5,max_tokens:512,stream:true,stream_options:{include_usage:true}});
  for await(const chunk of stream){answer+=chunk.choices?.[0]?.delta?.content||'';if(chunk.usage)usage=chunk.usage;body.textContent=answer;$('chat-log').scrollTop=$('chat-log').scrollHeight;}
  if(!answer.trim())throw Error(stopping?'Reply stopped before text was generated.':'The model returned no answer. Try a shorter request.');
  history.push({role:'user',content:prompt},{role:'assistant',content:answer});persist();$('prompt').value='';
  $('usage').textContent=usageLabel(usage,(performance.now()-started)/1000)+(stopping?' · stopped':'');status('Model loaded. Ready.');
 }catch(e){body.textContent=answer||'No answer was generated.';error(e.message);status('Model is loaded; the last request failed. You can retry or unload.');}
 finally{busy=false;generating=false;stopping=false;controls();}
};
$('prompt').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();$('composer').requestSubmit();}};
function chips(){
 $('attachments').replaceChildren();attachments.forEach((item,index)=>{const box=document.createElement('span');box.className='chip';box.textContent=item.name+(item.excerpt?' · excerpt':'');const remove=document.createElement('button');remove.type='button';remove.textContent='×';remove.setAttribute('aria-label','Remove '+item.name);remove.onclick=()=>{attachments.splice(index,1);chips();};box.append(remove);$('attachments').append(box);});
}
function media(kind,payload,progress){
 if(mediaJobs.has(kind))return Promise.reject(Error('Wait for the current '+kind+' task.'));
 return new Promise((resolve,reject)=>{
  const worker=new Worker(new URL('./media-worker.js',import.meta.url),{type:'module'});
  const finish=(failure,text)=>{worker.terminate();mediaJobs.delete(kind);failure?reject(Error(text)):resolve(text);};
  mediaJobs.set(kind,{cancel:()=>finish(true,'Media task cancelled.')});
  worker.onmessage=({data})=>{if(data.type==='progress')progress(data.text);else finish(data.type==='error',data.text);};
  worker.onerror=e=>finish(true,e.message||'The browser media worker failed.');
  worker.postMessage({kind,...payload});
 });
}
async function imageData(file){
 const image=await createImageBitmap(file);try{const scale=Math.min(1,768/Math.max(image.width,image.height)),canvas=document.createElement('canvas');canvas.width=Math.round(image.width*scale);canvas.height=Math.round(image.height*scale);canvas.getContext('2d').drawImage(image,0,0,canvas.width,canvas.height);return canvas.toDataURL('image/jpeg',.85);}finally{image.close();}
}
$('files').onchange=async()=>{
 if(attaching||busy){error('Finish the current task before attaching files.');$('files').value='';return;}
 attaching=true;controls();
 try{
  for(const file of $('files').files){
   if(attachments.length>=4)throw Error('Use up to four attachments. Remove one to add another.');
   if(file.size>10*1024*1024)throw Error(file.name+': choose a file under 10 MB.');
   let text='',truncated=false;
   if(['image/png','image/jpeg','image/webp'].includes(file.type)){status('Describing image locally; first use downloads a caption model…');text='LIMITED IMAGE CAPTION: '+await media('caption',{image:await imageData(file)},status);}
   else if(/\.pdf$/i.test(file.name)){
    status('Reading PDF locally…');const pdf=await import('https://cdn.jsdelivr.net/npm/pdfjs-dist@6.5.438/build/pdf.mjs');pdf.GlobalWorkerOptions.workerSrc='https://cdn.jsdelivr.net/npm/pdfjs-dist@6.5.438/build/pdf.worker.mjs';
    const doc=await pdf.getDocument({data:new Uint8Array(await file.arrayBuffer()),isEvalSupported:false}).promise;
    try{let page=1;for(;page<=Math.min(doc.numPages,20)&&text.length<=4000;page++){const content=await(await doc.getPage(page)).getTextContent();text+='\n[Page '+page+'] '+content.items.map(x=>x.str||'').join(' ');}truncated=page<=doc.numPages||text.length>4000;}finally{await doc.destroy();}
   }else if(/\.(txt|md|csv|json|py|js|ts|html|css)$/i.test(file.name)){text=await file.text();}
   else throw Error('Unsupported file: '+file.name+'. Use text, PDF, PNG, JPEG or WebP.');
   attachments.push(attachmentText(file.name,text,truncated));chips();
  }
 }catch(e){error(e.message);}finally{attaching=false;$('files').value='';status(attachments.length?(engine?'Model loaded. Attachments ready.':'Attachments ready. Load a chat model to ask about them.'):(engine?'Model loaded. Ready.':'Load a model to begin.'));controls();}
};
async function creative(){
 if(busy||attaching)throw Error('Finish or stop the current chat/attachment task first.');
 if(engine)await unload();
 const host=$('images-host');if(host.childNodes.length)return;
 const frame=document.createElement('iframe');frame.title='Free FLUX.1-schnell community image tool';
 frame.referrerPolicy='no-referrer';frame.src='https://black-forest-labs-flux-1-schnell.hf.space/?__theme=dark';
 frame.allow='clipboard-write; fullscreen';frame.loading='eager';host.append(frame);
}
$('open-images').onclick=()=>creative().catch(e=>error(e.message));
let recorder=null,recordingStream=null,recordingTimer;
async function transcribe(file){
 try{
  if(file.size>20*1024*1024)throw Error('Choose audio under 20 MB.');$('voice-status').textContent='Decoding audio locally…';
  const audioContext=new AudioContext();let audio;
  try{audio=await audioContext.decodeAudioData(await file.arrayBuffer());}finally{await audioContext.close();}
  if(audio.duration>60.5)throw Error('Use audio up to 60 seconds.');
  const offline=new OfflineAudioContext(1,Math.ceil(audio.duration*16000),16000),source=offline.createBufferSource();source.buffer=audio;source.connect(offline.destination);source.start();
  const decoded=await offline.startRendering();$('voice-status').textContent='Loading Whisper tiny…';
  const result=await media('transcribe',{audio:decoded.getChannelData(0),language:$('language').value},text=>$('voice-status').textContent=text);
  $('transcript').value=result;$('voice-status').textContent='Transcribed locally. Review before using in conversation.';
 }catch(e){$('voice-status').textContent=e.message;error(e.message);}
}
$('audio').onchange=()=>{const file=$('audio').files[0];if(file)transcribe(file);$('audio').value='';};
function releaseMic(){clearTimeout(recordingTimer);recordingStream?.getTracks().forEach(x=>x.stop());recordingStream=null;$('record').disabled=false;$('end-record').disabled=true;}
$('record').onclick=async()=>{
 try{
  if(!navigator.mediaDevices?.getUserMedia||!window.MediaRecorder)throw Error('Recording is unavailable in this browser. Upload an audio file instead.');
  if(recorder?.state==='recording'||mediaJobs.has('transcribe'))throw Error('Finish the current recording/transcription first.');
  recordingStream=await navigator.mediaDevices.getUserMedia({audio:true});recorder=new MediaRecorder(recordingStream);const chunks=[];
  recorder.ondataavailable=e=>{if(e.data.size)chunks.push(e.data);};recorder.onerror=()=>{releaseMic();error('Recording failed.');};
  recorder.onstop=()=>{releaseMic();transcribe(new Blob(chunks,{type:recorder.mimeType}));};
  recorder.start();$('record').disabled=true;$('end-record').disabled=false;$('voice-status').textContent='Recording locally… stops after 60 seconds.';recordingTimer=setTimeout(()=>{if(recorder.state==='recording')recorder.stop();},60000);
 }catch(e){releaseMic();error(e.message);}
};
$('end-record').onclick=()=>{if(recorder?.state==='recording')recorder.stop();};
$('cancel-audio').onclick=()=>{mediaJobs.get('transcribe')?.cancel();$('voice-status').textContent='Transcription cancelled.';};
$('use-transcript').onclick=()=>{$('prompt').value=$('transcript').value.slice(0,8000);tab('chat');$('prompt').focus();};
let voices=[];
function voiceList(){voices=window.speechSynthesis?.getVoices().filter(x=>x.localService)||[];$('voice-select').replaceChildren();voices.forEach((voice,index)=>{const option=document.createElement('option');option.value=String(index);option.textContent=voice.name+' · '+voice.lang;$('voice-select').append(option);});$('tts-status').textContent=voices.length?'Ready. Read aloud uses a device-local voice.':'No device-local voices are available. Install a device voice through your browser/OS to use Read aloud.';}
function speak(){
 const text=$('read-text').value.trim();if(!text){error('Choose some text to read.');return;}
 if(!voices.length||!window.speechSynthesis){error('No device-local voice is available.');return;}
 speechSynthesis.cancel();const utterance=new SpeechSynthesisUtterance(text);utterance.voice=voices[Number($('voice-select').value)||0];utterance.onend=()=>$('tts-status').textContent='Finished reading.';utterance.onerror=e=>$('tts-status').textContent='Voice stopped: '+e.error;speechSynthesis.speak(utterance);$('tts-status').textContent='Reading with a device-local voice…';
}
$('speak').onclick=speak;$('silence').onclick=()=>window.speechSynthesis?.cancel();
if(window.speechSynthesis){speechSynthesis.onvoiceschanged=voiceList;voiceList();}
window.addEventListener('pagehide',()=>{releaseMic();mediaJobs.forEach(x=>x.cancel());chatWorker?.terminate();window.speechSynthesis?.cancel();});
controls();
