// Runs the production conversation adapter in a minimal DOM fixture; not a browser layout test.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
class Element{constructor(tag='div'){this.tagName=tag;this.children=[];this.style={};this.files=[];this.textContent='';this.attrs={};}append(...nodes){this.children.push(...nodes)}prepend(...nodes){this.children.unshift(...nodes)}setAttribute(k,v){this.attrs[k]=v}getAttribute(k){return this.attrs[k]}addEventListener(){}querySelector(){return null}querySelectorAll(){return this.links||[]}replaceWith(node){this.replacement=node}before(){}get childNodes(){return this.children}}
const elements=new Map();const document={head:new Element(),createElement:tag=>new Element(tag),getElementById:id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id)},querySelector:()=>null};
const context={document,window:{},sessionStorage:{getItem:()=>null,setItem(){}},crypto:{randomUUID:()=> 'fixture-session'},URL,location:{href:'http://127.0.0.1:8087/',origin:'http://127.0.0.1:8087'},console};vm.createContext(context);vm.runInContext(fs.readFileSync('assets/web-search.js','utf8'),context);
const rows=[];function test(id,fn){try{fn();rows.push({id,status:'passed'})}catch(error){rows.push({id,status:'failed',error:String(error)})}}
function card(url,sources=[]){const link=new Element('a');link.attrs.href=url;link.textContent='Source';const container=new Element();container.links=[link];context.window.YoeWeb.card({role:'assistant',assistantResearchAttempted:true,assistantSources:sources},container);return {link,container}}
test('UI01-unretrieved-link-removed',()=>assert.ok(card('https://invented.example/a').link.replacement));
test('UI02-retrieved-link-retained',()=>assert.equal(card('https://example.org/a',[{url:'https://example.org/a',title:'Source'}]).link.replacement,undefined));
test('UI03-javascript-link-removed',()=>assert.ok(card('javascript:alert(1)').link.replacement));
test('UI04-http-link-removed',()=>assert.ok(card('http://example.org/a',[{url:'http://example.org/a',title:'Unsafe'}]).link.replacement));
test('UI05-private-source-link-retained',()=>assert.equal(card('/assistant/source/abcdefgh').link.replacement,undefined));
test('UI06-title-inserted-as-text',()=>{const {container}=card('https://example.org/a',[{url:'https://example.org/a',title:'<img src=x onerror=bad()>'}]);const sources=container.children[0];assert.equal(sources.children[0].textContent,'<img src=x onerror=bad()>');assert.equal(sources.children[0].rel,'noopener noreferrer')});
test('UI07-unsafe-file-url-removed',()=>assert.ok(card('file:///C:/private.txt').link.replacement));
test('UI08-credentials-url-removed',()=>assert.ok(card('https://secret@example.org/a').link.replacement));
test('UI09-normal-chat-hook-registered',()=>assert.equal(typeof context.window.YoeWeb.prepare,'function'));
test('UI10-unretrieved-visual-source-removed',()=>{const link=new Element('a');link.attrs.href='https://invented.example/visual';link.textContent='Visual source';const container=new Element();container.querySelectorAll=selector=>selector.includes('.vie-provenance')?[link]:[];context.window.YoeWeb.card({role:'assistant',assistantResearchAttempted:true,assistantSources:[]},container);assert.ok(link.replacement)});
test('UI11-export-filter-available',()=>assert.equal(typeof context.window.YoeWeb.filterSources,'function'));
test('UI12-internal-heading-link-preserved',()=>assert.equal(card('#section-one').link.replacement,undefined));
fs.mkdirSync('docs/search-results/ui',{recursive:true});fs.writeFileSync('docs/search-results/ui/results.json',JSON.stringify(rows,null,2));console.log(JSON.stringify(rows));process.exitCode=rows.some(r=>r.status==='failed')?1:0;
