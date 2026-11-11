/* Counts come only from the server's usage object, never streamed text chunks. */
(() => {
  const key = 'eazyai-token-usage-v1';
  const integer = n => Number.isSafeInteger(n) && n >= 0;
  const empty = () => ({input:0,output:0,total:0,requests:0,last:null});
  function parseUsage(value) {
    if (!value || !integer(value.prompt_tokens) || !integer(value.completion_tokens)) return null;
    const total = value.total_tokens ?? value.prompt_tokens + value.completion_tokens;
    if (!integer(total) || total !== value.prompt_tokens + value.completion_tokens) return null;
    const cached = value.prompt_tokens_details?.cached_tokens;
    return {input:value.prompt_tokens,output:value.completion_tokens,total,
      cached:integer(cached) && cached <= value.prompt_tokens ? cached : null};
  }
  let ledger = empty(), storageAvailable = true;
  try {
    const saved = JSON.parse(localStorage.getItem(key) || 'null');
    if (saved && ['input','output','total','requests'].every(k=>integer(saved[k])) && saved.total===saved.input+saved.output) {
      ledger={...empty(),...saved};
      if (ledger.last && !['input','output','total'].every(k=>integer(ledger.last[k]))) ledger.last=null;
    }
  } catch { storageAvailable=false; }
  let current=null, phase='idle';
  const el = id => document.getElementById(id);
  const number = value => integer(value) ? value.toLocaleString('en-US') : '—';
  function render() {
    el('usage-summary').textContent=phase==='running'?'Usage: counting…':phase==='unavailable'?'Usage: unavailable':`Last: ${number(ledger.last?.total)} tokens`;
    for (const field of ['input','output','total']) {
      el('usage-last-'+field).textContent=number(phase==='unavailable'?null:ledger.last?.[field]);
      el('usage-recorded-'+field).textContent=number(ledger[field]);
    }
    el('usage-cached').textContent=number(phase==='unavailable'?null:ledger.last?.cached);
    el('usage-requests').textContent=number(ledger.requests);
    el('usage-storage').textContent=storageAvailable?'Saved in this app profile.':'Storage unavailable; new totals may last only for this session.';
  }
  window.EazyTokenUsage = Object.freeze({
    begin() {current=null;phase='running';render();},
    observe(event) {const usage=parseUsage(event?.usage);if(usage)current=usage;},
    finish() {
      if (phase!=='running') return;
      if (current) {
        for (const field of ['input','output','total']) ledger[field]+=current[field];
        ledger.requests++;ledger.last=current;phase='idle';
        try {localStorage.setItem(key,JSON.stringify(ledger));storageAvailable=true;}catch {storageAvailable=false;}
      } else phase='unavailable';
      current=null;render();
    }
  });
  const dialog=el('token-usage-dialog');
  el('usage-summary').onclick=()=>dialog.showModal();
  el('usage-close').onclick=()=>dialog.close();
  dialog.addEventListener('click',event=>{if(event.target===dialog){const r=dialog.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)dialog.close();}});
  render();
})();
