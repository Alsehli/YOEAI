/* Local model settings are user controls, never executable model output. */
(()=>{'use strict';
 const dialog=document.getElementById('appearance-settings');if(!dialog)return;
 const box=document.createElement('section');box.className='local-model-settings';box.setAttribute('aria-labelledby','local-model-title');
 box.innerHTML='<h3 id="local-model-title">Local AI model</h3><p>Change the shared model without reinstalling. Your conversations stay on this PC.</p><label for="local-model-recent">Recent models</label><select id="local-model-recent"><option value="">Choose a recent model…</option></select><label for="local-model-path">GGUF model file</label><div class="local-model-path-row"><input id="local-model-path" type="text" placeholder="Select or paste the full .gguf file path" spellcheck="false"><button id="local-model-browse" type="button">Browse…</button></div><label for="local-model-projector">Vision projector (optional)</label><div class="local-model-path-row"><input id="local-model-projector" type="text" placeholder="Leave blank for text only" spellcheck="false"><button id="local-model-vision-browse" type="button">Browse…</button><button id="local-model-text-only" type="button">Text only</button></div><p class="local-model-help">Use a matching projector for vision. Support depends on the native runtime and available memory. Stop active tasks or voice before switching.</p><button id="local-model-load" type="button">Load selected model</button><p id="local-model-status" role="status" aria-live="polite"></p>';
 const downloads=document.createElement('details');downloads.className='model-download-choices';
 downloads.innerHTML='<summary>Need a model? Download choices</summary><p>These links open your browser only when clicked. Then Browse for the downloaded GGUF. A vision projector must match its model.</p><div><button type="button" data-model-download="lite">8GB starting model · Q4</button><button type="button" data-model-download="normal">16GB starting model · Q6</button><button type="button" data-model-download="vision">Matching vision projector</button><button type="button" data-model-download="catalog">Other GGUF models</button></div>';
 box.append(downloads);
 const footer=dialog.querySelector('.settings-footer');footer?footer.before(box):dialog.append(box);
 const el=id=>document.getElementById(id),model=el('local-model-path'),vision=el('local-model-projector'),recent=el('local-model-recent'),note=el('local-model-status');let dirty=false,polling=false,loading=false,pending=0,clientError='',clientNotice='',items=[],lastRecent='';
 model.addEventListener('input',()=>{dirty=true;clientError='';clientNotice='';});vision.addEventListener('input',()=>{dirty=true;clientError='';clientNotice='';});
 async function api(path,body){const r=await fetch('/local-models/'+path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const x=await r.json();if(!r.ok)throw Error(x.error||'Model operation failed.');return x;}
 function disable(value){for(const control of box.querySelectorAll('input,select,button'))if(control.disabled!==value)control.disabled=value;}
 async function poll(){if(polling||!dialog.open)return;polling=true;try{const s=await api('state');if(!dialog.open)return;loading=s.busy||s.experience?.state==='loading';updateGuide(s);disable(loading||pending>0);if(!dirty){if(model.value!==(s.model||''))model.value=s.model||'';if(vision.value!==(s.projector||''))vision.value=s.projector||'';}
  const signature=JSON.stringify(s.recent||[]);if(signature!==lastRecent){lastRecent=signature;items=s.recent||[];recent.replaceChildren(new Option('Choose a recent model…',''));items.forEach((x,i)=>recent.add(new Option(String(x.model).split(/[\\/]/).pop(),String(i))));}
  const statusText=clientError|| (s.experience?(s.experience.title+(s.experience.state==='loading'&&Number.isFinite(s.experience.progress)?' · '+Math.round(s.experience.progress*100)+'%':'')+'. '+s.experience.detail+(s.experience.error&&s.experience.state!=='choose'?' '+s.experience.error:'')+(s.rollback?' '+s.rollback:'')):(s.error||'Model status unavailable.'))+(s.warning?' '+s.warning:'')+(!loading&&clientNotice?' '+clientNotice:'');if(note.textContent!==statusText)note.textContent=statusText;
  if(s.phase==='ready'&&!s.busy&&dirty&&s.model===model.value){dirty=false;document.dispatchEvent(new CustomEvent('yoeai:local-model-changed',{detail:s}));}
 }catch(e){note.textContent=e.message;}finally{polling=false;}}
 recent.onchange=()=>{const x=items[Number(recent.value)];if(recent.value!==''&&x){model.value=x.model;vision.value=x.projector||'';dirty=true;clientError='';clientNotice='';}};
 async function browse(target){pending++;clientError='';clientNotice='';disable(true);try{const s=await api('pick',{});if(s.path){target.value=s.path;dirty=true;}}catch(e){clientError=e.message;note.textContent=clientError;}finally{pending--;disable(loading||pending>0);}}
 el('local-model-browse').onclick=()=>browse(model);el('local-model-vision-browse').onclick=()=>browse(vision);el('local-model-text-only').onclick=()=>{vision.value='';dirty=true;clientError='';clientNotice='';};
 el('local-model-load').onclick=async()=>{if(!model.value.trim()){clientError='Choose a GGUF model file first.';note.textContent=clientError;return;}pending++;clientError='';clientNotice='';disable(true);try{await api('apply',{model:model.value.trim(),projector:vision.value.trim(),confirmed:true});loading=true;note.textContent='Preparing the selected model…';await poll();}catch(e){loading=false;clientError=e.message;note.textContent=clientError;}finally{pending--;disable(loading||pending>0);}};
 downloads.querySelectorAll('[data-model-download]').forEach(button=>button.onclick=async()=>{pending++;disable(true);try{await api('downloads',{kind:button.dataset.modelDownload,confirmed:true});clientNotice='Download link opened in your browser. After downloading, choose Browse.';}catch(error){clientError=error.message;}finally{pending--;note.textContent=clientError||clientNotice;disable(loading||pending>0);}});
 const guide=document.createElement('section');guide.id='yoe-model-guide';guide.className='model-guide';guide.setAttribute('aria-labelledby','model-guide-title');guide.hidden=true;
 guide.innerHTML='<img src="/assets/yoeai-icon.png" width="52" height="52" alt=""><div class="model-guide-copy"><p class="model-guide-eyebrow">YOUR LOCAL AI</p><h2 id="model-guide-title"></h2><p id="model-guide-description"></p><p id="model-guide-hardware"></p><progress max="1" id="model-guide-progress" aria-label="Model loading progress" hidden></progress></div><div class="model-guide-actions"><button type="button" id="model-guide-start">Choose a model</button><button type="button" id="model-guide-later">Not now</button></div>';
 const chat=el('chat');if(chat)chat.before(guide);
 const chip=document.createElement('button');chip.type='button';chip.className='model-readiness-chip';chip.textContent='Checking model…';chip.title='Open model settings';(document.querySelector('.topbar')||document.querySelector('main header'))?.append(chip);
 let guideState=null,closedKey='',seen=false,modelTimer=0;
 try{seen=localStorage.getItem('yoeai-model-welcome-v1')==='done';}catch{}
 const text=(id,value)=>{const node=el(id);if(node&&node.textContent!==value)node.textContent=value;};
 function openSettings(){el('open-settings')?.click();requestAnimationFrame(()=>{box.scrollIntoView({block:'center'});model.focus({preventScroll:true});poll();});}
 chip.onclick=openSettings;
 el('model-guide-start').onclick=()=>{if(guideState?.state==='ready'){seen=true;try{localStorage.setItem('yoeai-model-welcome-v1','done');}catch{}guide.hidden=true;el('prompt')?.focus();}else openSettings();};
 el('model-guide-later').onclick=()=>{closedKey=guide.dataset.key;guide.hidden=true;};
 const contextSelect=el('context');let capacitySignature='';
 const contextNote=document.createElement('p');contextNote.id='context-capacity-note';contextNote.className='local-model-help';contextSelect?.closest('.settings-row')?.after(contextNote);
 function contextCapacity(s){
  const c=s.contextCapacity;if(!c||!contextSelect)return;
  const signature=JSON.stringify([c.options,c.requested,c.recommended]);
  if(signature!==capacitySignature){const selected=Number(contextSelect.value)||c.requested;contextSelect.replaceChildren(...c.options.map(n=>new Option(n.toLocaleString('en-US')+' tokens'+(n===c.recommended?' · recommended estimate':''),String(n))));contextSelect.value=String(c.options.includes(selected)?selected:c.requested);capacitySignature=signature;}
  const active=c.active?c.active.toLocaleString('en-US')+' tokens'+(c.allocationMeasured?' (native allocation verified)':' (older worker; reload to verify)'):'not loaded';
  const cache=Number.isFinite(c.kv?.bytes)?(c.kv.bytes/1073741824).toFixed(2)+' GiB estimated KV cache':'KV estimate unavailable';
  const message='Model-declared limit: '+(c.modelLimit?c.modelLimit.toLocaleString('en-US'):'unknown')+'. Active capacity: '+active+'. '+cache+'. '+c.note+(c.recommended?' Recommended estimate: '+c.recommended.toLocaleString('en-US')+' tokens. '+c.budgetScope+'.':' Select a size and apply to verify allocation; current VRAM does not establish a full-GPU recommendation.');
  if(contextNote.textContent!==message)contextNote.textContent=message;
  const usage=el('usage-capacity');if(usage)usage.textContent='Context capacity: '+active+'. Last-request token counts below measure actual input and output, not capacity.';
 }
 function updateGuide(s){contextCapacity(s);
  const state=s.experience;if(!state)return;guideState=state;
  const key=state.state+'|'+s.model;guide.dataset.key=key;
  const label=state.state==='ready'?'Ready':state.state==='loading'?'Loading…':state.state==='choose'?'Choose model':state.state==='error'?'Model needs attention':'Load model';
  window.YoeModelGuide={last:state,name:s.name,statusLabel:label};
  if(chip.textContent!==label)chip.textContent=label;chip.dataset.state=state.state;chip.setAttribute('aria-label',label+'. Open model settings');
  guide.hidden=(seen&&['ready','idle','loading'].includes(state.state))||closedKey===key;
  text('model-guide-title',state.title);text('model-guide-description',state.detail);
  const h=s.hardware;const hardwareText=h?((h.gpu?h.gpu+' · '+(h.vramMiB/1024).toFixed(1)+' GB GPU memory. ':'')+h.recommendation):'';text('model-guide-hardware',hardwareText);
  const primary=el('model-guide-start');primary.disabled=state.state==='loading';if(primary.textContent!==state.action)primary.textContent=state.action||'Loading…';
  const progress=el('model-guide-progress');progress.hidden=state.state!=='loading';if(state.state==='loading'){if(Number.isFinite(state.progress))progress.value=state.progress;else progress.removeAttribute('value');}
  document.dispatchEvent(new CustomEvent('yoeai:model-readiness',{detail:state}));
 }
 async function guidePoll(){if(document.hidden||dialog.open||modelTimer)return;modelTimer=1;try{updateGuide(await api('state'));}catch{guide.hidden=true;guideState=null;window.YoeModelGuide={last:null};if(chip.textContent!=='Status unavailable')chip.textContent='Status unavailable';}finally{modelTimer=0;}}
 guidePoll();setInterval(guidePoll,2500);
 new MutationObserver(()=>{if(dialog.open)poll();}).observe(dialog,{attributes:true,attributeFilter:['open']});setInterval(()=>{if(!document.hidden)poll();},1200);
})();
