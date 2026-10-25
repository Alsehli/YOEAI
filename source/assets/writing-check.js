/* Browser-style local spelling. No model calls, switch, check button or waiting row. */
(()=>{'use strict';const fields=[];
function setup(input){
 if(!input)return;input.spellcheck=false;
 const wrap=document.createElement('div');wrap.className='writing-wrap';input.before(wrap);wrap.append(input);
 const mirror=document.createElement('div');mirror.className='writing-mirror';mirror.setAttribute('aria-hidden','true');
 const popup=document.createElement('section');popup.className='writing-suggestions';popup.setAttribute('aria-label','Spelling suggestions');popup.hidden=true;wrap.append(mirror,popup);
 let edits=[],snapshot='',revision=0,timer,controller,composing=false;const ignored=new Set();
 function sync(){const c=getComputedStyle(input);for(const name of ['font','fontFamily','fontSize','fontWeight','fontStyle','lineHeight','letterSpacing','padding','borderWidth','borderStyle','boxSizing','textAlign','direction','tabSize','wordSpacing','textIndent','unicodeBidi','wordBreak','overflowWrap'])mirror.style[name]=c[name];mirror.style.width=input.offsetWidth+'px';mirror.scrollTop=input.scrollTop;mirror.scrollLeft=input.scrollLeft;}
 function draw(){mirror.replaceChildren();let offset=0;for(const e of edits){mirror.append(document.createTextNode(input.value.slice(offset,e.start)));const mark=document.createElement('mark');mark.textContent=e.original;mirror.append(mark);offset=e.end;}mirror.append(document.createTextNode(input.value.slice(offset)+'\n'));sync();}
 function invalidate(){revision++;clearTimeout(timer);controller?.abort();controller=null;edits=[];snapshot='';popup.hidden=true;draw();}
 async function check(){
  if(composing||input.disabled||!input.getClientRects().length||!input.value.trim()||input.value.length>8000)return;
  const text=input.value,version=revision;controller=new AbortController();const signal=controller.signal;
  try{const r=await fetch('/writing/spell',{method:'POST',signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({text})});if(!r.ok)return;const v=await r.json();if(version!==revision||input.value!==text||v.status!=='checked')return;snapshot=text;let end=0;edits=(v.edits||[]).filter(e=>Number.isInteger(e.start)&&Number.isInteger(e.end)&&e.start>=0&&e.end>e.start&&e.end<=text.length&&text.slice(e.start,e.end)===e.original&&!ignored.has(e.original.toLocaleLowerCase())).sort((a,b)=>a.start-b.start).filter(e=>{if(e.start<end)return false;end=e.end;return true;});draw();}catch(e){/* A missing OS language provider must not delay typing or invoke the model. */}
 }
 function schedule(){clearTimeout(timer);if(!composing)timer=setTimeout(check,120);}
 function show(e,event){
  if(input.value!==snapshot)return;popup.replaceChildren();const heading=document.createElement('strong');heading.textContent=e.original;popup.append(heading);
  for(const word of e.suggestions||[]){if(typeof word!=='string'||word.length>150)continue;const option=document.createElement('button');option.type='button';option.textContent=word||'Remove';option.onmousedown=x=>x.preventDefault();option.onclick=()=>{if(input.value!==snapshot){invalidate();return;}input.focus();input.setRangeText(word,e.start,e.end,'end');input.dispatchEvent(new Event('input',{bubbles:true}));};popup.append(option);}
  const ignore=document.createElement('button');ignore.type='button';ignore.className='writing-ignore';ignore.textContent='Ignore';ignore.onclick=()=>{ignored.add(e.original.toLocaleLowerCase());edits=edits.filter(x=>!ignored.has(x.original.toLocaleLowerCase()));popup.hidden=true;draw();input.focus();};popup.append(ignore);
  const rect=wrap.getBoundingClientRect(),x=event?.clientX?event.clientX-rect.left:0;popup.style.left=Math.max(0,Math.min(x,Math.max(0,rect.width-250)))+'px';popup.hidden=false;
 }
 input.addEventListener('input',()=>{invalidate();schedule();});input.addEventListener('focus',()=>{if(!edits.length)schedule();});input.addEventListener('scroll',()=>{popup.hidden=true;sync();});
 input.addEventListener('compositionstart',()=>{composing=true;invalidate();});input.addEventListener('compositionend',()=>{composing=false;input.dispatchEvent(new Event('input'));});
 for(const name of ['click','contextmenu'])input.addEventListener(name,event=>{const edit=edits.find(x=>input.selectionStart>=x.start&&input.selectionStart<=x.end);if(edit){if(name==='contextmenu')event.preventDefault();show(edit,event);}else popup.hidden=true;});
 input.addEventListener('keydown',event=>{if(event.key==='Escape')popup.hidden=true;});document.addEventListener('pointerdown',event=>{if(!wrap.contains(event.target))popup.hidden=true;});
 new ResizeObserver(sync).observe(input);new MutationObserver(()=>{if(!input.value&&(snapshot||edits.length))invalidate();sync();}).observe(input,{attributes:true,attributeFilter:['style','disabled']});new MutationObserver(sync).observe(document.documentElement,{attributes:true,attributeFilter:['style','data-theme']});document.fonts?.ready.then(sync);sync();
 fields.push({stop(){clearTimeout(timer);controller?.abort();revision++;popup.hidden=true;}});
}
for(const id of ['prompt','mini-objective','wy-objective'])setup(document.getElementById(id));
window.YoeWriting={async wait(){for(const field of fields)field.stop();}};
})();
