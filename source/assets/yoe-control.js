/* Main-chat computer control. All execution stays in Windows YOE's typed,
 * scoped workers; this UI never executes model-generated scripts or selectors. */
(function(root){'use strict';
function nearName(a,b){
 if(a===b)return true;if(Math.abs(a.length-b.length)>1||Math.min(a.length,b.length)<4)return false;
 if(a.length===b.length){const d=[];for(let i=0;i<a.length;i++)if(a[i]!==b[i])d.push(i);return d.length===1||d.length===2&&d[1]===d[0]+1&&a[d[0]]===b[d[1]]&&a[d[1]]===b[d[0]];}
 if(a.length>b.length)[a,b]=[b,a];let i=0,j=0,skipped=false;while(i<a.length&&j<b.length){if(a[i]===b[j]){i++;j++;}else{if(skipped)return false;skipped=true;j++;}}return true;
}
function scopeFor(text,apps,previous=null){
 const origins=[],add=u=>{try{const p=new URL(u);if(['https:','http:'].includes(p.protocol)&&!p.username&&!p.password&&!origins.includes(p.origin))origins.push(p.origin);}catch{}};
 // Remove URLs from app/site-name matching: words inside a URL cannot grant
 // extra origins or application permissions. Emails never become destinations.
 let words=text.replace(/https?:\/\/[^\s<>"']+/gi,u=>{add(u.replace(/[.,;!?)]*$/,''));return ' ';}).replace(/\S+@\S+/g,' ');
 words=words.replace(/(?<![@/\w.-])(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,24}(?::\d{1,5})?(?:\/[^\s<>"']*)?/gi,u=>{if(!/\.(?:exe|dll|pdf|txt|docx?|xlsx?|pptx?|png|jpe?g|webp|zip|py|js)$/i.test(u))add('https://'+u.replace(/[.,;!?)]*$/,''));return ' ';});
 for(const [pattern,url] of [[/\byoutube\b|يوتيوب/i,'https://www.youtube.com'],[/\bgithub\b|جيت\s*هب/i,'https://github.com'],[/\bwikipedia\b|ويكيبيديا/i,'https://www.wikipedia.org']])if(pattern.test(words))add(url);
 if(/\bgoogle\b(?!\s+chrom\w*)/i.test(words))add('https://www.google.com');
 if(/\bbing\b/i.test(words))add('https://www.bing.com');
 if(/\bduckduckgo\b/i.test(words))add('https://duckduckgo.com');
 if(!origins.length&&/\b(search|look\s+up)\b|ابحث|بحث/i.test(words))add('https://www.google.com');
 const aliases={chrome:/\b(?:chrom|chrome|google chrome)\b|كروم/i,edge:/\b(?:edge|microsoft edge)\b|ايدج|إيدج/i,word:/\b(?:open|opne|launch|start|bring up|switch to|focus|in|using|with)\s+(?:(?:the|microsoft)\s+)?word\b|\bmicrosoft word\b|\bword app\b|^word$|وورد|ورد/i,font:/\b(?:open|opne|launch|start|bring up|switch to|focus|in|using|with)\s+(?:the\s+)?font\b|\bfont app\b|^font$|فونت/i,notepad:/\bnotepad\b|المفكرة/i,photoshop:/\bphotoshop\b|فوتوشوب/i,explorer:/\b(?:explorer|file explorer)\b|مستكشف الملفات/i,calculator:/\bcalculator\b|الحاسبة/i,taskmanager:/\btask\s*manager\b|مدير المهام/i};
 const tokens=words.toLowerCase().match(/[a-z]+/g)||[];
 const chosen=Object.keys(apps).filter(a=>apps[a].installed&&((aliases[a]||new RegExp('\\b'+a+'\\b','i')).test(words)||a.length>=5&&tokens.some(t=>nearName(t,a))));
 if(!chosen.length&&/\b(?:open|opne|launch|start)\s+(?:the\s+)?browser\b|افتح المتصفح/i.test(words)){const b=['edge','chrome'].find(a=>apps[a]?.installed);if(b)chosen.push(b);}
 if(!origins.length&&!chosen.length&&previous&&Date.now()-previous.at<600000&&/\b(scroll|click|type|fill|read|navigate|page|window|button|link|it|this|there)\b|مرر|اضغط|اكتب|الصفحة|النافذة/i.test(words)){
  chosen.push(...previous.scope.apps.filter(a=>apps[a]?.installed));origins.push(...previous.scope.origins);
 }
 if(origins.length){const browser=chosen.find(a=>['chrome','edge'].includes(a))||['edge','chrome'].find(a=>apps[a]?.installed);if(!browser)throw Error('Install a supported browser (Edge or Chrome) before browsing.');if(!chosen.includes(browser))chosen.push(browser);}
 if(!chosen.length&&!origins.length)throw Error('Please name the application or include the website address to control.');
 return {mode:'ADVANCED',apps:chosen,origins:origins.slice(0,8),folder:null,maxActions:12,maxSeconds:300,maxRetries:0,reuseLowRisk:true,webSearch:false};
}
// Only navigation to the user's explicit origin can inherit the send action.
// Filling, clicking controls, file operations and submissions always use review.
function navigationApproval(action,scope,objective=''){
 if(action?.tool==='browser_read')return scope.origins.length>0;
 if(action?.tool!=='browser_open'||!scope.apps.includes(action.params?.app))return false;
 try{const u=new URL(action.params.url);if(!scope.origins.includes(u.origin))return false;
  const exact=(objective.match(/https?:\/\/[^\s<>"']+/gi)||[]).some(x=>new URL(x.replace(/[.,;!?)]*$/,'')).href===u.href);
  if(exact)return true;
  const q=u.searchParams.get('q'),known=['https://www.google.com','https://www.bing.com','https://duckduckgo.com'];
  if(q&&known.includes(u.origin)&&/\bsearch\b|\u0627\u0628\u062d\u062b|\u0628\u062d\u062b/i.test(objective)&&objective.toLowerCase().includes(q.toLowerCase()))return true;
  return !u.search&&u.pathname==='/'&&known.includes(u.origin)&&new RegExp(u.hostname.split('.').slice(-2,-1)[0],'i').test(objective);
 }catch{return false;}
}
if(typeof module==='object')module.exports={scopeFor,navigationApproval};
if(!root.document)return;
const $=id=>document.getElementById(id);let enabled=false,active=null,requestBusy=false,previous=null;
const arrow=document.createElement('button');arrow.id='yoe-control';arrow.type='button';arrow.className='yoe-control-toggle';arrow.setAttribute('aria-label','Activate YOE Control');arrow.setAttribute('aria-pressed','false');arrow.title='YOE Control — off';arrow.innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 3 20 12 13 14 10 21z"/></svg>';
document.querySelector('.composer-actions').prepend(arrow);
const panel=document.createElement('section');panel.className='yoe-control-panel';panel.hidden=true;panel.setAttribute('aria-label','YOE Control activity');
const label=document.createElement('p');label.setAttribute('role','status');label.setAttribute('aria-live','polite');
const controls=document.createElement('div');const pause=button('Pause'),stop=button('Stop');controls.append(pause,stop);
const details=document.createElement('details'),summary=document.createElement('summary'),log=document.createElement('pre');summary.textContent='Actions and permissions';details.append(summary,log);
const review=document.createElement('div');panel.append(label,controls,review,details);$('input-panel').before(panel);
function button(text,fn){const b=document.createElement('button');b.type='button';b.textContent=text;if(fn)b.onclick=fn;return b;}
async function api(path,body){const r=await fetch('/mini/'+path,{method:body===undefined?'GET':'POST',headers:body===undefined?{}:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});const data=await r.json();if(!r.ok)throw Error(data.error||'Computer-control request failed.');return data;}
function state(){arrow.classList.toggle('active',enabled);arrow.setAttribute('aria-pressed',String(enabled));arrow.title='YOE Control — '+(enabled?'on':'off');arrow.setAttribute('aria-label',(enabled?'Deactivate':'Activate')+' YOE Control');}
async function cancelJob(job){if(!job)return;job.stopping=true;if(job.id&&!job.cancelSent){job.cancelSent=true;try{await api(job.kind==='storage'?'windows/storage/'+job.id+'/cancel':'task/'+job.id+'/cancel',{});}catch(e){job.cancelSent=false;throw e;}}}
async function cancel(){await cancelJob(active);}
arrow.onclick=async()=>{if(requestBusy)return;requestBusy=true;arrow.disabled=true;try{if(enabled){await cancel();enabled=false;previous=null;}else{await api('windows/enable',{enabled:true,approve:true});enabled=true;}state();}catch(e){$('error').textContent=e.message;}finally{requestBusy=false;arrow.disabled=false;}};
stop.onclick=()=>cancel().catch(e=>{$('error').textContent=e.message;});
pause.onclick=async()=>{if(!active?.id)return;pause.disabled=true;try{await api(active.kind==='storage'?'windows/storage/'+active.id+(pause.textContent==='Resume'?'/resume':'/pause'):'task/'+active.id+(pause.textContent==='Resume'?'/windows-resume':'/windows-pause'),{});}catch(e){$('error').textContent=e.message;}finally{pause.disabled=false;}};
async function decision(t,choice){if(!active||active.stopping)return;for(const b of review.querySelectorAll('button'))b.disabled=true;try{await api('task/'+t.id+'/windows-decision',{choice,nonce:t.windows.pending.nonce});return true;}catch(e){$('error').textContent=e.message;for(const b of review.querySelectorAll('button'))b.disabled=false;return false;}}
function show(t){
 const pending=t.windows?.pending;label.textContent=t.status==='PAUSED'?'YOE is paused.':t.status==='WAITING_FOR_APPROVAL'?'YOE needs your review.':['COMPLETED','FAILED','CANCELLED'].includes(t.status)?(t.status==='COMPLETED'?'YOE task ended. Review the result.':'YOE '+t.status.toLowerCase()+'.'):'YOE is working…';
 pause.textContent=t.status==='PAUSED'?'Resume':'Pause';pause.disabled=!['QUEUED','PLANNING','RUNNING','WAITING_FOR_APPROVAL','PAUSED'].includes(t.status);stop.disabled=['COMPLETED','FAILED','CANCELLED'].includes(t.status);
 log.textContent=JSON.stringify({scope:t.windows?.scope,plan:t.windows?.plan,events:t.events,actions:t.tools,error:t.error},null,2);
 if(review.dataset.nonce===(t.status+':'+(pending?.nonce||'')))return;review.dataset.nonce=t.status+':'+(pending?.nonce||'');review.replaceChildren();
 if(t.status==='WAITING_FOR_APPROVAL'&&pending){const p=document.createElement('p');p.textContent=pending.message;const pre=document.createElement('pre');pre.textContent=JSON.stringify(pending.action||t.windows.plan,null,2);review.append(p,pre);details.open=true;
  if(pending.kind==='action')review.append(button('Approve once',()=>decision(t,'approve')));
  if(pending.kind==='handoff')review.append(button('I completed it myself',()=>decision(t,'done')));
  review.append(button('Stop task',()=>cancel().catch(e=>{$('error').textContent=e.message;})));
 }
}
root.YoeControl={get enabled(){return enabled;},async prepare(text,target,signal,refresh,messages=[]){
 if(!enabled)return false;if(active)throw Error('Stop the current YOE Control task first.');
 panel.hidden=false;label.textContent='YOE is preparing…';review.replaceChildren();review.dataset.nonce='';details.open=false;log.textContent='';
 const job={id:null,stopping:false};active=job;const onAbort=()=>{cancelJob(job).catch(()=>{});};signal.addEventListener('abort',onAbort,{once:true});
 try{
  const caps=await api('windows/capabilities');if(!caps.enabled)throw Error('YOE Control is disabled. Turn the arrow off and on again.');
  let scope=null;try{scope=scopeFor(text,caps.apps,previous);}catch{}
  const directComputer=scope&&/^(?:(?:please|can you|could you)\s+)?(?:open|opne|launch|start|visit|go to|click|scroll|type|fill|افتح|شغل|اضغط|مرر)\b/i.test(text);
  const route=directComputer?{route:'computer'}:await api('windows/control-route',{text,history:messages.filter(m=>['user','assistant'].includes(m.role)&&typeof m.content==='string').slice(-6)});
  if(job.stopping||signal.aborted||!enabled)throw new DOMException('Stopped','AbortError');
  target.controlRoute=route.route;target.controlQuery=route.route==='web'?(route.query||text):undefined;
  if(route.route==='chat'||route.route==='web'){panel.hidden=true;return false;}
  if(route.route==='clarify'){target.content=route.question||'What would you like me to do?';panel.hidden=true;refresh();return true;}
  if(route.route==='storage'){
   if(route.question||!route.drive){target.content=route.question||'Which drive should I inspect? For example, F:.';panel.hidden=true;refresh();return true;}
   job.kind='storage';let scan=await api('windows/storage/start',{text});job.id=scan.id;
   if(job.stopping||signal.aborted){await cancelJob(job);throw new DOMException('Stopped','AbortError');}
   for(;;){
    label.textContent=scan.status==='PAUSED'?'YOE is paused.':'Scanning '+scan.drive+' — '+Number(scan.count).toLocaleString()+' entries checked…';
    pause.disabled=stop.disabled=false;pause.textContent=scan.status==='PAUSED'?'Resume':'Pause';
    target.content='Scanning '+scan.drive+' for the '+scan.limit+' largest files… '+Number(scan.count).toLocaleString()+' entries checked.';refresh();
    if(!['RUNNING','PAUSED'].includes(scan.status))break;
    await new Promise(resolve=>setTimeout(resolve,500));if(signal.aborted||job.stopping)await cancelJob(job);
    scan=await api('windows/storage/'+job.id);
   }
   if(scan.status==='FAILED')throw Error(scan.error||'Storage scan failed.');
   const safe=p=>String(p).replace(/[`|\r\n]/g,' ');
   target.content='### '+(scan.status==='CANCELLED'?'Scan stopped — partial results':'Largest files on '+scan.drive)+'\n\n| File | Size (GiB) |\n|---|---:|\n'+scan.files.map(f=>'| `'+safe(f.path)+'` | '+(f.bytes/1024**3).toFixed(3)+' |').join('\n')+'\n\n'+Number(scan.count).toLocaleString()+' entries checked. '+scan.skipped+' protected, hidden, linked or inaccessible entries skipped.'+(scan.partial?' Time/entry limit reached; results are partial.':'')+' Metadata only; no files were changed.';
   label.textContent=scan.status==='CANCELLED'?'YOE stopped.':'Storage scan completed.';target.storageResult=scan;refresh();return true;
  }
  scope=scope||{mode:'ADVANCED',apps:[],origins:[],folder:null,maxActions:12,maxSeconds:300,maxRetries:0,reuseLowRisk:true,webSearch:false};if(signal.aborted||job.stopping||!enabled)throw new DOMException('Stopped','AbortError');
  const parent=previous&&Date.now()-previous.at<600000&&JSON.stringify(scope.apps)===JSON.stringify(previous.scope.apps)&&JSON.stringify(scope.origins)===JSON.stringify(previous.scope.origins)?previous.id:undefined;
  let task=await api('tasks',{agent:'windows',objective:text,windows:scope,windowsParent:parent});job.id=task.id;target.controlTask=task.id;
  if(job.stopping||signal.aborted){await cancelJob(job);throw new DOMException('Stopped','AbortError');}
  let updated=null;
  for(;;){
   if(signal.aborted){await cancel();throw new DOMException('Stopped','AbortError');}
   if(task.updated!==updated){updated=task.updated;show(task);target.content=task.result||task.error||'YOE Control: '+task.status.toLowerCase().replaceAll('_',' ')+'\n\n'+(task.events?.at(-1)?.message||'');refresh();}
   if(['COMPLETED','FAILED','CANCELLED'].includes(task.status))break;
   const p=task.windows?.pending;
   if(task.status==='WAITING_FOR_APPROVAL'&&p&&!job.stopping&&(p.kind==='plan'||p.kind==='action'&&navigationApproval(p.action,scope,text))){if(!await decision(task,'approve'))throw Error('The approval could not be applied. The task was stopped; review the error before retrying.');}
   await new Promise(resolve=>setTimeout(resolve,700));
   task=await api('windows/control-task/'+encodeURIComponent(job.id));if(!task)throw Error('Task status unavailable. Open Windows YOE history to review it.');
  }
  if(task.status==='COMPLETED'&&task.tools?.some(r=>r.verification==='VERIFIED'))previous={id:task.id,scope,at:Date.now()};
  return true;
 }catch(e){await cancelJob(job).catch(()=>{});label.textContent=e.name==='AbortError'?'YOE stopped.':e.message;throw e;}
 finally{signal.removeEventListener('abort',onAbort);active=null;pause.disabled=stop.disabled=true;review.replaceChildren();}
 }};
})(typeof window==='object'?window:globalThis);
