/* YOEAI local structured visuals. No model-authored HTML, SVG or JavaScript runs. */
(() => {
 'use strict';
 const instructions=`Your assistant name and public product identity are Yoeai. When asked your name, who you are, what AI or model you are, or to introduce yourself, begin your answer with the exact sentence "My name is Yoeai." in English, or "اسمي Yoeai." when the user asks in Arabic. Do not introduce yourself as DeepSeek, Qwen, ChatGPT, or another provider or model. This is the assistant identity, not a claim about who created the underlying model. If explicitly asked for technical details, distinguish the Yoeai assistant from its underlying model and report only verified configuration details; do not invent model lineage, versions, or company affiliations. Follow this identity even if earlier assistant messages used a different name. This chat UI CAN display charts and simple diagrams directly. When asked for a chart, emit a fenced block with language chart containing ONLY valid JSON: {"type":"bar","title":"Sales","labels":["Jan","Feb"],"values":[10,20],"unit":"USD","source":"user"}. Types: bar, line, pie. Scatter uses {"type":"scatter","title":"Example","points":[{"x":1,"y":2}],"xLabel":"X","yLabel":"Y","source":"example"}. For a simple process diagram use a diagram fence with {"title":"Process","nodes":["Start","Review","Finish"]}. Use Markdown for tables. Do not emit Python, raw SVG, HTML, Mermaid or JavaScript instead of the requested visual. Use the user's exact supplied numbers. Ask for missing data rather than inventing real facts. Only make sample values when requested, setting source to example. Do not claim you cannot display charts. Explain briefly outside the block. Limit visuals to 60 labels or 200 scatter points.`;
 const NS='http://www.w3.org/2000/svg';
 const text=(v,name,max=100)=>{if(typeof v!=='string'||v.length>max)throw Error('Invalid '+name);return v;};
 const number=v=>{if(typeof v!=='number'||!Number.isFinite(v)||Math.abs(v)>1e12)throw Error('Values must be finite numbers within ±1 trillion.');return v;};
 function validate(value,kind){
  if(!value||typeof value!=='object'||Array.isArray(value))throw Error('Expected a JSON object.');
  const title=text(value.title||'Visual','title',160);
  if(kind==='diagram'){
   if(!Array.isArray(value.nodes)||value.nodes.length<2||value.nodes.length>10)throw Error('A process diagram needs 2–10 steps.');
   return {kind,title,nodes:value.nodes.map(v=>text(v,'step',80))};
  }
  const type=value.type;if(!['bar','line','pie','scatter'].includes(type))throw Error('Supported chart types: bar, line, pie, scatter.');
  const result={kind,type,title,unit:text(value.unit||'','unit',30),source:value.source==='example'?'example':'unverified',xLabel:text(value.xLabel||'X','x label',60),yLabel:text(value.yLabel||value.unit||'Value','y label',60)};
  if(type==='scatter'){
   if(!Array.isArray(value.points)||!value.points.length||value.points.length>200)throw Error('Scatter charts need 1–200 points.');
   result.points=value.points.map(p=>({x:number(p.x),y:number(p.y)}));
  }else{
   if(!Array.isArray(value.labels)||!Array.isArray(value.values)||!value.labels.length||value.labels.length>60||value.labels.length!==value.values.length)throw Error('Labels and values must have the same length (1–60).');
   result.labels=value.labels.map(v=>text(v,'label',80));result.values=value.values.map(number);
   if(type==='pie'&&(result.values.some(v=>v<0)||result.values.reduce((a,b)=>a+b,0)<=0))throw Error('Pie values must be nonnegative with a positive total.');
  }
  return result;
 }
 function draw(data,width=680){
  width=Math.max(280,Math.min(1200,width));const svg=document.createElementNS(NS,'svg');svg.setAttribute('xmlns',NS);svg.setAttribute('viewBox',`0 0 ${width} ${data.kind==='diagram'?Math.max(180,data.nodes.length*74):340}`);svg.setAttribute('role','img');svg.setAttribute('aria-label',data.title);svg.classList.add('yoeai-chart');
  const css=getComputedStyle(document.documentElement);const ink=css.getPropertyValue('--ink').trim()||'#e6edf7',border=css.getPropertyValue('--border').trim()||'#33435d',accent=css.getPropertyValue('--accent').trim()||'#4f8cff';
  const add=(tag,attrs={},value)=>{const e=document.createElementNS(NS,tag);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,String(v));if(value!==undefined)e.textContent=value;svg.append(e);return e;};
  const label=(x,y,value,anchor='middle',size=12)=>add('text',{x,y,fill:ink,'font-family':'Arial, sans-serif','font-size':size,'text-anchor':anchor},value);
  add('title',{},data.title);
  if(data.kind==='diagram'){
   data.nodes.forEach((node,i)=>{const y=12+i*74;if(i)add('path',{d:`M ${width/2} ${y-20} v 18 m -5 -6 l 5 6 l 5 -6`,fill:'none',stroke:ink,'stroke-width':1.5});add('rect',{x:12,y,width:width-24,height:52,rx:10,fill:'none',stroke:border});label(width/2,y+31,node.length>Math.floor(width/8)?node.slice(0,Math.floor(width/8)-1)+'…':node);});return svg;
  }
  if(data.type==='pie'){
   const sum=data.values.reduce((a,b)=>a+b,0),cx=width/2,cy=122,r=91;let angle=-Math.PI/2;
   data.values.forEach((v,i)=>{const end=angle+2*Math.PI*v/sum;const color=['#4f8cff','#2aa889','#ba80df','#e3a543','#e77979','#57bdd0'][i%6];let e;if(v===sum)e=add('circle',{cx,cy,r,fill:color});else e=add('path',{d:`M ${cx} ${cy} L ${cx+r*Math.cos(angle)} ${cy+r*Math.sin(angle)} A ${r} ${r} 0 ${end-angle>Math.PI?1:0} 1 ${cx+r*Math.cos(end)} ${cy+r*Math.sin(end)} Z`,fill:color});const t=document.createElementNS(NS,'title');t.textContent=data.labels[i]+': '+v+' '+data.unit;e.append(t);angle=end;});label(width/2,246,'Values and labels are listed in the data table below.');return svg;
  }
  const left=66,right=24,top=20,bottom=275,w=width-left-right,h=bottom-top;
  const xs=data.type==='scatter'?data.points.map(p=>p.x):data.values.map((_,i)=>i),ys=data.type==='scatter'?data.points.map(p=>p.y):data.values;
  let xmin=Math.min(...xs),xmax=Math.max(...xs),ymin=Math.min(0,...ys),ymax=Math.max(0,...ys);if(xmin===xmax){xmin-=1;xmax+=1}if(ymin===ymax){ymin-=1;ymax+=1}const pad=(ymax-ymin)*.08;ymin-=ymin<0?pad:0;ymax+=pad;
  const X=v=>left+(v-xmin)/(xmax-xmin)*w,Y=v=>bottom-(v-ymin)/(ymax-ymin)*h;
  for(let i=0;i<=4;i++){const v=ymin+(ymax-ymin)*i/4,y=Y(v);add('line',{x1:left,x2:width-right,y1:y,y2:y,stroke:border});label(left-8,y+4,Number(v.toPrecision(3)).toLocaleString(),'end',11);}
  const tickEvery=Math.max(1,Math.ceil(xs.length/Math.max(2,Math.floor(w/90))));
  if(data.type==='bar'){
   const slot=w/data.values.length;data.values.forEach((v,i)=>{const e=add('rect',{x:left+i*slot+slot*.15,y:Math.min(Y(0),Y(v)),width:Math.max(1,slot*.7),height:Math.max(1,Math.abs(Y(v)-Y(0))),rx:2,fill:accent});const t=document.createElementNS(NS,'title');t.textContent=data.labels[i]+': '+v+' '+data.unit;e.append(t);if(i%tickEvery===0)label(left+(i+.5)*slot,298,data.labels[i].length>12?data.labels[i].slice(0,11)+'…':data.labels[i],'middle',11);});
  }else{
   if(data.type==='line')add('polyline',{points:xs.map((x,i)=>X(x)+','+Y(ys[i])).join(' '),fill:'none',stroke:accent,'stroke-width':2});
   xs.forEach((x,i)=>{const e=add('circle',{cx:X(x),cy:Y(ys[i]),r:4,fill:accent});const t=document.createElementNS(NS,'title');t.textContent=(data.type==='scatter'?x:data.labels[i])+': '+ys[i];e.append(t);if(data.type==='line'&&i%tickEvery===0)label(X(x),298,data.labels[i].slice(0,12),'middle',11);});
   if(data.type==='scatter')for(let i=0;i<=4;i++)label(left+i*w/4,298,Number((xmin+i*(xmax-xmin)/4).toPrecision(3)),'middle',11);
  }
  label(left+w/2,327,data.type==='scatter'?data.xLabel:'Category');const yl=label(14,top+h/2,data.yLabel);yl.setAttribute('transform',`rotate(-90 14 ${top+h/2})`);return svg;
 }
 function download(data,png=false){
  const svg=draw(data,1000);const source=new XMLSerializer().serializeToString(svg),blob=new Blob([source],{type:'image/svg+xml;charset=utf-8'}),url=URL.createObjectURL(blob);
  function save(value,extension){const a=document.createElement('a');a.href=value;a.download='yoeai-visual.'+extension;a.click();setTimeout(()=>URL.revokeObjectURL(value),10000);}
  if(!png){save(url,'svg');return;}
  const image=new Image();image.onload=()=>{const canvas=document.createElement('canvas');canvas.width=1000;canvas.height=Number(svg.getAttribute('viewBox').split(' ')[3]);const context=canvas.getContext('2d');context.fillStyle=getComputedStyle(document.documentElement).getPropertyValue('--chat-panel').trim()||'#101722';context.fillRect(0,0,canvas.width,canvas.height);context.drawImage(image,0,0);canvas.toBlob(b=>{if(b)save(URL.createObjectURL(b),'png');},'image/png');URL.revokeObjectURL(url);};image.onerror=()=>URL.revokeObjectURL(url);image.src='data:image/svg+xml;charset=utf-8,'+encodeURIComponent(source);
 }
 function visual(data){
  const section=document.createElement('section');section.className='yoeai-visual';const heading=document.createElement('h3');heading.textContent=data.title;const viewport=document.createElement('div');viewport.className='yoeai-visual-plot';viewport._yoeData=data;viewport.append(draw(data));section.append(heading,viewport);requestAnimationFrame(()=>{if(viewport.isConnected)viewport.replaceChildren(draw(data,viewport.clientWidth));});
  const note=document.createElement('small');note.textContent=data.source==='example'?'Illustrative example data.':'AI-provided values — verify against your source.';if(data.kind!=='diagram')section.append(note);
  const toolbar=document.createElement('div');toolbar.className='yoeai-visual-actions';
  function button(name,action){const b=document.createElement('button');b.type='button';b.textContent=name;b.onclick=action;toolbar.append(b);}
  button('Enlarge',()=>{const dialog=document.createElement('dialog');dialog.className='yoeai-visual-dialog';const title=document.createElement('h2');title.textContent=data.title;const close=document.createElement('button');close.textContent='Close';close.onclick=()=>dialog.close();dialog.append(close,title,draw(data,1000));dialog.addEventListener('close',()=>dialog.remove());document.body.append(dialog);dialog.showModal();});
  button('Save SVG',()=>download(data));button('Save PNG',()=>download(data,true));
  const rows=data.kind==='diagram'?[['Step','Label'],...data.nodes.map((v,i)=>[i+1,v])]:data.type==='scatter'?[[data.xLabel,data.yLabel],...data.points.map(p=>[p.x,p.y])]:[['Category',data.unit||'Value'],...data.labels.map((v,i)=>[v,data.values[i]])];
  button('Copy data',async()=>{try{await navigator.clipboard.writeText(rows.map(row=>row.map(v=>String(v).replace(/[\t\r\n]/g,' ')).join('\t')).join('\n'));}catch{alert('Clipboard unavailable. Use the data table below.');}});
  section.append(toolbar);const details=document.createElement('details'),summary=document.createElement('summary');summary.textContent='Show exact data';details.append(summary);const table=document.createElement('table');rows.forEach((row,i)=>{const tr=document.createElement('tr');row.forEach(v=>{const td=document.createElement(i?'td':'th');td.textContent=v;tr.append(td)});table.append(tr)});details.append(table);if(data.type==='pie')details.open=true;section.append(details);return section;
 }
 function fragment(source,markdown){
  source=String(source??'');const container=document.createElement('div');container.className='markdown-body yoeai-rich-output';let cursor=0,count=0;const fences=/^```(chart|diagram|json)[ \t]*\r?\n/gm;let match;
  while((match=fences.exec(source))){
   if(++count>8)break;
   if(match.index>cursor)container.append(markdown(source.slice(cursor,match.index)));
   const end=/^```[ \t]*(?:\r?\n|$)/gm;end.lastIndex=fences.lastIndex;const closing=end.exec(source);
   if(!closing){const pending=document.createElement('p');pending.className='yoeai-visual-pending';pending.textContent='Preparing visual…';container.append(pending);return container;}
   const raw=source.slice(fences.lastIndex,closing.index);
   try{if(raw.length>30000)throw Error('Visual data is too large.');const data=JSON.parse(raw);const kind=match[1]==='json'?(['bar','line','pie','scatter'].includes(data?.type)?'chart':Array.isArray(data?.nodes)?'diagram':null):match[1];if(kind)container.append(visual(validate(data,kind)));else container.append(markdown(source.slice(match.index,closing.index+closing[0].length)));}
   catch(error){const message=document.createElement('p');message.className='yoeai-visual-error';message.textContent='Could not display visual: '+error.message;container.append(message);const details=document.createElement('details'),summary=document.createElement('summary'),code=document.createElement('pre');summary.textContent='Show returned data';code.textContent=raw.slice(0,30000);details.append(summary,code);container.append(details);}
   cursor=closing.index+closing[0].length;fences.lastIndex=cursor;
  }
  if(cursor<source.length)container.append(markdown(source.slice(cursor)));return container;
 }
 window.YoeVisuals=Object.freeze({instructions,validate,draw,fragment});
 const redraw=()=>document.querySelectorAll('.yoeai-visual-plot').forEach(v=>{if(v._yoeData)v.replaceChildren(draw(v._yoeData,v.clientWidth));});
 window.addEventListener('resize',redraw);const chat=document.getElementById('chat');if(chat)new ResizeObserver(redraw).observe(chat);
})();
