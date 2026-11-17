/* YOEAI shared bidirectional presentation. Never rewrites model/editor values. */
(function(root,factory){const api=factory(root);if(typeof module==='object'&&module.exports)module.exports=api;else root.YoeBidi=api;})(typeof window==='object'?window:globalThis,root=>{
 'use strict';
 const letter=/\p{Letter}/u,rtlLetter=/[\p{Script=Arabic}\p{Script=Hebrew}\p{Script=Syriac}\p{Script=Thaana}]/u;
 const technical=/(?:https?:\/\/|www\.)[^\s<>"'،؛؟\u0600-\u06ff]+|(?:[A-Za-z]:[\\/]|\\\\)[^\r\n<>"'،؛؟\u0600-\u06ff]+|[+\-][0-9\u0660-\u0669\u06f0-\u06f9]+(?:[.,٫٬:/][0-9\u0660-\u0669\u06f0-\u06f9]+)*[%٪]?|[A-Za-z0-9](?:[A-Za-z0-9_@.+%:#~?&=\/\\()\[\],;!-]*[A-Za-z0-9_@+%#~?&=\/\\)\]])?(?:[ \t]+[A-Za-z0-9][A-Za-z0-9_@.+%:#~?&=\/\\()\[\],;!-]*)*|[\u0660-\u0669\u06f0-\u06f9]+(?:[.,٫٬:/%+-][0-9\u0660-\u0669\u06f0-\u06f9]+)*/gu;
 function direction(value,fallback='ltr'){for(const c of String(value??'')){if(letter.test(c))return rtlLetter.test(c)?'rtl':'ltr';}return fallback;}
 function ranges(value){
  const text=String(value??''),result=[];
  for(const m of text.matchAll(technical)){
   let value=m[0].trimEnd(),index=m.index;value=value.replace(/[.,;:!?]+$/u,'');
   for(const [open,close] of [['(',')'],['[',']'],['{','}']]){
    const count=c=>[...value].filter(x=>x===c).length;
    while(value.endsWith(close)&&count(close)>count(open)){
     if(index>0&&text[index-1]===open){index--;value=open+value;}
     else value=value.slice(0,-1);
    }
   }
   if(value)result.push({index,text:value});
  }
  return result;
 }
 // Display-only labels for canvas renderers; datasets and exports remain untouched.
 function canvasText(value){const text=String(value??'');if(!rtlLetter.test(text))return text;let result='',cursor=0;for(const m of ranges(text)){result+=text.slice(cursor,m.index)+'\u2066'+m.text+'\u2069';cursor=m.index+m.text.length;}return result+text.slice(cursor);}
 const api={direction,ranges,canvasText};
 if(!root.document)return Object.freeze(api);
 const doc=root.document,SVG='http://www.w3.org/2000/svg',anchors=new WeakMap(),pending=new Set();let frame=0,observer;
 const codeSelector='code,kbd,samp,[data-yoe-code],.code-editor,.terminal,.terminal-output,.mini-diff,#mini-diff,#wy-permission-data';
 const contentSelector='p,h1,h2,h3,h4,h5,h6,li,ul,ol,dt,dd,td,th,caption,figcaption,blockquote,summary,legend,label,button,option,pre,table,[role="alert"],[role="status"],.markdown-body,.yoe-plain-text';
 function set(el,key,value){if(el.getAttribute(key)!==value)el.setAttribute(key,value);}
 function proseText(el){const walker=doc.createTreeWalker(el,NodeFilter.SHOW_TEXT);let out='',n;while((n=walker.nextNode())){if(!n.parentElement?.closest('code,pre,kbd,samp,[data-yoe-code]'))out+=n.nodeValue;}return out;}
 function protectedCode(el){return el.matches(codeSelector)||!!el.closest(codeSelector)||el.tagName==='PRE'&&!!el.querySelector('code');}
 function selectionInside(el){const s=doc.getSelection();return s&&!s.isCollapsed&&(el.contains(s.anchorNode)||el.contains(s.focusNode));}
 function isolate(el){
  if(el.namespaceURI===SVG||el.closest('code,kbd,samp,bdi,textarea,input,[contenteditable]:not([contenteditable="false"])')||selectionInside(el))return;
  const context=el.closest('p,li,td,th,figcaption,blockquote,.yoe-plain-text')||el;if(!rtlLetter.test(context.textContent||''))return;
  for(const n of [...el.childNodes]){if(n.nodeType!==3||!n.nodeValue.trim())continue;const text=n.nodeValue,plaintext=el.matches('.yoe-plain-text,.yoe-bidi-plain,pre'),matches=ranges(text).filter(m=>{if(!plaintext||!text.includes('\n'))return true;const start=text.lastIndexOf('\n',m.index-1)+1,end=text.indexOf('\n',m.index);return direction(text.slice(start,end<0?text.length:end))==='rtl';});if(!matches.length)continue;const fragment=doc.createDocumentFragment();let cursor=0;for(const m of matches){if(m.index>cursor)fragment.append(text.slice(cursor,m.index));const bdi=doc.createElement('bdi');bdi.dir='ltr';bdi.dataset.yoeLtr='';bdi.textContent=m.text;fragment.append(bdi);cursor=m.index+m.text.length;}fragment.append(text.slice(cursor));n.replaceWith(fragment);}
 }
 function localize(el){if(!el.hasAttribute('lang'))return;const language=(el.getAttribute('lang')||'').toLowerCase().split('-')[0];if(['ar','fa','ur','he','ps','sd','ug'].includes(language))set(el,'dir','rtl');else if(language)set(el,'dir','ltr');}
 function element(el){
  if(el.closest('script,style,template,noscript'))return;
  localize(el);
  if(el.matches('input,textarea,[contenteditable]:not([contenteditable="false"])')){
   const type=(el.getAttribute('type')||'text').toLowerCase();if(el.tagName==='INPUT'&&!['text','search','email','url','tel','number','password'].includes(type))return;
   const fixed=['email','url','tel','number','password'].includes(type)||/(?:paths?|directory|folder|command|terminal|code-editor|diff)/i.test(el.id+' '+el.className)||!!el.closest('[data-yoe-code]');set(el,'dir',fixed?'ltr':'auto');el.classList.add(fixed?'yoe-bidi-code':'yoe-bidi-field');return;
  }
  if(el.tagName==='SELECT'){set(el,'dir',direction(el.selectedOptions[0]?.textContent));el.classList.add('yoe-bidi-text');return;}
  if(el.matches('bdi,[data-yoe-ltr]')){set(el,'dir','ltr');return;}
  if(protectedCode(el)){set(el,'dir','ltr');el.classList.add('yoe-bidi-code');return;}
  if(el.namespaceURI===SVG){
   if(el.tagName.toLowerCase()==='text'){const dir=direction(el.textContent);if(!anchors.has(el))anchors.set(el,el.getAttribute('text-anchor')||'start');const anchor=anchors.get(el);set(el,'direction',dir);set(el,'unicode-bidi','plaintext');set(el,'text-anchor',dir==='rtl'?(anchor==='start'?'end':anchor==='end'?'start':anchor):anchor);}return;
  }
  if(el.matches('canvas,.yoeai-visual-plot,.vie-chart-surface,.yg-view')){set(el,'dir','ltr');return;}
  const ownText=[...el.childNodes].some(n=>n.nodeType===3&&n.nodeValue.trim());
  if(!el.matches(contentSelector)&&!(['DIV','SPAN','A','STRONG','EM','SMALL','B','I','OUTPUT'].includes(el.tagName)&&ownText))return;
  // Never derive a structural layout from an author badge or a nested English control.
  if(['DIV','SPAN'].includes(el.tagName)&&!el.matches('.markdown-body,.yoe-plain-text,[role="alert"],[role="status"]')&&el.querySelector('p,div,section,article,form,ul,ol,table,button,input,textarea'))return;
  const text=el.matches('.markdown-body')||el.querySelector('code,kbd,samp')?proseText(el):el.textContent;if(!text?.trim())return;
  set(el,'dir',direction(text));el.classList.add('yoe-bidi-text');if(text.includes('\n')&&ownText&&/^(pre|pre-wrap|break-spaces)$/.test(getComputedStyle(el).whiteSpace))el.classList.add('yoe-bidi-plain');isolate(el);
 }
 function prepare(node){
  if(!node)return node;
  if(node.nodeType===1)element(node);
  node.querySelectorAll?.('*').forEach(element);
  return node;
 }
 function plain(value){const el=doc.createElement('div');el.className='yoe-plain-text';el.textContent=String(value??'');return prepare(el);}
 function queue(node){const el=node?.nodeType===3?node.parentElement:node;if(el?.nodeType===1){pending.add(el);if(!frame)frame=requestAnimationFrame(flush);}}
 function collect(records){for(const record of records){if(record.type==='characterData')queue(record.target.parentElement);else{queue(record.target);for(const node of record.addedNodes)queue(node);}}}
 function flush(){frame=0;collect(observer.takeRecords());observer.disconnect();const roots=[...pending].filter(n=>n.isConnected);pending.clear();const selected=roots.filter(n=>!roots.some(other=>other!==n&&other.contains(n)));selected.forEach(prepare);observer.observe(doc.body,{subtree:true,childList:true,characterData:true});}
 function start(){
  prepare(doc.body);localize(doc.documentElement);
  observer=new MutationObserver(collect);observer.observe(doc.body,{subtree:true,childList:true,characterData:true});
  const localeObserver=new MutationObserver(records=>{for(const r of records){if(r.attributeName==='lang'||r.attributeName==='data-language'||r.attributeName==='data-locale'){const value=r.target.dataset.language||r.target.dataset.locale;if(value)set(r.target,'lang',value);localize(r.target);queue(r.target);}}});localeObserver.observe(doc.documentElement,{subtree:true,attributes:true,attributeFilter:['lang','data-language','data-locale']});
  doc.addEventListener('input',e=>{if(e.target.matches('input,textarea,[contenteditable]'))element(e.target);},true);
  doc.addEventListener('change',e=>{if(e.target.tagName==='SELECT')element(e.target);},true);
  doc.addEventListener('compositionend',e=>element(e.target),true);
 }
 Object.assign(api,{prepare,plain,setLocale(language){doc.documentElement.lang=language;localize(doc.documentElement);}});
 if(doc.readyState==='loading')doc.addEventListener('DOMContentLoaded',start,{once:true});else start();
 return Object.freeze(api);
});
