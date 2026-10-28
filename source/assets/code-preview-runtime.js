/* Runs ONLY in the opaque-origin, CSP-sandboxed preview document. */
(()=>{'use strict';
 const {files,channel}=window.__YOE_PROJECT__;delete window.__YOE_PROJECT__;
 let count=0;const send=(kind,message)=>{if(count++<200)parent.postMessage({yoePreview:channel,kind,message:String(message).slice(0,4000)},'*')};
 const describe=v=>{try{return typeof v==='string'?v:JSON.stringify(v)}catch{return String(v)}};
 for(const kind of ['log','warn','error']){const original=console[kind].bind(console);console[kind]=(...v)=>{send(kind,v.map(describe).join(' '));original(...v)}}
 addEventListener('error',e=>send('error',(e.message||'Resource failed')+(e.filename?' at '+e.filename+':'+e.lineno+':'+e.colno:'')),true);
 addEventListener('unhandledrejection',e=>send('error','Unhandled promise: '+(e.reason?.stack||e.reason)));
 addEventListener('securitypolicyviolation',e=>send('error','Blocked by preview policy: '+e.violatedDirective+' '+e.blockedURI));
 let heartbeat=setInterval(()=>parent.postMessage({yoePreview:channel,kind:'heartbeat'},'*'),2000);
 const normal=(name,base='')=>{const parts=(base?base.split('/').slice(0,-1):[]);for(const p of name.split('/')){if(p==='..')parts.pop();else if(p&&p!=='.')parts.push(p)}return parts.join('/')};
 function resolve(name,base=''){const p=normal(name,base);for(const f of [p,p+'.js',p+'.jsx',p+'.ts',p+'.tsx',p+'/index.js',p+'/index.jsx'])if(Object.hasOwn(files,f))return f;throw Error('Missing project file: '+name+' (from '+base+')')}
 const cache={};
 function requireFile(name,base=''){
  if(name==='react')return window.React;
  if(name==='react-dom'||name==='react-dom/client')return window.ReactDOM;
  if(name==='three')return window.THREE;
  if(name==='echarts')return window.echarts;
  if(!name.startsWith('.')&&base)throw Error('Package "'+name+'" is unavailable offline. Use bundled react, react-dom/client, three, echarts or a relative project file.');
  const path=resolve(name,base);if(cache[path])return cache[path].exports;
  const module={exports:{}};cache[path]=module;
  if(path.endsWith('.json')){module.exports=JSON.parse(files[path]);return module.exports}
  if(path.endsWith('.css')){style(files[path],path);return module.exports}
  let code=files[path];if(window.Babel){const presets=[['react',{runtime:'classic'}]];if(/\.tsx?$/.test(path))presets.push(['typescript',{isTSX:path.endsWith('.tsx'),allExtensions:true}]);code=Babel.transform(code,{filename:path,presets,plugins:['transform-modules-commonjs'],sourceType:'unambiguous'}).code}
  else if(/\b(?:import|export)\s/.test(code)||/\.[jt]sx$/.test(path))throw Error('JSX/module compiler did not load.');
  Function('require','module','exports',code+'\n//# sourceURL=yoe-project/'+path)(n=>requireFile(n,path),module,module.exports);return module.exports;
 }
 function style(css,base){const s=document.createElement('style');s.textContent=css.replace(/@import\s+(?:url\()?['"]([^'"]+)['"]\)?\s*;/g,(_,name)=>{try{return files[resolve(name,base)]}catch(e){send('error',e.message);return ''}});document.head.append(s)}
 window.__YOE_BOOT__=()=>{delete window.__YOE_BOOT__;try{
  const html=Object.keys(files).find(n=>/(^|\/)index\.html$/i.test(n))||Object.keys(files).find(n=>n.endsWith('.html'));
  const scripts=[];
  if(html){const parsed=new DOMParser().parseFromString(files[html],'text/html');
   for(const node of [...parsed.querySelectorAll('script')]){scripts.push({src:node.getAttribute('src'),type:node.getAttribute('type'),code:node.textContent});node.remove()}
   for(const node of [...parsed.querySelectorAll('base,meta[http-equiv],iframe,object,embed')])node.remove();
   for(const link of [...parsed.querySelectorAll('link')]){if(link.rel==='stylesheet'){try{style(files[resolve(link.getAttribute('href'),html)],html)}catch(e){send('error',e.message)}}link.remove()}
   for(const image of parsed.querySelectorAll('img[src]')){const src=image.getAttribute('src');if(!src.startsWith('data:')){try{const file=resolve(src,html);if(!file.endsWith('.svg'))throw Error('Only inline data images and project SVG images are supported.');image.src='data:image/svg+xml;charset=utf-8,'+encodeURIComponent(files[file])}catch(e){send('error',e.message);image.removeAttribute('src')}}}
   document.title=parsed.title||'Code YOE preview';for(const node of [...parsed.head.children])if(node.tagName==='STYLE')style(node.textContent,html);
   document.body.replaceChildren(...parsed.body.childNodes);
   for(const item of scripts){if(item.src){if(/^(https?:)?\/\//.test(item.src)){send('error','External script blocked: '+item.src+'. Import a bundled library or include a local file.');continue}const file=resolve(item.src,html);if(item.type==='module'||/\.[jt]sx?$/.test(file)&&/\b(?:import|export)\s/.test(files[file]))requireFile('./'+file);else{const s=document.createElement('script');s.textContent=files[file]+'\n//# sourceURL=yoe-project/'+file;document.body.append(s)}}else if(['text/babel','text/jsx','module'].includes(item.type)){const name='__inline'+scripts.indexOf(item)+'.jsx';files[name]=item.code;requireFile('./'+name)}else if(!item.type||['text/javascript','application/javascript'].includes(item.type)){const s=document.createElement('script');s.textContent=item.code+'\n//# sourceURL=yoe-project/inline.js';document.body.append(s)}}
   // Separate generated CSS/JS blocks commonly accompany an HTML fragment.
   if(!scripts.length){for(const n of Object.keys(files).filter(n=>n.endsWith('.css')))style(files[n],n);const entry=Object.keys(files).find(n=>/\.(?:js|jsx|ts|tsx)$/.test(n));if(entry)runEntry(entry)}
  }else{document.body.innerHTML='<div id="root"></div>';for(const n of Object.keys(files).filter(n=>n.endsWith('.css')))style(files[n],n);const entry=Object.keys(files).find(n=>/(?:^|\/)(?:main|index)\.[jt]sx?$/.test(n))||Object.keys(files).find(n=>/\.[jt]sx?$/.test(n));if(!entry)throw Error('This project needs a native runtime. Select Run and review the runtime approval.');runEntry(entry)}
  function runEntry(entry){const mod=requireFile('./'+entry);if(typeof mod.default==='function'&&window.ReactDOM&&!document.getElementById('root')?.hasChildNodes())ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(mod.default))}
  // Boot runs during parsing; the browser emits DOMContentLoaded once, naturally.
  send('ready','Running in isolated browser');
 }catch(e){send('error',e.stack||e.message);const p=document.createElement('pre');p.id='yoe-boot-error';p.textContent=e.stack||e.message;document.body.append(p)}};
})();
