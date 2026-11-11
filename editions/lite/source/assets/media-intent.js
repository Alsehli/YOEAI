/* Explicit media requests use the existing local generators in ordinary chat. */
((root)=>{'use strict';
 function video(text){
  const value=String(text||'').trim();
  if(!value||/\b(?:do not|don't|cannot|can't|never)\s+(?:create|make|generate|animate|produce|render)\b/i.test(value)||/لا\s+(?:تحرك|تنشئ|تولد)/.test(value))return false;
  // Questions about making videos and requests for code stay in conversation.
  if(/^(?:please\s+)?(?:how\b|explain\b|tell me\b|what\b|why\b|write\b|compare\b)/i.test(value)||/^(?:كيف|اشرح|اكتب|قارن)/.test(value))return false;
  const request=value.replace(/^(?:please\s+)?(?:(?:can|could|would) you\s+)?(?:please\s+)?/i,'');
  const firstMedia=request.match(/\b(?:picture|image|photo|photograph|illustration|video|animation|movie|clip)\b/i);
  if(firstMedia&&/^(?:picture|image|photo|photograph|illustration)$/i.test(firstMedia[0])&&!/^animate\b/i.test(request))return false;
  return /^(?:create|make|generate|produce|render)\b[^\n]{0,100}\b(?:video|animation|animated clip|movie|short clip)\b/i.test(request)||/^animate\s+(?:this|the|my|an?|attached)\s+(?:picture|image|photo|photograph|scene)\b/i.test(request)||/^(?:حرك|حرّك)\s+(?:هذه\s+)?(?:الصورة|صورة)/.test(request)||/^(?:أنشئ|انشئ|اصنع|ولد|ولّد)\s+(?:مقطع\s+)?فيديو/.test(request);
 }
 const api={video};root.YoeMediaIntent=api;
 if(typeof module==='object'&&module.exports)module.exports=api;
})(typeof window==='object'?window:globalThis);
