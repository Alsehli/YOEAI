// Exercise production chat preparation with empty/failed tools; no model or network.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
class Element{
 constructor(){this.children=[];this.style={};this.files=[];this.textContent='';}
 append(...nodes){this.children.push(...nodes)}
 setAttribute(){} addEventListener(){} querySelector(){return null} querySelectorAll(){return []}
}
async function prepare(result,query,fail=false){
 const elements=new Map(),calls=[];
 const document={head:new Element(),createElement:()=>new Element(),querySelector:()=>null,getElementById:id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id)}};
 const context={document,window:{},sessionStorage:{getItem:()=>null,setItem(){}},crypto:{randomUUID:()=> 'fixture-session'},URL,location:{href:'http://127.0.0.1:8087/',origin:'http://127.0.0.1:8087'},setInterval:()=>1,clearInterval(){},console,
  fetch:async(path,options)=>{const body=JSON.parse(options.body);calls.push({path,body});if(path==='/assistant/prepare'&&fail)throw Error('Search service unavailable');return {ok:true,json:async()=>path==='/assistant/prepare'?result:{messages:body.messages}};}};
 vm.createContext(context);vm.runInContext(fs.readFileSync('assets/web-search.js','utf8'),context);
 const messages=[{role:'user',content:query}],message={role:'assistant'};
 await context.window.YoeWeb.prepare(query,messages,message);
 return {messages,message,calls,system:messages.filter(x=>x.role==='system').map(x=>x.content).join('\n')};
}
(async()=>{
 const query='Summarize The Stranger by Albert Camus';
 const empty={evidence:[{tool:'web.research',untrusted:true,result:{searched:true,pages:[],sources:[],limitations:'No results'}}],sources:[],approvals:[],notices:[]};
 const book=await prepare(empty,query);
 assert.match(book.system,/answer the request directly from general knowledge/i);
 assert.match(book.system,/do not ask permission/i);
 assert.equal(book.message.assistantSources.length,0);
 assert.ok(book.messages.at(-1).content.startsWith(query));
 assert.equal(book.calls.at(-1).path,'/assistant/fit');
 const unavailable=await prepare({},query,true);
 assert.match(unavailable.system,/answer directly from general knowledge/i);
 assert.match(unavailable.system,/do not invent quotations, page numbers, citations or current facts/i);
 assert.equal(unavailable.message.assistantSources,undefined);
 const current=await prepare(empty,'What is the current price of this book?');
 assert.match(current.system,/do not guess current facts/i);
 const document=await prepare({evidence:[{tool:'documents.search',result:{coverage:{complete:false},passages:[{text:'Attached passage [excerpt]'}]}}],sources:[],approvals:[],notices:[]},'Summarize my attached book');
 assert.match(document.system,/do not substitute a general-knowledge summary for the unavailable document/i);
 assert.match(document.messages.at(-1).content,/Attached passage \[excerpt\]/);
 assert.match(document.system,/describe summaries as based on excerpts/i);
 console.log('PASS: empty research, unavailable tools, current facts and attached-document evidence boundaries');
})().catch(error=>{console.error(error);process.exitCode=1});
