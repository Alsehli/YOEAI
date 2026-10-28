/* Reliable local chat transport. No model, tool permissions or history schema changes. */
(()=>{'use strict';
 async function readStream(response,onEvent,signal){
  if(!response.body)throw Error('The model returned no response stream. Please try again.');
  const reader=response.body.getReader(),decoder=new TextDecoder();let pending='',data=[],ended=false;
  function event(){if(!data.length)return;const raw=data.join('\n');data=[];if(raw.trim()==='[DONE]'){ended=true;return;}let value;try{value=JSON.parse(raw);}catch{throw Error('The model returned an unreadable response. Please try again.');}if(value.error){const error=typeof value.error==='string'?value.error:value.error.message;throw Error(String(error||'The model could not complete this response.').slice(0,500));}onEvent(value);}
  function line(value){if(value.endsWith('\r'))value=value.slice(0,-1);if(!value){event();return;}if(value.startsWith('data:')){data.push(value.slice(5).replace(/^ /,''));if(data.reduce((n,s)=>n+s.length,0)>2*1024*1024)throw Error('The response event is too large. Please try a shorter request.');}}
  try{while(!ended){if(signal?.aborted)throw new DOMException('Response stopped.','AbortError');const part=await reader.read();pending+=part.done?decoder.decode():decoder.decode(part.value,{stream:true});let index;while(!ended&&(index=pending.indexOf('\n'))>=0){line(pending.slice(0,index));pending=pending.slice(index+1);}if(pending.length>2*1024*1024)throw Error('The response event is too large. Please try a shorter request.');if(part.done){if(pending&&!ended)line(pending);if(!ended)event();break;}}}finally{try{await reader.cancel();}catch{}reader.releaseLock();}
 }
 const historyState={writable:true,issue:'',recoveryKey:null};
 function loadHistory(){let storage,raw;try{storage=localStorage;raw=storage.getItem('deepseek-chat');}catch{historyState.writable=false;historyState.issue='Saved chat storage is unavailable. New messages can be used, but cannot be saved.';return [];}
  if(!raw)return [];try{const value=JSON.parse(raw);if(!Array.isArray(value)||!value.every(m=>m&&['user','assistant'].includes(m.role)&&(typeof m.content==='string'||Array.isArray(m.content)&&m.content.every(part=>part&&(part.type==='text'&&typeof part.text==='string'||part.type==='image_url'&&typeof part.image_url?.url==='string')))))throw Error('Invalid chat history');return value;}catch{
   try{let key='deepseek-chat-recovery';const previous=storage.getItem(key);if(previous!==null&&previous!==raw)key+='-'+Date.now();storage.setItem(key,raw);historyState.recoveryKey=key;historyState.issue='Saved chat could not be opened. A recovery copy was kept on this PC; you can start a new conversation.';}
   catch{historyState.writable=false;historyState.issue='Saved chat could not be opened. Its original data is unchanged; free browser storage before saving new messages.';}
   return [];
  }
 }
 function saveHistory(history){if(!historyState.writable)throw Error(historyState.issue);try{localStorage.setItem('deepseek-chat',JSON.stringify(history));}catch{throw Error('Your conversation could not be saved. Free browser storage or export important answers before closing.');}}
 window.YoeChatReliability={readStream,loadHistory,saveHistory,historyState};
})();
