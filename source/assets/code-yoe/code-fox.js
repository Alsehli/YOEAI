/* SPDX-License-Identifier: GPL-3.0-only
 * Four cleaned reference poses + derived Canvas motion, NOT 64 extracted drawings.
 * One shared 736 KB atlas; no network/model calls, audio or backend changes.
 */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.CodeYoeAnimation=api;})(typeof window==='object'?window:globalThis,()=>{'use strict';
const states=Object.freeze(['idle','thinking','typing','working','happy','success','error','sleeping']);
const FPS=10,FRAMES=8;let atlas=null,ready=false,lastActivity=Date.now()/1000,drawCalls=0,drawMs=0,lastTick=0;
const poses={idle:[0,0],thinking:[512,0],typing:[0,512],working:[0,512],happy:[512,512],success:[512,512],error:[512,0],sleeping:[0,0]};
function selectState(task,now=Date.now()/1000,activity=lastActivity,online=true){
 if(task){const age=Math.max(0,now-Number(task.updated||task.created||0));switch(task.status){
 case 'QUEUED':case 'PLANNING':case 'WAITING_FOR_APPROVAL':case 'PAUSED':return 'thinking';
 case 'RUNNING':{const message=String(task.events?.at(-1)?.message||'');if(/review|plan|compar/i.test(message))return 'thinking';if(task.phase==='validate'||/test|check|patch|tool/i.test(message))return 'working';return task.stream?'typing':'working';}
 case 'FAILED':return 'error';case 'COMPLETED':if(age<1.6)return 'success';if(age<4)return 'happy';break;
 }}return !online||now-activity>=90?'sleeping':'idle';
}
function eyelid(ctx,x,y,amount){if(!amount)return;ctx.save();const g=ctx.createRadialGradient(x,y,1,x,y,27);g.addColorStop(0,'#fff7e9');g.addColorStop(.8,'#fff5e7');g.addColorStop(1,'#fff5e700');ctx.fillStyle=g;ctx.beginPath();ctx.ellipse(x,y,26,29,0,0,Math.PI*2);ctx.fill();ctx.strokeStyle='#503635';ctx.lineWidth=3;ctx.lineCap='round';ctx.beginPath();ctx.moveTo(x-16,y);ctx.quadraticCurveTo(x,y+7*amount,x+16,y-2);ctx.stroke();ctx.restore();}
function star(ctx,x,y,r){ctx.beginPath();for(let k=0;k<8;k++){const a=k*Math.PI/4-Math.PI/2,v=k%2?r*.3:r;const px=x+Math.cos(a)*v,py=y+Math.sin(a)*v;k?ctx.lineTo(px,py):ctx.moveTo(px,py);}ctx.closePath();ctx.fill();}
function draw(ctx,state,frame=0,{reduced=false,blink=true}={}){
 if(!ready||!states.includes(state))return false;const start=typeof performance==='object'?performance.now():0;
 frame=reduced?0:Math.max(0,Math.floor(frame))%FRAMES;const phase=frame/FRAMES*Math.PI*2,s=Math.sin(phase),pose=poses[state],size=ctx.canvas.width;
 ctx.save();ctx.clearRect(0,0,ctx.canvas.width,ctx.canvas.height);ctx.scale(size/512,ctx.canvas.height/512);ctx.imageSmoothingEnabled=true;ctx.imageSmoothingQuality='high';
 const bounce=reduced?0:state==='success'?-Math.max(0,s)*7:state==='happy'?-Math.max(0,s)*3:-s*.8;
 ctx.translate(280,480+bounce);if(!reduced&&['thinking','error'].includes(state))ctx.rotate(s*(state==='error'?.025:.012));const breathe=reduced?1:1+s*.003;ctx.scale(1,breathe);ctx.translate(-280,-480);
 ctx.drawImage(atlas,pose[0],pose[1],512,512,0,0,512,512);
 if(!reduced&&['typing','working'].includes(state))for(const [x,y,w,h,offset] of [[222,417,70,43,0],[299,413,24,40,Math.PI]]){const motion=Math.sin(phase*2+offset);ctx.save();ctx.beginPath();ctx.rect(x-1,y-2,w+2,h+4);ctx.clip();ctx.drawImage(atlas,pose[0]+x,pose[1]+y,w,h,x+motion*.7,y-motion*2,w,h);ctx.restore();}
 if(state==='sleeping'){eyelid(ctx,259,325,1);eyelid(ctx,331,331,1);}else if(!reduced&&blink&&frame===6&&['idle','typing','working'].includes(state)){const typing=state!=='idle';eyelid(ctx,typing?270:259,typing?334:325,1);eyelid(ctx,typing?337:331,typing?340:331,1);}
 ctx.restore();ctx.save();ctx.scale(size/512,ctx.canvas.height/512);
 if(state==='working'&&!reduced){ctx.fillStyle='#df315d';ctx.font='600 18px "JetBrains Mono",monospace';ctx.globalAlpha=.25+frame/40;ctx.fillText('</>',409,300-frame*2);ctx.fillRect(410,317-frame*2,29,2);ctx.globalAlpha=1;}
 if(state==='success'&&!reduced){ctx.fillStyle='#edb84c';for(const [x,y] of [[145,240],[427,260],[90,330]]){ctx.globalAlpha=.35+.5*Math.abs(s);star(ctx,x,y-s*4,5+Math.abs(s)*3);}}
 if(state==='error'){ctx.fillStyle='#cf3458';ctx.font='600 25px Manrope,sans-serif';ctx.fillText('?',366+(reduced?0:s*2),245);}
 if(state==='sleeping'){ctx.fillStyle='#7685a4';ctx.font='500 17px Inter,sans-serif';ctx.globalAlpha=.6;ctx.fillText('z',375,260-(reduced?0:Math.max(0,s)*3));}
 ctx.restore();drawCalls++;drawMs+=(typeof performance==='object'?performance.now():0)-start;return true;
}
function taskFor(snapshot){const all=snapshot?.state?.tasks||[],selected=all.find(t=>t.id===snapshot.selected&&t.agent==='code');return selected||all.find(t=>t.agent==='code'&&['QUEUED','PLANNING','RUNNING','WAITING_FOR_APPROVAL','PAUSED'].includes(t.status))||all.find(t=>t.agent==='code');}
function tick(){if(typeof document!=='object'||!ready||document.hidden||!document.body.classList.contains('mini-open'))return;const snapshot=window.MiniYoeUI?.snapshot(),task=taskFor(snapshot),now=Date.now()/1000,reduced=matchMedia('(prefers-reduced-motion: reduce)').matches,state=selectState(task,now,lastActivity,snapshot?.state?.model?.online!==false),frame=Math.floor(performance.now()/100)%FRAMES;lastTick=performance.now();for(const c of document.querySelectorAll('.mini-animated-fox[data-agent="code"]')){const r=c.getBoundingClientRect();if(!r.width||!r.height||r.bottom<0||r.top>innerHeight||r.right<0||r.left>innerWidth)continue;if(reduced&&c.dataset.codeState===state)continue;draw(c.getContext('2d'),state,frame,{reduced,blink:state!=='idle'||Math.floor(now)%5===0});if(c.dataset.codeState!==state){c.dataset.codeState=state;c.setAttribute('aria-label','Code YOE: '+state);}c.dataset.codeFrame=String(frame);}}
if(typeof document==='object'){atlas=new Image();atlas.onload=()=>{ready=true;tick();};atlas.src='/assets/code-yoe/poses.png';document.addEventListener('pointerdown',()=>lastActivity=Date.now()/1000,{passive:true});document.addEventListener('keydown',()=>lastActivity=Date.now()/1000,{passive:true});setInterval(tick,100);}
return Object.freeze({states,FPS,FRAMES,draw,selectState,taskFor,get ready(){return ready;},stats:()=>({drawCalls,totalDrawMs:drawMs,meanDrawMs:drawCalls?drawMs/drawCalls:0,lastTick,atlasDecodedBytes:1024*1024*4})});
});
