/* Local document creation. Model text is parsed as data, never executed. */
(() => {
 'use strict';
 const cache=new WeakMap();
 const requested=text=>/(?:\b(?:create|make|generate|write|prepare|export|save|produce|build)\b[\s\S]{0,160}\bpdf\b|\bpdf\s+(?:report|document|file)\b|(?:انش|أنش|اصنع|اكتب|جهز|حوّل|حول)[\s\S]{0,160}(?:pdf|بي دي اف))/i.test(text);
 const instructions='This app has a real OFFLINE PDF document creator. The user requested a PDF. Write the complete document content in Markdown, starting with a descriptive # title. The app automatically turns your final response into an actual downloadable PDF. Do not say you cannot create files, do not provide Python or instructions for creating the PDF, and do not claim the file is saved before the app finishes. Use headings, paragraphs, lists and Markdown tables as appropriate. Use chart fences for requested data charts. Do not invent user data. Keep the document concise enough to finish within the response limit.';
 const cleanName=title=>(title.normalize('NFKC').replace(/[<>:"/\\|?*\x00-\x1f]/g,'').trim().slice(0,80)||'YOEAI-document')+'.pdf';
 function inline(node,extra={}){
  if(node.nodeType===3)return {text:node.textContent,...extra};
  const tag=node.nodeName.toLowerCase();let style={...extra};
  if(tag==='strong'||tag==='b')style.bold=true;
  if(tag==='em'||tag==='i')style.italics=true;
  if(tag==='code')style.fontSize=9;
  if(tag==='a'){const href=node.getAttribute('href');if(/^https?:\/\//i.test(href||'')){style.link=href;style.color='#275CB0';style.decoration='underline';}}
  if(tag==='br')return {text:'\n',...style};
  return {text:[...node.childNodes].map(n=>inline(n,style)),...style};
 }
 function definition(content){
  if(typeof content!=='string'||!content.trim())throw Error('The document has no content.');
  if(/[\u0590-\u0dff\u3040-\u9fff]/.test(content))throw Error('This PDF creator currently supports Latin, Greek and Cyrillic text. Ask for an English PDF; other scripts need additional font and layout support.');
  if(content.length>100000)throw Error('This document is too long. Ask for a shorter PDF.');
  const root=YoeVisuals.fragment(content,YoeMarkdown.fragment),blocks=[];
  const title=(root.querySelector('h1,h2')?.textContent||'YOEAI document').slice(0,160);
  const walk=node=>{
   if(node.nodeType===3){if(node.textContent.trim())blocks.push({text:node.textContent,margin:[0,0,0,8]});return;}
   if(node.nodeType!==1)return;
   const tag=node.nodeName.toLowerCase();
   if(node.classList.contains('yoeai-visual')){
    const plot=node.querySelector('.yoeai-visual-plot');
    if(plot?._yoeData){const data=plot._yoeData;blocks.push({text:data.title,bold:true,fontSize:14,margin:[0,12,0,8]});const svg=YoeVisuals.draw(data,720);svg.querySelectorAll('text').forEach(t=>t.setAttribute('fill','#202B3C'));blocks.push({svg:new XMLSerializer().serializeToString(svg),width:490,margin:[0,0,0,12]});const table=node.querySelector('table');if(table)walk(table);}
    return;
   }
   if(tag==='table'){
    const rows=[...node.querySelectorAll('tr')].map(tr=>[...tr.children].map(td=>({text:td.textContent,bold:td.nodeName==='TH',fontSize:9,margin:[3,4,3,4]})));
    if(rows.length){const cols=Math.max(...rows.map(r=>r.length));if(cols>12||rows.length>300)throw Error('The table is too large. Use up to 12 columns and 300 rows.');rows.forEach(row=>{while(row.length<cols)row.push('');});blocks.push({table:{headerRows:node.querySelector('thead')?1:0,widths:Array(cols).fill('*'),body:rows},layout:'lightHorizontalLines',margin:[0,8,0,14]});}return;
   }
   if(/^h[1-6]$/.test(tag)){blocks.push({text:node.textContent,bold:true,fontSize:[24,19,15,13,12,11][Number(tag[1])-1],margin:[0,12,0,8]});return;}
   if(tag==='p'){blocks.push({text:[...node.childNodes].map(n=>inline(n)),margin:[0,0,0,10]});return;}
   if(tag==='pre'){blocks.push({text:node.textContent,fontSize:9,preserveLeadingSpaces:true,margin:[8,8,0,12],color:'#202B3C'});return;}
   if(tag==='ul'||tag==='ol'){blocks.push({[tag]:[...node.children].map(li=>({text:li.textContent})),margin:[0,0,0,12]});return;}
   if(tag==='blockquote'){blocks.push({text:node.textContent,italics:true,margin:[14,4,0,12],color:'#475569'});return;}
   if(tag==='button'||tag==='svg'||tag==='details'||tag==='script'||tag==='style')return;
   [...node.childNodes].forEach(walk);
  };
  [...root.childNodes].forEach(walk);
  if(!blocks.length)throw Error('No printable document content was returned.');
  return {title,doc:{info:{title,creator:'YOEAI local PDF creator'},pageSize:'A4',pageMargins:[44,44,44,48],defaultStyle:{font:'Roboto',fontSize:11,lineHeight:1.35,color:'#172033'},content:blocks,footer:(page,pages)=>({text:page+' / '+pages,alignment:'right',margin:[0,12,44,0],fontSize:9,color:'#64748B'})}};
 }
 async function blobFor(m){
  if(cache.has(m))return cache.get(m);
  const completeVisual=/^\s*(?:\{[\s\S]*\}|```(?:yoeai-visual|visual|chart|diagram)\s*\n[\s\S]*\n```\s*)$/.test(m.content);
  if(completeVisual){const rendered=YoeVisuals.fragment(m.content,YoeMarkdown.fragment),visual=rendered.querySelector('.vie-response');if(visual){const host=document.createElement('div');host.style.cssText='position:fixed;left:-10000px;top:0;width:900px';host.append(rendered);document.body.append(host);try{m.pdfTitle=visual.vieSpec.title;const result=await YoeVisualRenderer.pdf(visual);cache.set(m,Promise.resolve(result));return result;}finally{host.remove();}}}
  const {title,doc}=definition(m.content);m.pdfTitle=title;
  const promise=new Promise((resolve,reject)=>{try{pdfMake.createPdf(doc).getBlob(blob=>resolve(blob));}catch(e){reject(e);}setTimeout(()=>reject(Error('PDF creation timed out. Try a shorter document.')),60000);});
  cache.set(m,promise);try{return await promise;}catch(e){cache.delete(m);throw e;}
 }
 async function finish(m){m.pdfRequested=true;m.pdfError='';try{const blob=await blobFor(m);if(blob.size<100)throw Error('An empty PDF was produced.');m.pdfReady=true;}catch(e){m.pdfReady=false;m.pdfError=e.message;} }
 function card(m,target){
  if(!m.pdfRequested)return;
  const box=document.createElement('section');box.className='yoeai-pdf-card';box.style.cssText='margin:16px 0;padding:16px;border:1px solid var(--border,#33435d);border-radius:12px;white-space:normal';
  const label=document.createElement('p');label.textContent=m.pdfError?'PDF creation failed: '+m.pdfError:(m.pdfTitle||'Your document')+' — PDF ready';
  const button=document.createElement('button');button.type='button';button.textContent=m.pdfError?'Retry PDF creation':'Download PDF';
  button.onclick=async()=>{button.disabled=true;label.textContent='Preparing PDF…';try{const blob=await blobFor(m);const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=cleanName(m.pdfTitle||'YOEAI-document');a.click();setTimeout(()=>URL.revokeObjectURL(url),60000);label.textContent='PDF ready. Choose where to save it.';button.textContent='Download PDF';m.pdfError='';}catch(e){label.textContent='PDF creation failed: '+e.message;button.textContent='Retry PDF creation';}finally{button.disabled=false;}};
  box.append(label,button);target.append(box);
 }
 window.YoePdf=Object.freeze({requested,instructions,definition,finish,card,blobFor});
})();
