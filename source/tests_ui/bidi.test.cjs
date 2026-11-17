const assert=require('node:assert/strict'), B=require('../assets/bidi.js');
for(const [text,expected] of [['مرحباً بك','rtl'],['Hello world','ltr'],['... معالج AMD Ryzen 5 7600X ممتاز','rtl'],['افتح ملف C:\\Users\\Documents','rtl'],['The word مرحبا is Arabic.','ltr'],['123 - العربية','rtl'],['١٢٣','ltr'],['','ltr']])assert.equal(B.direction(text),expected,text);
const mixed='افتح ملف C:\\Users\\Documents ثم زر https://example.com/a?q=5 ومعالج AMD Ryzen 5 7600X ممتاز';
const ranges=B.ranges(mixed);assert(ranges.some(r=>r.text==='C:\\Users\\Documents'));assert(ranges.some(r=>r.text==='AMD Ryzen 5 7600X'));assert(ranges.some(r=>r.text==='https://example.com/a?q=5'));
assert.equal(B.canvasText(mixed).replace(/[\u2066\u2069]/g,''),mixed);assert.equal(B.canvasText('English only 123'),'English only 123');
console.log('Direction, paths, URLs, mixed processor names, neutral/Arabic numbers, and lossless canvas-label isolation passed.');

assert(B.ranges('افتح (C:\\Users\\Documents).').some(r=>r.text==='(C:\\Users\\Documents)'));assert(B.ranges('زر https://example.com.').some(r=>r.text==='https://example.com'));

assert(B.ranges('الحرارة -12.5 ثم +٢٠٪').some(r=>r.text==='-12.5'));assert(B.ranges('الحرارة -12.5 ثم +٢٠٪').some(r=>r.text==='+٢٠٪'));
