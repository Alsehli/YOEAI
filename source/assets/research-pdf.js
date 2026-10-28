/* Local formatted reports. Only sanitized data reaches the native print engine. */
(()=>{'use strict';
async function reportBlob(content){
 if(typeof content!=='string'||!content.trim())throw Error('This report has no content.');
 const root=YoeVisuals.fragment(content,YoeMarkdown.fragment),host=document.createElement('div');host.append(root);
 // Isolate mixed-script cell text from an RTL table's surrounding direction.
 for(const cell of host.querySelectorAll('th,td'))if(/[A-Za-z]/.test(cell.textContent)&&/[\u0590-\u08ff]/.test(cell.textContent)){cell.prepend(document.createTextNode('\u2068'));cell.append(document.createTextNode('\u2069'));}
 // Preserve existing generated charts as inert PNGs; never pass scripts to print.
 for(const svg of [...host.querySelectorAll('svg')]){
  if(!window.YoeVisualExport?.png)continue;
  const copy=svg.cloneNode(true);copy.querySelectorAll('text').forEach(t=>t.setAttribute('fill','#172033'));
  try{const png=await YoeVisualExport.png(new XMLSerializer().serializeToString(copy),1400);const url=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result);r.onerror=reject;r.readAsDataURL(png);});const image=document.createElement('img');image.src=url;svg.replaceWith(image);}catch{svg.remove();}
 }
 for(const canvas of [...host.querySelectorAll('canvas')]){try{const img=document.createElement('img');img.src=canvas.toDataURL('image/png');canvas.replaceWith(img);}catch{canvas.remove();}}
 host.querySelectorAll('button,script,style,iframe,input,select,textarea').forEach(e=>e.remove());
 const title=host.querySelector('h1,h2')?.textContent||'Mini YOE report';
 const response=await fetch('/reports/pdf',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title,html:host.innerHTML})});
 if(!response.ok){const error=await response.json().catch(()=>({}));throw Error(error.error||'The formatted report could not be exported.');}
 const blob=await response.blob();if(blob.size<100)throw Error('An empty PDF was returned.');return blob;
}
window.YoeReportPdf=Object.freeze({blobFor:reportBlob});
})();
