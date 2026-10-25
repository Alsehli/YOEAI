/* Model selection is an explicit application operation, never model output. */
(()=>{'use strict';
 const box=document.createElement('div');box.className='model-mode-control';
 const label=document.createElement('label');label.textContent='AI mode';label.htmlFor='model-mode';
 const select=document.createElement('select');select.id='model-mode';select.setAttribute('aria-label','Shared AI model');
 for(const [v,t] of [['fast','Fast · 9B'],['advanced','Advanced · 27B']]){const o=document.createElement('option');o.value=v;o.textContent=t;select.append(o);}
 const note=document.createElement('span');note.className='model-mode-note';note.setAttribute('role','status');note.setAttribute('aria-live','polite');
 box.append(label,select,note);document.querySelector('.topbar')?.append(box);
 const detail=document.createElement('details');detail.className='model-mode-details';const summary=document.createElement('summary');summary.textContent='Model loading details';const pre=document.createElement('pre');detail.append(summary,pre);detail.hidden=true;box.after(detail);
 let busy=false,polling=false,previous=null,lastError=null;
 select.onchange=async()=>{const mode=select.value;select.disabled=true;note.textContent='Requesting model switch…';try{const r=await fetch('/models/switch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode})});const x=await r.json();if(!r.ok)throw Error(x.error||'Model switch failed');busy=true;await poll();}catch(e){note.textContent=e.message;select.disabled=false;if(previous)select.value=previous;}};
 async function poll(){if(polling)return;polling=true;try{const r=await fetch('/models/state');if(!r.ok)throw Error('Model status unavailable');const s=await r.json();busy=s.busy;previous=s.selected;select.disabled=busy;select.value=(busy&&s.target)||s.active||s.selected;select.options[1].disabled=!s.advancedAvailable;
  note.textContent=s.error?'Loading failed — open details':busy?s.phase==='unloading'?'Unloading previous model…':'Loading selected model…':!s.online?'Model offline':s.active==='advanced'?(s.vision?'8K profile · text, vision & tools':'8K profile · text & tools'):'Fast model · text & vision';
  if(s.active==='advanced'&&s.context!==8192&&!busy)note.textContent=Number(s.context).toLocaleString()+(s.vision?' tokens · text, vision & tools':' tokens · text & tools');
  pre.textContent=(s.error||s.detail||'')+'\n\nModel: '+s.model+'\nBackend: '+s.backend;detail.hidden=!(busy||s.error);if(s.error&&s.error!==lastError)detail.open=true;lastError=s.error||null;
  const ctx=document.getElementById('context');if(ctx){for(const o of ctx.options)o.disabled=s.active==='advanced'&&Number(o.value)>8192;if(!busy&&s.context)ctx.value=String(s.context);}
  const vision=s.vision===true,image=document.getElementById('image');if(image){image.disabled=!vision||busy;const label=document.querySelector('label[for="image"]');if(label){label.title=vision?'Analyse an attached image':'Select Fast Mode for image analysis';label.style.opacity=vision?'':'0.45';}}
  for(const b of document.querySelectorAll('[data-prompt]'))if(b.dataset.prompt.includes('understand an image')){b.disabled=!vision;b.title=vision?'':'Select Fast Mode for image analysis';}
  const prompt=document.getElementById('prompt');if(prompt)prompt.placeholder=vision?'Ask a question, share an idea, or attach an image…':'Ask a question or work through a complex task…';
  document.dispatchEvent(new CustomEvent('yoeai:model-state',{detail:s}));
 }catch(e){note.textContent=e.message;}finally{polling=false;}}
 poll();setInterval(poll,1500);
})();
