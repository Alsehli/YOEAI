/* Presentation-only mascot. Reads existing UI state; never changes inference or history. */
(() => {
  'use strict';
  const modes = {
    startup: {row:0, fps:5, label:'Starting YOEAI'},
    initializing: {row:0, fps:5, label:'Loading the model'},
    generating: {row:1, fps:4, label:'Thinking'},
    processing: {row:1, fps:4, label:'Working'},
    success: {row:3, fps:4, label:'All done'},
    idle: {row:2, fps:2, label:'Ready when you are'},
    error: {row:2, fps:2, label:'Needs attention'}
  };
  let mode='startup', since=performance.now(), wasBusy=false, wasReady=false, happyUntil=0, background=false, frame=-1;
  const atlas=new Image();atlas.src='/assets/mascot/fox-atlas.png';atlas.onload=()=>paint(performance.now(),true);
  const reduced=matchMedia('(prefers-reduced-motion: reduce)');
  const badge=document.querySelector('.private-badge');
  if (badge) {
    badge.classList.add('fox-companion');
    badge.replaceChildren();
    const fox=document.createElement('span');fox.className='fox-sprite fox-small';fox.setAttribute('aria-hidden','true');
    const label=document.createElement('span');label.id='fox-status';label.setAttribute('role','status');label.setAttribute('aria-live','polite');
    badge.append(fox,label);
  }
  const welcomeObserver=new MutationObserver(() => {
    const image=document.querySelector('img.welcome-mascot');
    if(image){const fox=document.createElement('div');fox.className='welcome-mark welcome-mascot fox-sprite';fox.setAttribute('aria-hidden','true');image.replaceWith(fox);paint(performance.now(),true);}
  });
  welcomeObserver.observe(document.getElementById('chat'),{childList:true,subtree:true});
  // Also convert an existing empty state without rebuilding chat/history.
  const welcome=document.querySelector('img.welcome-mascot');
  if(welcome){const fox=document.createElement('div');fox.className='welcome-mark welcome-mascot fox-sprite';fox.setAttribute('aria-hidden','true');welcome.replaceWith(fox);}
  function setMode(next,now){
    if(next===mode)return;
    mode=next;since=now;frame=-1;document.documentElement.dataset.foxState=mode;
    const label=document.getElementById('fox-status');if(label)label.textContent=modes[mode].label;
  }
  function observe(now){
    const active=typeof busy!=='undefined' && busy;
    const ready=document.getElementById('status')?.textContent==='Ready';
    const error=document.getElementById('error')?.textContent?.trim();
    if(wasBusy && !active && !error)happyUntil=now+2200;
    if(active)setMode(typeof responseController!=='undefined' && responseController?'generating':'processing',now);
    else if(background)setMode('processing',now);
    else if(error && error!=='Response stopped.')setMode('error',now);
    else if(!ready)setMode(wasReady?'initializing':'startup',now);
    else if(now<happyUntil)setMode('success',now);
    else setMode('idle',now);
    wasBusy=active;wasReady=ready||wasReady;
  }
  function paint(now,force=false){
    const item=modes[mode];const next=reduced.matches?0:Math.floor((now-since)/1000*item.fps)%8;
    if(next===frame && !force)return;frame=next;
    const rect=window.YoeFoxAtlas?.rows[item.row]?.[next];if(!rect || !atlas.complete || !atlas.naturalWidth)return;
    for(let fox of document.querySelectorAll('.fox-sprite')){
      if(fox.tagName!=='CANVAS'){
        const canvas=document.createElement('canvas');canvas.width=canvas.height=256;canvas.className=fox.className;canvas.setAttribute('aria-hidden','true');canvas.style.backgroundImage='none';fox.replaceWith(canvas);fox=canvas;
      }
      const [x,y,w,h]=rect;const scale=Math.min(190/h,220/w);const dw=w*scale,dh=h*scale;const context=fox.getContext('2d');
      context.clearRect(0,0,256,256);context.drawImage(atlas,x,y,w,h,(256-dw)/2,232-dh,dw,dh);
      fox.dataset.frame=String(next);fox.dataset.row=String(item.row);
    }
  }
  addEventListener('yoeai:visual-processing',event=>{background=event.detail?.active===true;});
  document.documentElement.dataset.foxState=mode;
  if(document.getElementById('fox-status'))document.getElementById('fox-status').textContent=modes[mode].label;
  // A lightweight visual clock; pauses drawing for hidden windows.
  setInterval(()=>{const now=performance.now();observe(now);if(!document.hidden)paint(now);},80);
  paint(performance.now(),true);
})();
