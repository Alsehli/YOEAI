/* Windows YOE transparent reference-derived poses with procedural motion. Shared Code YOE canvas architecture: one atlas,
   10 FPS, viewport/visibility gating, static reduced motion. No inference calls. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.WindowsYoeAnimation=api;})(typeof window==='object'?window:globalThis,()=>{'use strict';
const FPS=10,FRAMES=8,SIZE=132,states=Object.freeze(['idle','thinking','working','success']);
let atlas=null,ready=false,drawCalls=0,drawMs=0,lastTick=0;
const rows={idle:0,thinking:1,working:2,success:3};
const completions=new Map(),details=new Map(),requested=new Set(),seen=new Map();
function observe(task,now){
 if(!task)return task;
 const key=task.id+':'+task.updated,previous=seen.get(task.id);seen.set(task.id,task.status);
 if(task.status!=='COMPLETED')return task;
 if(!completions.has(key))completions.set(key,(previous&&previous!=='COMPLETED')||now-Number(task.updated)<1?now:-Infinity);
 if(!task.tools&&!requested.has(key)){requested.add(key);fetch('/mini/state?selected='+encodeURIComponent(task.id)).then(r=>r.ok?r.json():null).then(s=>{const full=s?.tasks?.find(t=>t.id===task.id&&t.updated===task.updated);if(full)details.set(key,full);}).catch(()=>{});}
 const full=task.tools?task:details.get(key)||task;
 return {...full,updated:completions.get(key)};
}
function successful(task){
 const records=(task?.tools||[]).filter(r=>r.windowsAction);
 return task?.status==='COMPLETED'&&!task.error&&records.length>0&&records.every(r=>r.status==='PASS'&&r.verification==='VERIFIED'&&!r.error);
}
function selectState(task,now=Date.now()/1000){
 if(!task)return 'idle';
 if(task.status==='PLANNING'||task.status==='THINKING')return 'thinking';
 if(task.status==='RUNNING')return /refreshing remaining|planning/i.test(task.events?.at(-1)?.message||'')?'thinking':'working';
 if(successful(task)){const age=now-Number(task.updated||0);if(age>=0&&age<FRAMES/FPS-1e-6)return 'success';}
 return 'idle';
}
function taskFor(snapshot){
 const all=(snapshot?.state?.tasks||[]).filter(t=>t.agent==='windows');
 return all.find(t=>t.id===snapshot?.selected)||all.find(t=>['PLANNING','RUNNING','QUEUED','WAITING_FOR_APPROVAL','PAUSED'].includes(t.status))||all[0];
}
function eyelid(ctx,x,y){
 const g=ctx.createRadialGradient(x,y,6,x,y,27);g.addColorStop(0,'#fff3e3');g.addColorStop(.7,'#fff3e3');g.addColorStop(1,'#fff3e300');ctx.fillStyle=g;
 ctx.beginPath();ctx.ellipse(x,y,25,29,0,0,Math.PI*2);ctx.fill();ctx.strokeStyle='#483039';ctx.lineWidth=3;ctx.lineCap='round';ctx.beginPath();ctx.moveTo(x-14,y);ctx.quadraticCurveTo(x,y+8,x+14,y);ctx.stroke();
}
function star(ctx,x,y,r){ctx.beginPath();for(let i=0;i<8;i++){const a=i*Math.PI/4-Math.PI/2,v=i%2?r*.3:r;i?ctx.lineTo(x+Math.cos(a)*v,y+Math.sin(a)*v):ctx.moveTo(x+Math.cos(a)*v,y+Math.sin(a)*v);}ctx.closePath();ctx.fill();}
function draw(ctx,state,frame=0,{reduced=false,blink=false}={}){
 if(!ready||!states.includes(state))return false;
 const started=performance.now();frame=reduced?0:Math.max(0,Math.floor(frame))%FRAMES;
 const pose={idle:[0,0],thinking:[512,0],working:[0,512],success:[512,512]}[state];
 const phase=frame/FRAMES*Math.PI*2,wave=Math.sin(phase);
 ctx.save();ctx.clearRect(0,0,ctx.canvas.width,ctx.canvas.height);ctx.scale(ctx.canvas.width/512,ctx.canvas.height/512);
 ctx.imageSmoothingEnabled=true;ctx.imageSmoothingQuality='high';
 const bounce=!reduced&&state==='success'?-Math.max(0,wave)*8:0;
 ctx.translate(270,490+bounce);if(!reduced&&state==='thinking')ctx.rotate(wave*.012);
 ctx.scale(1,reduced?1:1+wave*.003);ctx.translate(-270,-490);
 ctx.drawImage(atlas,pose[0],pose[1],512,512,0,0,512,512);
 if(!reduced&&state==='working'){
  // Repaint the keyboard paw region with a subtle two-pixel typing motion.
  const x=205,y=414,w=95,h=38,motion=Math.sin(phase*2);
  ctx.save();ctx.beginPath();ctx.rect(x,y,w,h);ctx.clip();ctx.clearRect(x,y,w,h);
  ctx.drawImage(atlas,pose[0]+x,pose[1]+y,w,h,x,y-motion*1.8,w,h);ctx.restore();
 }
 if(blink&&!reduced&&state==='idle'){eyelid(ctx,242,263);eyelid(ctx,332,283);}
 ctx.restore();ctx.save();ctx.scale(ctx.canvas.width/512,ctx.canvas.height/512);
 if(state==='thinking'&&!reduced&&frame>=3&&frame<=5){ctx.fillStyle='#248cfa';ctx.font='700 28px sans-serif';ctx.globalAlpha=.75;ctx.fillText('?',452,220-wave*3);}
 if(state==='working'&&!reduced){ctx.fillStyle='#55cdff';ctx.globalAlpha=.25+Math.abs(wave)*.35;ctx.fillRect(419,266-wave*3,35,2);ctx.fillRect(422,276-wave*3,22,2);}
 if(state==='success'&&!reduced){ctx.fillStyle='#ffd965';for(const [x,y] of [[58,205],[444,220],[440,295]]){ctx.globalAlpha=.35+.6*Math.abs(wave);star(ctx,x,y-wave*4,4+Math.abs(wave)*3);}}
 ctx.restore();drawCalls++;drawMs+=performance.now()-started;return true;
}
function tick(){
 if(!ready||document.hidden||!document.body.classList.contains('mini-open'))return;
 const dashboard=window.MiniYoeUI?.snapshot(),workspace=window.WindowsYoe?.snapshot?.(),now=Date.now()/1000;
 const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
 for(const c of document.querySelectorAll('.mini-animated-fox[data-agent="windows"]')){
  const r=c.getBoundingClientRect();if(!r.width||!r.height||r.bottom<0||r.top>innerHeight||r.right<0||r.left>innerWidth)continue;
  const snapshot=c.closest('#windows-yoe')?workspace:dashboard;
  const task=observe(taskFor(snapshot),now),state=selectState(task,now);
  const frame=state==='success'?Math.min(7,Math.floor((now-task.updated)*FPS)):Math.floor(performance.now()/100)%FRAMES;
  const blink=state==='idle'&&Math.floor(now*FPS)%50===0;
  const key=[state,reduced?0:frame,reduced,blink].join(':');if(c.dataset.windowsDrawKey===key)continue;
  draw(c.getContext('2d'),state,frame,{reduced,blink});c.dataset.windowsDrawKey=key;
  c.dataset.windowsState=state;c.dataset.windowsFrame=String(reduced?0:frame);
  c.dataset.taskStatus=task?.status||'READY';c.setAttribute('aria-label','Windows YOE: '+(task?.status||'Ready')+' ('+state+')');
 }lastTick=performance.now();
}
if(typeof document==='object'){
 atlas=new Image();atlas.onload=()=>{ready=true;tick();};atlas.src='/assets/windows-yoe/poses.png';
 setInterval(tick,100);document.addEventListener('visibilitychange',tick);
}
return Object.freeze({states,FPS,FRAMES,draw,selectState,successful,taskFor,tick,get ready(){return ready;},stats:()=>({drawCalls,totalDrawMs:drawMs,meanDrawMs:drawCalls?drawMs/drawCalls:0,lastTick,atlasDecodedBytes:1024*1024*4})});
});

