'use strict';
/* A small, safe Markdown reader for plugin descriptions and changelogs. It builds elements, never HTML text,
   drops raw HTML tags, links only http(s), and shows pictures only from Modrinth's own CDN (no tracking pixels). */
const Md = (() => {
  const SAFE_IMG = /^https:\/\/cdn\.modrinth\.com\//;
  const link = (text, url) => {
    if (!/^https?:\/\//i.test(url)) return document.createTextNode(text);
    return h('a', { href: url, target: '_blank', rel: 'noopener noreferrer', text });
  };
  function inline(src) {
    const out = [];
    const re = /(!\[([^\]]*)\]\(([^)\s]+)[^)]*\))|(\[([^\]]+)\]\(([^)\s]+)[^)]*\))|(`([^`]+)`)|(\*\*([^*]+)\*\*)|(__([^_]+)__)|(\*([^*\n]+)\*)/g;
    let last = 0, m;
    src = src.replace(/<br\s*\/?>/gi, '\n').replace(/<\/?[a-zA-Z][^>]*>/g, '');
    while ((m = re.exec(src))) {
      if (m.index > last) out.push(src.slice(last, m.index));
      if (m[1]) out.push(SAFE_IMG.test(m[3]) ? h('img', { src: m[3], alt: m[2], loading: 'lazy', referrerpolicy: 'no-referrer', class: 'md-img' }) : (m[2] ? link(m[2], m[3]) : ''));
      else if (m[4]) out.push(link(m[5], m[6]));
      else if (m[7]) out.push(h('code', { text: m[8] }));
      else if (m[9] || m[11]) out.push(h('strong', { text: m[10] || m[12] }));
      else if (m[13]) out.push(h('em', { text: m[14] }));
      last = re.lastIndex;
    }
    if (last < src.length) out.push(src.slice(last));
    return out;
  }
  function render(text) {
    const root = h('div', { class: 'md' });
    const lines = String(text || '').replace(/\r/g, '').split('\n');
    let i = 0, para = [];
    const flush = () => { if (para.length) { root.append(h('p', {}, ...inline(para.join(' ')))); para = []; } };
    while (i < lines.length) {
      const l = lines[i];
      let m;
      if (/^```/.test(l)) {
        flush(); const code = []; i++;
        while (i < lines.length && !/^```/.test(lines[i])) code.push(lines[i++]);
        root.append(h('pre', {}, h('code', { text: code.join('\n') })));
      } else if ((m = l.match(/^(#{1,6})\s+(.*)$/))) {
        flush(); root.append(h('h' + Math.min(6, m[1].length + 1), {}, ...inline(m[2])));
      } else if (/^\s*([-*_])(\s*\1){2,}\s*$/.test(l)) { flush(); root.append(h('hr')); }
      else if (/^\s*[-*+]\s+/.test(l) || /^\s*\d+[.)]\s+/.test(l)) {
        flush(); const ordered = /^\s*\d+[.)]/.test(l), items = [];
        while (i < lines.length && (/^\s*[-*+]\s+/.test(lines[i]) || /^\s*\d+[.)]\s+/.test(lines[i]))) items.push(h('li', {}, ...inline(lines[i++].replace(/^\s*([-*+]|\d+[.)])\s+/, ''))));
        root.append(h(ordered ? 'ol' : 'ul', {}, items)); continue;
      } else if (/^>\s?/.test(l)) {
        flush(); const q = [];
        while (i < lines.length && /^>\s?/.test(lines[i])) q.push(lines[i++].replace(/^>\s?/, ''));
        root.append(h('blockquote', {}, ...inline(q.join(' ')))); continue;
      } else if (!l.trim()) flush();
      else para.push(l.trim());
      i++;
    }
    flush();
    return root;
  }
  return { render };
})();
