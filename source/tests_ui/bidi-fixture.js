/* Local synthetic QA; no model, profile, history or external service is touched. */
window.YoePdf={card(){}};
const $=id=>document.getElementById(id), checks=[];
const arabic='افتح ملف C:\\Users\\Documents ثم راجع معالج AMD Ryzen 5 7600X ممتاز وزر https://example.com/a?q=5. الحرارة -12.5 ثم +٢٠٪.';
const markdown='# ملخص البحث\n\n'+arabic+'\n\n- العنصر الأول: 123\n- العنصر الثاني: AMD Ryzen\n\n1. الخطوة الأولى\n2. الخطوة الثانية\n\n| الاسم | القيمة |\n| --- | --- |\n| معالج AMD | 7600 |\n| الحالة | ممتاز |\n\n> ملاحظة عربية مهمة.\n\n`C:\\Users\\Documents` هذا مسار داخل شرح عربي.\n\nEnglish explanation with Arabic word مرحباً remains left to right.\n\n```powershell\nGet-Item "C:\\Users\\Documents"\n# تعليق عربي داخل الكود\n```';
const items=[{role:'user',content:arabic},{role:'assistant',content:'This English response answers an Arabic question.'},{role:'assistant',content:markdown},{role:'assistant',content:''}];
const content=(text,assistant)=>assistant?YoeMarkdown.fragment(text):YoeBidi.plain(text);
function paint(busy){YoeUI.render(items,busy,content,()=>{},()=>{});}
function check(name,value){checks.push({name,passed:!!value});}
const delay=ms=>new Promise(r=>setTimeout(r,ms));
async function run(){
 checks.length=0;items[3].content='';paint(true);$('components').replaceChildren();
 for(const [id,tag,cls] of [['research-result','div','mini-output'],['code-explanation','p',''],['windows-result','div','mini-output'],['game-conversation','div','yg-message'],['image-description','p',''],['notification','div',''],['file-preview','pre','gmail-body']]){const el=document.createElement(tag);el.id=id;el.className=cls;if(id==='notification')el.setAttribute('role','status');el.textContent=arabic;$('components').append(el);}
 const mixedPlain=YoeBidi.plain('فقرة عربية.\nEnglish line.');mixedPlain.id='mixed-plain';$('components').append(mixedPlain);
 const data={columns:[{key:'name',label:'المعالج',type:'string'},{key:'score',label:'النقاط',type:'number'}],rows:[{name:'معالج AMD Ryzen',score:25},{name:'معالج Intel',score:40}]};
 $('table-host').replaceChildren(YoeVisualTables.render({title:'نتائج المقارنة'},data));
 const plan=YoeVisualCharts.options({type:'chart',chartType:'bar',x:'name',series:[{field:'score',label:'النقاط'}]},data);const previous=echarts.getInstanceByDom($('chart'));previous?.dispose();const chart=echarts.init($('chart'),null,{renderer:'svg'});chart.setOption(plan.option);
 const stream='...\n\nهذه إجابة عربية تتدفق تدريجياً مع AMD Ryzen 5 7600X ومسار C:\\Users\\Documents.\n\n- نقطة عربية أثناء التدفق\n\n```python\nprint("مرحبا")\n```\n\nAn English paragraph inside the same streamed response.';
 let streamingCorrect=true;
 for(let i=1;i<=stream.length;i+=11){items[3].content=stream.slice(0,i);paint(true);await delay(25);const p=[...$('message-3').querySelectorAll('p')].find(e=>e.textContent.includes('هذه'));if(p&&/هذه/.test(p.textContent)&&getComputedStyle(p).direction!=='rtl')streamingCorrect=false;}
 items[3].content=stream;paint(false);await delay(220);
 check('Arabic user text is RTL',getComputedStyle($('message-0').querySelector('.yoe-plain-text')).direction==='rtl');
 check('English answer to Arabic user stays LTR',getComputedStyle($('message-1').querySelector('p')).direction==='ltr');
 const md=$('message-2');check('Arabic heading RTL',getComputedStyle(md.querySelector('h1')).direction==='rtl');check('Arabic list markers use RTL', [...md.querySelectorAll('li')].every(e=>getComputedStyle(e).direction==='rtl'));
 check('English paragraph independently LTR',[...md.querySelectorAll('p')].find(e=>e.textContent.startsWith('English')).dir==='ltr');
 check('Inline code does not choose Arabic prose direction',[...md.querySelectorAll('p')].find(e=>e.textContent.includes('هذا مسار')).dir==='rtl');
 check('Arabic table cell RTL',getComputedStyle(md.querySelector('td')).direction==='rtl');check('Numeric table cell LTR',[...md.querySelectorAll('td')].find(e=>e.textContent==='7600').dir==='ltr');
 check('Code block LTR and unchanged',getComputedStyle(md.querySelector('pre')).direction==='ltr'&&md.querySelector('pre code').textContent.includes('Get-Item "C:\\Users\\Documents"'));
 check('Paths and processor names isolated',[...md.querySelectorAll('bdi[dir=ltr]')].some(e=>e.textContent==='C:\\Users\\Documents')&&[...md.querySelectorAll('bdi')].some(e=>e.textContent.includes('AMD Ryzen 5 7600X')));
 check('Negative ASCII numbers stay isolated',[...md.querySelectorAll('bdi')].some(e=>e.textContent==='-12.5'));
 check('Signed Arabic numbers stay isolated',[...md.querySelectorAll('bdi')].some(e=>e.textContent==='+٢٠٪'));
 check('Streaming stays RTL after Arabic arrives',streamingCorrect);
 check('Streamed Markdown code stays LTR',getComputedStyle($('message-3').querySelector('pre')).direction==='ltr');
 check('Streaming language changes per paragraph',[...$('message-3').querySelectorAll('p')].find(e=>e.textContent.startsWith('An English')).dir==='ltr');
 for(const id of ['research-result','code-explanation','windows-result','game-conversation','image-description','notification','file-preview'])check(id+' shared RTL',getComputedStyle($(id)).direction==='rtl'&&$(id).textContent===arabic);
 const walker=document.createTreeWalker($('mixed-plain'),NodeFilter.SHOW_TEXT);let line;while((line=walker.nextNode()))if(line.nodeValue.includes('English'))break;const lineRange=document.createRange();const offset=line.nodeValue.indexOf('English');lineRange.setStart(line,offset);lineRange.setEnd(line,offset+7);check('English plaintext line aligns left independently',lineRange.getBoundingClientRect().left<$('mixed-plain').getBoundingClientRect().left+20);
 check('Interactive data table Arabic cells RTL',[...$('table-host').querySelectorAll('td')].some(e=>e.textContent.includes('معالج')&&getComputedStyle(e).direction==='rtl'));
 check('Chart SVG rendered without geometry mirroring',$('chart').querySelectorAll('svg text').length>0&&getComputedStyle($('chart')).direction==='ltr'&&!plan.option.xAxis.inverse);
 check('Localized Arabic menu layout RTL',getComputedStyle($('localized')).direction==='rtl');check('English application layout stays LTR',document.documentElement.dir==='ltr');
 check('Editable DOM not rewritten',$('editable').childNodes.length===1&&$('editable').getAttribute('dir')==='auto');
 const range=document.createRange();range.selectNodeContents($('message-0').querySelector('.yoe-plain-text'));const selection=getSelection();selection.removeAllRanges();selection.addRange(range);const selected=selection.toString();YoeBidi.prepare($('message-0'));check('Text selection preserves original text',selected===arabic&&selection.toString()===arabic);selection.removeAllRanges();
 check('No bidi control characters inserted in copyable message',!/[\u2066-\u2069]/.test($('message-0').textContent));
 $('report').textContent=JSON.stringify(checks,null,2);$('test-status').textContent=checks.filter(x=>x.passed).length+' / '+checks.length+' checks passed';window.rtlTestResults=checks;
}
$('run').onclick=run;$('locale-ar').onclick=()=>YoeBidi.setLocale('ar');$('locale-en').onclick=()=>YoeBidi.setLocale('en');
document.addEventListener('DOMContentLoaded',run,{once:true});
