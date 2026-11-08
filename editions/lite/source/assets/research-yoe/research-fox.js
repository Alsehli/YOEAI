/* Research YOE: four RGBA poses + eight derived motion steps at 10 FPS.
   Reuses Code/Windows YOE's single-atlas canvas architecture. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.ResearchYoeAnimation=api;})(typeof window==='object'?window:globalThis,()=>{'use strict';
const FPS=10,FRAMES=8,states=Object.freeze(['idle','thinking','researching','success']);
const poses={idle:[0,0],thinking:[512,0],researching:[0,512],success:[512,512]};
let atlas=null,ready=false,drawCalls=0,drawMs=0;const details=new Map(),seen=new Map(),celebrations=new Map();let pending=false;
function evidence(task){return !!(task?.documents?.length||task?.sources?.length||(task?.tools||[]).some(t=>/read selected document|web search/i.test(t.name)));}
function selectState(task,now=Date.now()/1000){
 if(!task)return 'idle';
 if(['PLANNING','THINKING','ANALYSING'].includes(task.status))return 'thinking';
 if(['SEARCHING','READING','COMPARING'].includes(task.status))return 'researching';
 if(task.status==='RUNNING'){
  const event=task.events?.at(-1),message=event?.message||'',tool=task.tools?.at(-1);
  if(/searching the web|reading (?:selected|approved)|comparing (?:available )?(?:evidence|sources)/i.test(message))return /comparing/i.test(message)&&!evidence(task)?'thinking':'researching';
  if(tool&&tool.time>=Number(event?.time||0)&&/read selected document|web search/i.test(tool.name))return 'researching';
  return 'thinking';
 }
 if(task.status==='COMPLETED'&&!task.error&&!task.cancelled&&task.result){const age=now-Number(task.updated||0);if(age>=0&&age<FRAMES/FPS-1e-6)return 'success';}
 return 'idle';
}
function taskFor(snapshot,selected=true){const all=(snapshot?.state?.tasks||[]).filter(t=>t.agent==='research');return selected?(all.find(t=>t.id===snapshot?.selected)||null):all.find(t=>['PLANNING','RUNNING','QUEUED'].includes(t.status))||all[0];}
function observe(task,now){
 if(!task)return task;const prior=seen.get(task.id);seen.set(task.id,task.status);
 const cached=details.get(task.id);
 const full=task.events?task:cached?.status===task.status?{...cached,updated:task.updated}:task;
 if(task.status!=='COMPLETED')return full;
 let completion=celebrations.get(task.id);
 if(!completion||completion.version!==task.updated){
  completion={version:task.updated,eligible:prior?prior!=='COMPLETED':now-task.updated<1,started:null};celebrations.set(task.id,completion);
 }
 // Start the one-shot only after the real completed report has arrived.
 // Slow summary hydration must not consume the celebration before it can draw.
 if(completion.eligible&&completion.started===null&&full.result&&!full.error&&!full.cancelled)completion.started=now;
 return {...full,updated:completion.started??-Infinity};
}
function prune(snapshot){const ids=new Set((snapshot?.state?.tasks||[]).filter(t=>t.agent==='research').map(t=>t.id));for(const map of [details,seen,celebrations])for(const id of map.keys())if(!ids.has(id))map.delete(id);}
// Summary records omit events. Hydrate only on the existing 700ms UI update,
// never on the animation clock; no task submission or inference request here.
async function hydrate(snapshot){
 if(document.hidden||!document.body.classList.contains('mini-open')||snapshot?.connected===false)return;
 const task=taskFor(snapshot,false);if(!task||task.events||pending||!['PLANNING','RUNNING','COMPLETED'].includes(task.status))return;
 if(details.get(task.id)?.updated===task.updated)return;
 pending=true;try{const r=await fetch('/mini/state?selected='+encodeURIComponent(task.id));if(r.ok){const s=await r.json(),full=s.tasks?.find(t=>t.id===task.id);if(full){details.set(task.id,full);tick();}}}catch{}finally{pending=false;}
}
function star(ctx,x,y,r){ctx.beginPath();for(let i=0;i<8;i++){const a=i*Math.PI/4-Math.PI/2,v=i%2?r*.3:r;i?ctx.lineTo(x+Math.cos(a)*v,y+Math.sin(a)*v):ctx.moveTo(x+Math.cos(a)*v,y+Math.sin(a)*v);}ctx.closePath();ctx.fill();}
function eyelid(ctx,x,y){const g=ctx.createRadialGradient(x,y,6,x,y,25);g.addColorStop(0,'#fff3e3');g.addColorStop(.7,'#fff3e3');g.addColorStop(1,'#fff3e300');ctx.fillStyle=g;ctx.beginPath();ctx.ellipse(x,y,24,27,0,0,Math.PI*2);ctx.fill();ctx.strokeStyle='#493139';ctx.lineWidth=3;ctx.lineCap='round';ctx.beginPath();ctx.moveTo(x-14,y);ctx.quadraticCurveTo(x,y+7,x+14,y);ctx.stroke();}
function draw(ctx,state,frame=0,{reduced=false,blink=false}={}){
 if(!ready||!states.includes(state))return false;
 const start=performance.now();frame=reduced?0:Math.max(0,Math.floor(frame))%FRAMES;const phase=frame/FRAMES*Math.PI*2,wave=Math.sin(phase),pose=poses[state];
 ctx.save();ctx.clearRect(0,0,ctx.canvas.width,ctx.canvas.height);ctx.scale(ctx.canvas.width/512,ctx.canvas.height/512);ctx.imageSmoothingEnabled=true;ctx.imageSmoothingQuality='high';
 ctx.translate(270,490+(!reduced&&state==='success'?-Math.max(0,wave)*7:0));if(!reduced&&state==='thinking')ctx.rotate(wave*.013);ctx.scale(1,reduced?1:1+wave*.003);ctx.translate(-270,-490);
 ctx.drawImage(atlas,pose[0],pose[1],512,512,0,0,512,512);
 if(!reduced&&state==='idle'){
  // Tiny ear flex in an isolated ear-tip region of the approved pose.
  ctx.save();ctx.beginPath();ctx.rect(60,70,85,80);ctx.clip();ctx.clearRect(60,70,85,80);ctx.translate(102,145);ctx.rotate(wave*.012);ctx.translate(-102,-145);ctx.drawImage(atlas,0,0,512,512,0,0,512,512);ctx.restore();
  if(blink){eyelid(ctx,246,262);eyelid(ctx,332,281);}
 }
 ctx.restore();ctx.save();ctx.scale(ctx.canvas.width/512,ctx.canvas.height/512);
 if(!reduced&&state==='thinking'&&frame>=3&&frame<=5){ctx.fillStyle='#319df6';ctx.globalAlpha=.8;ctx.font='700 28px sans-serif';ctx.fillText('?',432,202-wave*3);}
 if(!reduced&&state==='researching'){
  // Translucent page fold follows the open notebook; it is a derived effect.
  const fold=Math.sin(phase)*22;ctx.fillStyle='#d8f3ff80';ctx.strokeStyle='#81caff90';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(314,451);ctx.lineTo(314+fold,411);ctx.quadraticCurveTo(337+fold,404,349,412);ctx.lineTo(331,449);ctx.closePath();ctx.fill();ctx.stroke();
  ctx.fillStyle='#6cd8ff';for(const [x,y] of [[90,289],[439,345],[414,253]]){ctx.globalAlpha=.3+Math.abs(wave)*.5;star(ctx,x,y-wave*5,2+Math.abs(wave)*2);}
 }
 if(!reduced&&state==='success'){ctx.fillStyle='#6bdfff';for(const [x,y] of [[59,205],[453,230],[444,295]]){ctx.globalAlpha=.35+.55*Math.abs(wave);star(ctx,x,y-wave*4,4+Math.abs(wave)*3);}}
 ctx.restore();drawCalls++;drawMs+=performance.now()-start;return true;
}
function tick(){
 if(!ready||document.hidden||!document.body.classList.contains('mini-open'))return;
 const snapshot=window.MiniYoeUI?.snapshot(),now=Date.now()/1000,reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
 for(const c of document.querySelectorAll('.mini-animated-fox[data-agent="research"]')){
  const r=c.getBoundingClientRect();if(!r.width||!r.height||r.bottom<0||r.top>innerHeight||r.right<0||r.left>innerWidth)continue;
  const task=observe(taskFor(snapshot,!!c.closest('#mini-work')),now),state=snapshot?.connected===false?'idle':selectState(task,now);
  const frame=state==='success'?Math.min(7,Math.floor((now-task.updated)*FPS)):Math.floor(performance.now()/100)%FRAMES,blink=!reduced&&state==='idle'&&Math.floor(now*FPS)%50===0;
  const key=[state,reduced?0:frame,reduced,blink].join(':');
  if(c.dataset.researchDrawKey!==key){draw(c.getContext('2d'),state,frame,{reduced,blink});c.dataset.researchDrawKey=key;}
  c.dataset.researchState=state;c.dataset.researchFrame=String(reduced?0:frame);c.dataset.taskStatus=task?.status||'READY';c.setAttribute('aria-label',snapshot?.connected===false?'Research YOE: Connection lost; task status unavailable':'Research YOE: '+(task?.status||'Ready')+' ('+state+')');
 }
}
if(typeof document==='object'){atlas=new Image();atlas.onload=()=>{ready=true;tick();};atlas.src='/assets/research-yoe/poses.png';setInterval(tick,100);document.addEventListener('visibilitychange',tick);addEventListener('mini:updated',e=>{prune(e.detail);hydrate(e.detail);tick();});}
return Object.freeze({states,FPS,FRAMES,selectState,taskFor,observe,draw,tick,get ready(){return ready;},stats:()=>({drawCalls,totalDrawMs:drawMs,meanDrawMs:drawCalls?drawMs/drawCalls:0,atlasDecodedBytes:4194304})});
});
