/* Approved fox atlas + original vector accessories. No new animal artwork or model calls. */
(()=>{'use strict';
const profiles={
 research:{idle:{row:2,frames:[0,0,1,1,0,2,0,7],fps:1.2},working:{row:1,frames:[0,1,2,3,2,1],fps:1.6},phase:.35},
 code:{idle:{row:1,frames:[0,0,1,2,1,0],fps:.9},working:{row:1,frames:[4,5,6,5,4,3],fps:2.2},phase:1.7},
 windows:{idle:{row:3,frames:[0,1,2,3,4,5,6,7,7,7],fps:1.1},working:{row:0,frames:[0,1,2,3,4,5,6,7],fps:2.4},phase:2.9},
 hero:{idle:{row:2,frames:[0,0,0,2,0,1,0,0],fps:.8},working:{row:1,frames:[0,1,2,1],fps:1.2},phase:0}
};
function pose(agent,status,seconds,reduced=false){
 const profile=profiles[agent]||profiles.hero,working=['PLANNING','RUNNING'].includes(status);
 let spec=working?profile.working:profile.idle;
 if(status==='COMPLETED')spec={row:3,frames:agent==='code'?[0,1,2,1,0]:agent==='research'?[0,1,2,3,2,1]:[3,4,5,6,7],fps:1.2};
 const t=reduced?0:seconds+profile.phase,frame=spec.frames[reduced?0:Math.floor(t*spec.fps)%spec.frames.length];
 return {row:spec.row,frame,dx:reduced?0:agent==='windows'?Math.sin(t*.85)*2:agent==='research'?Math.sin(t*.5):0,dy:reduced?0:Math.sin(t*(agent==='code'?1.8:.9))*(working?1.2:.65),working,accessory:agent};
}
function rounded(ctx,x,y,w,h,r){ctx.beginPath();ctx.roundRect(x,y,w,h,r);}
function accessories(ctx,agent,seconds,reduced=false,working=false){
 ctx.save();ctx.lineCap='round';ctx.lineJoin='round';
 if(agent==='research'){
  // Blue handled lens, positioned beside the paw; never over the fox's eyes.
  ctx.translate(69,221);ctx.rotate(reduced?-.12:Math.sin(seconds*.65)*.07-.12);
  ctx.strokeStyle='#194f9b';ctx.lineWidth=10;ctx.beginPath();ctx.moveTo(-16,26);ctx.lineTo(-34,57);ctx.stroke();
  ctx.fillStyle='#bcefff66';ctx.strokeStyle='#3c9af4';ctx.lineWidth=5;ctx.beginPath();ctx.arc(0,0,31,0,Math.PI*2);ctx.fill();ctx.stroke();
  ctx.strokeStyle='#fff';ctx.lineWidth=3;ctx.beginPath();ctx.arc(0,0,24,Math.PI*1.12,Math.PI*1.55);ctx.stroke();
  ctx.fillStyle='#3186d4';ctx.font='600 11px Inter,sans-serif';ctx.fillText('?',-4,5);
 }else if(agent==='code'){
  // A small red headset and laptop distinguish the code fox without recolouring its fur.
  ctx.strokeStyle='#d92e58';ctx.lineWidth=7;ctx.beginPath();ctx.arc(182,173,53,Math.PI*1.05,Math.PI*1.94);ctx.stroke();
  ctx.fillStyle='#d92e58';rounded(ctx,125,164,15,31,7);ctx.fill();rounded(ctx,226,164,13,29,6);ctx.fill();
  ctx.strokeStyle='#812647';ctx.lineWidth=3;ctx.beginPath();ctx.moveTo(232,189);ctx.quadraticCurveTo(247,206,235,210);ctx.stroke();
  const grad=ctx.createLinearGradient(40,230,170,290);grad.addColorStop(0,'#58314e');grad.addColorStop(1,'#17243e');ctx.fillStyle=grad;ctx.strokeStyle='#f17292';ctx.lineWidth=2;
  rounded(ctx,37,229,126,66,8);ctx.fill();ctx.stroke();ctx.fillStyle='#ff658c';ctx.font='600 24px monospace';ctx.fillText('</>',76,270);
  ctx.fillStyle='#d8def0';ctx.beginPath();ctx.moveTo(34,293);ctx.lineTo(170,293);ctx.lineTo(184,302);ctx.lineTo(27,302);ctx.closePath();ctx.fill();
  if(working&&!reduced){ctx.fillStyle=Math.floor(seconds*3)%2?'#ff9bb4':'#f0527f';rounded(ctx,105,297,22,3,1);ctx.fill();}
 }else if(agent==='windows'){
  const drift=reduced?0:Math.sin(seconds*.8)*3;ctx.translate(0,drift);
  ctx.fillStyle='#cff0ffb8';ctx.strokeStyle='#55b6ef';ctx.lineWidth=2;rounded(ctx,207,200,101,80,10);ctx.fill();ctx.stroke();
  ctx.fillStyle='#367fe1';for(const [x,y] of [[220,216],[240,216],[220,236],[240,236]]){rounded(ctx,x,y,15,15,2);ctx.fill();}
  ctx.strokeStyle='#8d73f2';ctx.lineWidth=3;ctx.beginPath();ctx.moveTo(271,223);ctx.lineTo(293,223);ctx.moveTo(271,233);ctx.lineTo(286,233);ctx.stroke();
  ctx.strokeStyle='#fff';ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(220,266);ctx.lineTo(294,266);ctx.stroke();
  ctx.fillStyle='#7eabed99';rounded(ctx,24,187,42,34,6);ctx.fill();ctx.fillStyle='#fff';ctx.font='600 18px monospace';ctx.fillText('✓',36,210);
 }
 ctx.restore();
}
window.MiniFoxVariants={pose,accessories,profiles};
})();
