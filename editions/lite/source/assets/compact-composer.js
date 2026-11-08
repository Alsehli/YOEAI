/* Keep short prompts compact; grow only as content needs more lines. */
(()=>{'use strict';
 const prompt=document.getElementById('prompt');if(!prompt)return;
 const style=document.createElement('style');style.textContent=`
 .composer{padding:8px 12px;align-items:center;gap:12px}
 .composer #prompt{min-height:28px;height:28px;max-height:min(180px,25dvh);resize:none;overflow-y:hidden;padding:2px 0;line-height:24px;box-sizing:border-box}
 .composer .composer-actions{gap:4px;align-self:flex-end}
 .composer .composer-actions button{min-height:30px;height:30px;padding:4px 12px}
 .composer-bottom{padding-top:6px;padding-bottom:4px}
 `;document.head.append(style);prompt.rows=1;
 let geometryKey='',pending=false;
 function fit(){const key=[prompt.value,innerHeight,prompt.clientWidth,document.documentElement.getAttribute('style'),document.documentElement.dataset.theme].join('|');if(key===geometryKey)return;geometryKey=key;const max=Math.max(28,Math.min(180,innerHeight*.25));prompt.style.height='28px';const needed=prompt.scrollHeight;prompt.style.height=Math.min(max,Math.max(28,needed))+'px';prompt.style.overflowY=needed>max?'auto':'hidden';}
 function schedule(){if(pending)return;pending=true;requestAnimationFrame(()=>{pending=false;fit();});}
 prompt.addEventListener('input',schedule);addEventListener('resize',schedule);
 // Existing send, suggestion and image controls can set the value directly.
 document.addEventListener('click',()=>schedule());
 new MutationObserver(()=>schedule()).observe(document.getElementById('send'),{attributes:true,attributeFilter:['disabled']});
 new MutationObserver(()=>schedule()).observe(document.documentElement,{attributes:true,attributeFilter:['style','data-theme']});
 if(document.fonts)document.fonts.ready.then(()=>{geometryKey='';schedule();});fit();
})();
