const fs=require('fs'),vm=require('vm'),assert=require('assert');
for(const file of process.argv.slice(2)){
 const html=fs.readFileSync(file,'utf8'),code=html.match(/<script>([\s\S]*?)<\/script>/)[1];
 const elements=new Map();let clicks=0;
 const get=id=>{if(!elements.has(id))elements.set(id,{value:'',disabled:false,textContent:'',replaceChildren(){},append(){},click(){clicks++}});return elements.get(id)};
 const sandbox={document:{getElementById:get,createElement:()=>({append(){}}),createTextNode:s=>s},localStorage:{getItem:()=>null,setItem(){}},setInterval(){},fetch:async()=>({json:async()=>({status:'ok',used:1,total:1,util:0,temp:35,context:2048,model:'Q6_K'})}),AbortController,structuredClone,performance,TextDecoder};
 vm.createContext(sandbox);vm.runInContext(code,sandbox);
 const key=get('prompt').onkeydown;
 let prevented=0;key({key:'Enter',preventDefault(){prevented++}});assert.equal(clicks,1);assert.equal(prevented,1);
 key({key:'Enter',shiftKey:true,preventDefault(){throw Error('Shift Enter blocked')}});assert.equal(clicks,1);
 key({key:'Enter',isComposing:true,preventDefault(){throw Error('Composition blocked')}});assert.equal(clicks,1);
 key({key:'Enter',keyCode:229,preventDefault(){throw Error('IME blocked')}});assert.equal(clicks,1);
 key({key:'Enter',repeat:true,preventDefault(){}});assert.equal(clicks,1);
 vm.runInContext('responseController=new AbortController();',sandbox);get('stop-response').onclick();assert(vm.runInContext('responseController.signal.aborted',sandbox));assert.equal(get('speed').textContent,'Stopped');
 console.log('PASS: Enter, Shift+Enter, IME, key-repeat, Stop for '+file);
}
