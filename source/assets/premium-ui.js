/* SPDX-License-Identifier: GPL-3.0-only */
/* Presentation only: retained message nodes, accessible controls and local clipboard. */
(() => {
 'use strict';
 const nodes=new WeakMap(),ids=new WeakMap();let sidebarKey='',follow=true,frame=0,nextId=0,lastItems=null,lastCount=0,lastTail=null,streamPass=false,dirty=false,lastPaint=0;const id=m=>{if(!ids.has(m))ids.set(m,++nextId);return ids.get(m);};
 const $=id=>document.getElementById(id);
 function snapshot(m){return [m.content,JSON.stringify([m.imageGeneration,m.videoGeneration,m.webSources,m.webPhotos,m.pdfRequested,m.pdfReady,m.pdfError,m.pdfTitle,!!window.YoeImages,!!window.YoeVideos])];}
 function same(a,b){return a&&a[0]===b[0]&&a[1]===b[1];}
 function group(m){if(!m.createdAt)return 'Earlier exchanges';const d=new Date(m.createdAt);if(!Number.isFinite(+d))return 'Earlier exchanges';const today=new Date();today.setHours(0,0,0,0);return d>=today?'Today':d>=new Date(+today-86400000)?'Yesterday':'Earlier exchanges';}
 function historyList(items,isBusy,onDelete){
  const users=items.filter(m=>m.role==='user');const key=JSON.stringify(users.map(m=>[id(m),m.createdAt]));
  if(key===sidebarKey){$('history-list').querySelectorAll('.history-delete').forEach(b=>b.disabled=isBusy);return;}
  sidebarKey=key;const list=$('history-list');list.replaceChildren();let last='';
  for(const m of users){const title=Array.isArray(m.content)?m.content.find(x=>x.type==='text')?.text:m.content;const label=group(m);if(label!==last){const h=document.createElement('h3');h.className='history-group';h.textContent=label;list.append(h);last=label;}
   const row=document.createElement('div');row.className='history-row';const b=document.createElement('button');b.className='history-item';b.textContent=title||'Image conversation';b.title=b.textContent;b.onclick=()=>{follow=false;nodes.get(m)?.el.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'start'});};
   const remove=document.createElement('button');remove.className='history-delete';remove.type='button';remove.textContent='×';remove.title='Delete this question and reply';remove.setAttribute('aria-label','Delete exchange: '+b.textContent.slice(0,100));remove.disabled=isBusy;remove.onclick=()=>onDelete(m);row.append(b,remove);list.append(row);
  }
  if(!users.length){const p=document.createElement('p');p.className='history-empty';p.textContent='Your conversation will appear here.';list.append(p);}
 }
 async function copy(message,button,state){
  const text=Array.isArray(message.content)?message.content.filter(x=>x.type==='text').map(x=>x.text).join('\n\n'):String(message.content||'');
  try{if(navigator.clipboard?.writeText)await navigator.clipboard.writeText(text);else{const field=document.createElement('textarea');field.value=text;field.style.cssText='position:fixed;opacity:0';document.body.append(field);field.select();const ok=document.execCommand('copy');field.remove();if(!ok)throw Error('Clipboard unavailable');}button.textContent='Copied';state.textContent='Response copied.';setTimeout(()=>{if(button.isConnected){button.textContent='Copy';state.textContent='';}},1800);}
  catch{state.textContent='Could not copy. Select the response and press Ctrl+C.';}
 }
 function actions(m,article,index,isBusy,retry){
  if(m.role!=='assistant'||m.imageGeneration||m.videoGeneration||!String(m.content||'').trim())return;
  const controls=document.createElement('div');controls.className='response-actions';const state=document.createElement('span');state.className='response-action-status';state.setAttribute('role','status');
  const c=document.createElement('button');c.type='button';c.textContent='Copy';c.setAttribute('aria-label','Copy response');c.onclick=()=>copy(m,c,state);
  const r=document.createElement('button');r.type='button';r.textContent='Regenerate';r.className='regenerate-response';r.setAttribute('aria-label','Regenerate response');r.title='Answer this question again using the current Net setting';r.disabled=isBusy;r.onclick=()=>retry(index);controls.append(c,r,state);article.append(controls);
 }
 function render(items,isBusy,contentNode,onDelete,retry){
  const chat=$('chat');if(!items.length){nodes.clear?.();return false;}
  const streamOnly=streamPass&&isBusy&&items===lastItems&&items.length===lastCount&&items.at(-1)===lastTail&&lastTail?.role==='assistant';
  chat.querySelector('.empty')?.remove();const keep=new Set();let index=streamOnly?items.length-1:0;
  for(const m of (streamOnly?[items.at(-1)]:items)){let record=nodes.get(m);const sig=snapshot(m);if(!record){record={el:document.createElement('article')};nodes.set(m,record);}const el=record.el;el.id='message-'+index;el.className='message '+m.role;keep.add(el);
   if(!same(record.sig,sig)){
    el.replaceChildren();const label=document.createElement('div');label.className='label';label.textContent=m.role==='user'?'YOU':'YOEAI™';el.append(label);
    if(Array.isArray(m.content)){for(const item of m.content){if(item.type==='text')el.append(contentNode(item.text,m.role==='assistant'));else if(item.type==='image_url'){const img=document.createElement('img');img.src=item.image_url.url;img.alt='Attached image';el.append(img);}}}else el.append(contentNode(m.content,m.role==='assistant'));
    if(m.role==='assistant'&&!m.imageGeneration&&!m.videoGeneration)YoePdf.card(m,el);if(m.imageGeneration&&window.YoeImages)YoeImages.card(m,el);window.YoeVideos?.card(m,el);window.YoeWeb?.card(m,el);if(!isBusy)window.YoeSpeech?.card(m,el);actions(m,el,index,isBusy,retry);record.sig=snapshot(m);
   }
   if(!isBusy&&m.role==='assistant'&&!m.imageGeneration&&!m.videoGeneration&&!el.querySelector('.speech-controls')&&window.YoeSpeech){const controls=el.querySelector('.response-actions');if(controls)controls.remove();YoeSpeech.card(m,el);if(controls)el.append(controls);}
   const r=el.querySelector('.regenerate-response');if(r){r.disabled=isBusy;r.onclick=()=>retry(items.indexOf(m));}if(el.parentNode!==chat)chat.append(el);index++;
  }
  if(!streamOnly){for(const el of [...chat.children])if(!keep.has(el))el.remove();historyList(items,isBusy,onDelete);lastItems=items;lastCount=items.length;lastTail=items.at(-1);}if(follow)chat.scrollTop=chat.scrollHeight;return true;
 }
 function init(){
  const chat=$('chat');chat.addEventListener('scroll',()=>{follow=chat.scrollHeight-chat.scrollTop-chat.clientHeight<100;},{passive:true});
  const stats=document.querySelector('.stats');stats.classList.add('system-status');const toggle=document.createElement('button');toggle.id='monitoring-toggle';toggle.className='monitoring-toggle';toggle.type='button';toggle.textContent='Details';toggle.setAttribute('aria-expanded','false');toggle.setAttribute('aria-controls','monitoring-details');const details=document.createElement('div');details.id='monitoring-details';details.hidden=true;
  const note=document.createElement('p');note.textContent='Live readings from this PC. Token usage is reported by llama.cpp; local inference has no API token fee.';details.append(note);const usage=$('token-usage');if(usage)details.append(usage);stats.append(toggle,details);toggle.onclick=()=>{details.hidden=!details.hidden;toggle.textContent=details.hidden?'Details':'Hide details';toggle.setAttribute('aria-expanded',String(!details.hidden));};
  const toolbar=document.createElement('div');toolbar.className='composer-toolbar';const composer=document.querySelector('.composer');const attach=document.querySelector('.attach-button');const file=$('image');const net=document.querySelector('.web-toggle');const buttons=document.querySelector('.composer-actions');toolbar.append(attach,file);if(net)toolbar.append(net);toolbar.append(buttons);composer.append(toolbar);if(net){const small=net.querySelector('small');if(small)small.hidden=true;}
  const heading=document.querySelector('.history-section>.eyebrow');if(heading)heading.textContent='CONVERSATION HISTORY';
  $('send').addEventListener('click',()=>{follow=true;});window.addEventListener('resize',()=>{if(follow)requestAnimationFrame(()=>chat.scrollTop=chat.scrollHeight);});
  window.render?.();
 }
 window.YoeUI={render,historyList,follow(){follow=true;},schedule(){dirty=true;if(frame||document.hidden)return;frame=setTimeout(()=>{requestAnimationFrame(()=>{frame=0;if(document.hidden)return;dirty=false;streamPass=true;try{window.render();lastPaint=performance.now();}finally{streamPass=false;}});},Math.max(0,50-(performance.now()-lastPaint)));}};
 document.addEventListener('visibilitychange',()=>{if(!document.hidden&&dirty)window.YoeUI.schedule();});
 document.addEventListener('DOMContentLoaded',init,{once:true});
})();
