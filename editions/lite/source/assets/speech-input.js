/* Microphone capture is explicit; offline transcripts are reviewed before send. */
(()=>{'use strict';
 const panel=document.getElementById('input-panel'),prompt=document.getElementById('prompt');if(!panel||!prompt)return;
 const row=document.createElement('div');row.className='assistant-controls';
 const button=document.createElement('button');button.type='button';button.textContent='Dictate';
 const status=document.createElement('span');status.className='assistant-notice';status.setAttribute('role','status');
 row.append(button,status);panel.append(row);
 let stream=null,context=null,processor=null,source=null,muted=null,chunks=[],samples=0,rate=16000,recording=false,transcribing=false,timer=null,sequence=0;
 async function api(path,body){const response=await fetch('/speech-input/'+path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const value=await response.json();if(!response.ok)throw Error(value.error||'Local dictation failed.');return value;}
 function release(){clearTimeout(timer);timer=null;recording=false;if(processor){processor.disconnect();processor.onaudioprocess=null;}source?.disconnect();muted?.disconnect();stream?.getTracks().forEach(track=>track.stop());context?.close().catch(()=>{});processor=source=muted=stream=context=null;}
 function wav(){const count=Math.floor(samples*16000/rate),buffer=new ArrayBuffer(44+count*2),view=new DataView(buffer);const text=(offset,value)=>{for(let i=0;i<value.length;i++)view.setUint8(offset+i,value.charCodeAt(i));};
  text(0,'RIFF');view.setUint32(4,36+count*2,true);text(8,'WAVE');text(12,'fmt ');view.setUint32(16,16,true);view.setUint16(20,1,true);view.setUint16(22,1,true);view.setUint32(24,16000,true);view.setUint32(28,32000,true);view.setUint16(32,2,true);view.setUint16(34,16,true);text(36,'data');view.setUint32(40,count*2,true);
  const input=new Float32Array(samples);let at=0;for(const chunk of chunks){input.set(chunk,at);at+=chunk.length;}for(let i=0;i<count;i++){const start=Math.floor(i*rate/16000),end=Math.max(start+1,Math.floor((i+1)*rate/16000));let sum=0;for(let j=start;j<Math.min(end,input.length);j++)sum+=input[j];const value=Math.max(-1,Math.min(1,sum/(end-start)));view.setInt16(44+i*2,value*(value<0?32768:32767),true);}
  let binary='';const bytes=new Uint8Array(buffer);for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));return btoa(binary);
 }
 async function finish(){if(!recording)return;const id=++sequence;release();transcribing=true;button.textContent='Cancel dictation';status.textContent='Transcribing locally…';
  try{const audio=wav();chunks=[];let value=await api('create',{audio});while(value.status==='running'&&id===sequence){await new Promise(resolve=>setTimeout(resolve,500));if(id===sequence)value=await api('status');}if(id!==sequence)return;if(value.status==='error')throw Error(value.message);if(value.status==='complete'){prompt.value+=(prompt.value.trim()?' ':'')+value.text;prompt.dispatchEvent(new Event('input',{bubbles:true}));prompt.focus();status.textContent=value.text?'Review the transcript, then send.':'No speech recognized. Try again.';}else status.textContent='Dictation stopped.';
  }catch(error){if(id===sequence)status.textContent=error.message;}finally{if(id===sequence){transcribing=false;button.textContent='Dictate';}}
 }
 button.onclick=async()=>{if(recording){await finish();return;}if(transcribing){sequence++;await api('stop',{}).catch(()=>{});transcribing=false;button.textContent='Dictate';status.textContent='Dictation stopped.';return;}button.disabled=true;
  try{await api('models');stream=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true},video:false});context=new AudioContext();rate=context.sampleRate;chunks=[];samples=0;source=context.createMediaStreamSource(stream);processor=context.createScriptProcessor(4096,1,1);muted=context.createGain();muted.gain.value=0;processor.onaudioprocess=event=>{if(!recording)return;const chunk=event.inputBuffer.getChannelData(0).slice(0,Math.max(0,60*rate-samples));chunks.push(chunk);samples+=chunk.length;if(samples>=60*rate)finish();};source.connect(processor);processor.connect(muted);muted.connect(context.destination);await context.resume();recording=true;timer=setTimeout(finish,60000);button.textContent='Stop recording';status.textContent='Recording locally · up to 60 seconds';
  }catch(error){release();status.textContent=error.message;}finally{button.disabled=false;}
 };
 window.addEventListener('pagehide',()=>{release();sequence++;if(transcribing)fetch('/speech-input/stop',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}',keepalive:true}).catch(()=>{});});
})();
