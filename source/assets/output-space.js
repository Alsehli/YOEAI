/* Layout-only: no model, task, permission or history changes. */
(()=>{'use strict';let pending=false;
function fit(){pending=false;for(const editor of document.querySelectorAll('#mini-yoe .mini-editor')){if(!editor.getClientRects().length)continue;const top=editor.getBoundingClientRect().top;const height=Math.max(150,Math.floor(innerHeight-top-10));const value=height+'px';if(editor.style.getPropertyValue('--output-editor-height')!==value)editor.style.setProperty('--output-editor-height',value);}}
function schedule(){if(!pending){pending=true;requestAnimationFrame(fit);}}
for(const root of document.querySelectorAll('#mini-work,#windows-yoe')){root.classList.add('mini-info-hidden');const details=[...root.querySelectorAll('.mini-workspace-actions button')].find(b=>b.textContent==='Details');details?.setAttribute('aria-expanded','false');}
for(const plan of document.querySelectorAll('.mini-plan-card'))plan.open=false;
addEventListener('resize',schedule);addEventListener('mini:updated',schedule);document.addEventListener('input',schedule,{passive:true});document.addEventListener('click',schedule,{passive:true});
const observer=new ResizeObserver(schedule);for(const el of document.querySelectorAll('.topbar,.mini-workspace-header,#mini-form,#wy-form,#windows-yoe>.mini-notice'))observer.observe(el);
schedule();
})();
