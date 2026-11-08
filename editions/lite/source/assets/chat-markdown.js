/* Local Markdown presentation only. Raw HTML and remote Markdown images disabled. */
(() => {
  'use strict';
  const safeLink = value => /^(https?:\/\/[^\s/]+|#)/i.test(value) && !/[\u0000-\u0020\u007f]/.test(value);
  const md = window.markdownit({
    html: false, linkify: true, breaks: false, typographer: false,
    highlight(code, language) {
      if (code.length <= 100000 && language && window.hljs?.getLanguage(language)) {
        try { return hljs.highlight(code, {language, ignoreIllegals: true}).value; }
        catch (_) { /* Use the parser's escaped plaintext fallback. */ }
      }
      return '';
    }
  });
  md.validateLink = safeLink;
  const openLink = md.renderer.rules.link_open || ((tokens, index, options, env, self) => self.renderToken(tokens, index, options));
  md.renderer.rules.link_open = (tokens, index, options, env, self) => {
    tokens[index].attrSet('rel', 'noopener noreferrer');
    return openLink(tokens, index, options, env, self);
  };
  // Uploaded attachments keep their existing image renderer. Model Markdown cannot fetch images.
  md.renderer.rules.image = (tokens, index) => md.utils.escapeHtml(tokens[index].content || 'Image');
  window.YoeMarkdown = Object.freeze({
    fragment(text) {
      const body = document.createElement('div');
      body.className = 'markdown-body';
      const template = document.createElement('template');
      // Only markdown-it-generated markup enters this template; raw source HTML is escaped.
      template.innerHTML = md.render(String(text ?? ''));
      body.append(template.content);
      body.querySelectorAll('table').forEach(table=>{const wrap=document.createElement('div');wrap.className='table-scroll';wrap.tabIndex=0;wrap.setAttribute('role','region');wrap.setAttribute('aria-label','Scrollable table');table.before(wrap);wrap.append(table);});
      return body;
    }
  });
})();
