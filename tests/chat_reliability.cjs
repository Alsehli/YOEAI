'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');global.window={};vm.runInThisContext(fs.readFileSync(process.argv[2],'utf8'));const read=window.YoeChatReliability.readStream,encoder=new TextEncoder();let tests=[];
async function test(name,fn){try{await fn();tests.push({name,passed:true});}catch(e){tests.push({name,passed:false,error:e.message});}}
function stream(parts){return new Response(new ReadableStream({start(c){for(const part of parts)c.enqueue(typeof part==='string'?encoder.encode(part):part);c.close();}}));}
(async()=>{
await test('EOF without newline',async()=>{let got=[];await read(stream(['data: {"text":"ok"}']),e=>got.push(e));assert.equal(got[0].text,'ok');});
await test('UTF8 split across chunks',async()=>{let bytes=encoder.encode('data: {"text":"مرحبا"}\n\n'),got=[];await read(stream([...bytes].map(b=>new Uint8Array([b]))),e=>got.push(e));assert.equal(got[0].text,'مرحبا');});
await test('CRLF and comments',async()=>{let got=[];await read(stream([': keepalive\r\ndata: {"text":"ok"}\r\n\r\n']),e=>got.push(e));assert.equal(got.length,1);});
await test('multiline SSE data',async()=>{let got=[];await read(stream(['data: {"text":\ndata: "ok"}\n\n']),e=>got.push(e));assert.equal(got[0].text,'ok');});
await test('DONE cancels unclosed transport',async()=>{let cancelled=false,got=[];const response=new Response(new ReadableStream({start(c){c.enqueue(encoder.encode('data: {"text":"ok"}\n\ndata: [DONE]\n\n'));},cancel(){cancelled=true;}}));await Promise.race([read(response,e=>got.push(e)),new Promise((_,reject)=>setTimeout(()=>reject(Error('hung after DONE')),500))]);assert.ok(cancelled);assert.equal(got.length,1);});
for(const error of ['model failed',{message:'model failed'}])await test('server error '+typeof error,async()=>{await assert.rejects(read(stream(['data: '+JSON.stringify({error})+'\n\n']),()=>{}),/model failed/);});
await test('malformed JSON is explained',async()=>{await assert.rejects(read(stream(['data: nope\n\n']),()=>{}),/unreadable response/);});
await test('abort before reading',async()=>{let controller=new AbortController();controller.abort();await assert.rejects(read(stream(['data: {}\n\n']),()=>{},controller.signal),{name:'AbortError'});});
await test('missing response body',async()=>{await assert.rejects(read({body:null},()=>{}),/no response stream/);});
await test('bounded incomplete event',async()=>{await assert.rejects(read(stream(['data: '+ 'x'.repeat(2*1024*1024+1)]),()=>{}),/too large/);});
await test('usage-only event retained',async()=>{let got=[];await read(stream(['data: {"usage":{"completion_tokens":12}}\n\n']),e=>got.push(e));assert.equal(got[0].usage.completion_tokens,12);});

function storage(initial={},failWrites=false){const values=new Map(Object.entries(initial));global.localStorage={getItem:key=>values.get(key)??null,setItem:(key,value)=>{if(failWrites)throw Error('storage full');values.set(key,value);}};window.YoeChatReliability.historyState.writable=true;window.YoeChatReliability.historyState.issue='';return values;}
await test('malformed saved chat preserved',()=>{const values=storage({'deepseek-chat':'{broken'});assert.deepEqual(window.YoeChatReliability.loadHistory(),[]);assert.equal(values.get('deepseek-chat-recovery'),'{broken');assert.equal(values.get('deepseek-chat'),'{broken');});
await test('valid chat and media metadata preserved',()=>{const data=[{role:'assistant',content:'video',videoGeneration:{id:'fixture'}}];storage({'deepseek-chat':JSON.stringify(data)});assert.deepEqual(window.YoeChatReliability.loadHistory(),data);});
await test('incorrect history shape recovered',()=>{const values=storage({'deepseek-chat':'{}'});assert.deepEqual(window.YoeChatReliability.loadHistory(),[]);assert.equal(values.get('deepseek-chat-recovery'),'{}');});
await test('backup storage full prevents overwrite',()=>{storage({'deepseek-chat':'{broken'},true);window.YoeChatReliability.loadHistory();assert.throws(()=>window.YoeChatReliability.saveHistory([]),/original data is unchanged/);});
await test('previous recovery is not overwritten',()=>{const values=storage({'deepseek-chat':'{new broken','deepseek-chat-recovery':'older recovery'});window.YoeChatReliability.loadHistory();assert.equal(values.get('deepseek-chat-recovery'),'older recovery');assert.equal(values.get(window.YoeChatReliability.historyState.recoveryKey),'{new broken');});
await test('storage unavailable leaves chat usable',()=>{global.localStorage={getItem(){throw Error('denied')}};assert.deepEqual(window.YoeChatReliability.loadHistory(),[]);assert.throws(()=>window.YoeChatReliability.saveHistory([]),/unavailable/);});
await test('new chat persists after recovery',()=>{const values=storage({'deepseek-chat':'{broken'});window.YoeChatReliability.loadHistory();window.YoeChatReliability.saveHistory([{role:'user',content:'hello'}]);assert.equal(JSON.parse(values.get('deepseek-chat'))[0].content,'hello');assert.equal(values.get('deepseek-chat-recovery'),'{broken');});
await test('damaged media record recovered',()=>{const raw=JSON.stringify([{role:'user',content:[null]}]);const values=storage({'deepseek-chat':raw});assert.deepEqual(window.YoeChatReliability.loadHistory(),[]);assert.equal(values.get('deepseek-chat-recovery'),raw);});
console.log(JSON.stringify(tests,null,2));if(tests.some(t=>!t.passed))process.exitCode=1;
})();
