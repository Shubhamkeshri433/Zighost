'use strict';
/* Shared helpers: DOM builder, API, dialogs, toasts, formatting, pixel icons. */

const DEMO = !!(window.MCP_FORCE_DEMO || location.protocol === 'file:' || new URLSearchParams(location.search).has('demo'));
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];

function h(tag, props = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v == null || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k === 'text') el.textContent = v;
    else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? '' : v);
  }
  for (const kid of kids.flat(2)) {
    if (kid == null || kid === false) continue;
    el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  }
  return el;
}

const ICONS = {
  overview: '<rect x="3" y="3" width="7" height="9"/><rect x="14" y="3" width="7" height="5"/><rect x="14" y="12" width="7" height="9"/><rect x="3" y="16" width="7" height="5"/>',
  console: '<polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/>',
  players: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.6-3.6 3.2-5.5 6.5-5.5s5.9 1.9 6.5 5.5"/><circle cx="17.5" cy="9" r="2.5"/><path d="M17.5 14c2.4 0 4 1.4 4.5 4"/>',
  settings: '<line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/><line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/>',
  files: '<path d="M3 6a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
  plugins: '<path d="M10 4a2 2 0 1 1 4 0v2h4a1 1 0 0 1 1 1v4h-2a2 2 0 1 0 0 4h2v4a1 1 0 0 1-1 1h-4v-2a2 2 0 1 0-4 0v2H6a1 1 0 0 1-1-1v-4h2a2 2 0 1 0 0-4H5V7a1 1 0 0 1 1-1h4z"/>',
  backups: '<polyline points="21 8 21 21 3 21 3 8"/><rect x="1" y="3" width="22" height="5"/><line x1="10" y1="12" x2="14" y2="12"/>',
  automation: '<circle cx="12" cy="12" r="9"/><polyline points="12 7 12 12 15.5 14"/>',
  servers: '<rect x="2" y="2" width="20" height="8" rx="2"/><rect x="2" y="14" width="20" height="8" rx="2"/><line x1="6" y1="6" x2="6.01" y2="6"/><line x1="6" y1="18" x2="6.01" y2="18"/>',
  network: '<circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>',
  panel: '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1 7 17M17 7l2.1-2.1"/>',
  play: '<polygon points="6 4 20 12 6 20"/>', stop: '<rect x="6" y="6" width="12" height="12" rx="1.5"/>',
  restart: '<path d="M20 11a8 8 0 1 0-2.3 5.7"/><polyline points="20 4 20 11 13 11"/>',
  back: '<line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/>',
  close: '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',
  arrow: '<line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>',
  image: '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/>',
  copy: '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V6a2 2 0 0 1 2-2h9"/>',
  plus: '<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>',
  trash: '<polyline points="4 7 20 7"/><path d="M9 7V4h6v3M6 7l1 13h10l1-13"/>',
  upload: '<path d="M12 16V4"/><polyline points="7 9 12 4 17 9"/><path d="M4 20h16"/>',
  download: '<path d="M12 4v12"/><polyline points="7 11 12 16 17 11"/><path d="M4 20h16"/>',
  search: '<circle cx="11" cy="11" r="6.5"/><line x1="16" y1="16" x2="21" y2="21"/>',
  edit: '<path d="M4 20h4L19 9l-4-4L4 16z"/>', file: '<path d="M6 3h8l4 4v14H6z"/><polyline points="14 3 14 8 18 8"/>',
  check: '<polyline points="5 12 10 17 19 7"/>', x: '<line x1="6" y1="6" x2="18" y2="18"/><line x1="18" y1="6" x2="6" y2="18"/>',
  alert: '<path d="M12 3 2.5 20h19z"/><line x1="12" y1="10" x2="12" y2="14"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
  menu: '<line x1="4" y1="7" x2="20" y2="7"/><line x1="4" y1="12" x2="20" y2="12"/><line x1="4" y1="17" x2="20" y2="17"/>',
  link: '<path d="M14 4h6v6"/><line x1="20" y1="4" x2="10" y2="14"/><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
  save: '<path d="M5 4h11l3 3v13H5z"/><rect x="8" y="4" width="7" height="5"/><rect x="8" y="13" width="8" height="7"/>',
  help: '<circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.4-1 .9-1 1.7"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
  shield: '<path d="M12 3 4 6v6c0 4.5 3.2 7.8 8 9 4.8-1.2 8-4.5 8-9V6z"/><polyline points="9 12 11.5 14.5 15.5 9.5"/>',
  refresh: '<path d="M4 12a8 8 0 0 1 14-5.3L20 9"/><polyline points="20 4 20 9 15 9"/><path d="M20 12a8 8 0 0 1-14 5.3L4 15"/><polyline points="4 20 4 15 9 15"/>',
};
function ico(name) {
  const s = h('span', { class: 'ico', 'aria-hidden': 'true' });
  s.innerHTML = `<svg viewBox="0 0 24 24">${ICONS[name] || ''}</svg>`;
  return s;
}
const withIcon = (name, label) => [ico(name), label ? h('span', { text: label }) : null];

const store = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch { /* storage can be blocked */ } },
};

const S = { st: null, sys: null, sel: null, page: 'overview', hist: { cpu: [], ram: [] }, polling: false, dismissedErr: '', lastInstallErr: '' };
const Pages = {};
const BUSY = new Set(['starting', 'online', 'stopping']);

/* ---------- API ---------- */
async function api(path, o = {}) {
  const method = o.method || 'GET';
  if (DEMO) return window.demoApi(path, method, o.json, o.body);
  const opt = { method, headers: {} };
  if (method !== 'GET') {
    opt.headers['X-MCPanel'] = '1';
    if (o.json !== undefined) { opt.headers['Content-Type'] = 'application/json'; opt.body = JSON.stringify(o.json); }
    else if (o.body !== undefined) opt.body = o.body;
  }
  let r;
  try { r = await fetch(path, opt); } catch { throw new Error('Cannot reach the panel. Is the panel window still open?'); }
  let data = {};
  try { data = await r.json(); } catch { /* not json */ }
  if (!r.ok) throw new Error(data.error || `The panel answered with error ${r.status}.`);
  return data;
}
const srvUrl = (sub = '') => `/api/servers/${currentServer().id}${sub}`;

/* ---------- toasts and dialogs ---------- */
function toast(msg, kind = '') {
  const t = h('div', { class: 'toast ' + kind, text: msg });
  $('#toasts').append(t);
  setTimeout(() => t.remove(), kind === 'bad' ? 7500 : 3500);
}
const fail = e => toast(e.message || String(e), 'bad');

function dialog({ title, text = '', ok = 'OK', danger = false, field = null }) {
  const d = $('#dlg');
  $('#dlg-title').textContent = title;
  $('#dlg-text').textContent = text;
  $('#dlg-text').hidden = !text;
  const b = $('#dlg-ok');
  b.textContent = ok;
  b.className = 'btn ' + (danger ? 'danger' : 'primary');
  const f = $('#dlg-field'), inp = $('#dlg-input');
  f.hidden = !field;
  if (field) { $('#dlg-label').textContent = field.label; inp.value = field.value || ''; inp.placeholder = field.placeholder || ''; }
  return new Promise(res => {
    d.addEventListener('close', () => res(d.returnValue === 'ok' ? (field ? inp.value : true) : (field ? null : false)), { once: true });
    d.returnValue = 'cancel';
    d.showModal();
    if (field) { inp.focus(); inp.select(); }
  });
}
const confirmBox = (title, text, ok = 'OK', danger = false) => dialog({ title, text, ok, danger });
const promptBox = (title, label, value = '', ok = 'OK', text = '') => dialog({ title, text, ok, field: { label, value } });

async function busy(btn, fn) {
  if (btn) btn.disabled = true;
  try { return await fn(); } catch (e) { fail(e); } finally { if (btn) btn.disabled = false; }
}

/* ---------- formatting ---------- */
const cap = s => s ? s[0].toUpperCase() + s.slice(1) : '';
const fmtSize = b => b > 1e9 ? (b / 1e9).toFixed(1) + ' GB' : b > 1e6 ? (b / 1e6).toFixed(1) + ' MB' : b > 0 ? Math.max(1, Math.round(b / 1e3)) + ' KB' : '0 KB';
const fmtDate = s => new Date(s * 1000).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' });
function fmtAgo(s) {
  const d = Math.max(0, Date.now() / 1000 - s);
  return d < 90 ? 'just now' : d < 5400 ? Math.round(d / 60) + ' min ago' : d < 129600 ? Math.round(d / 3600) + ' h ago' : Math.round(d / 86400) + ' days ago';
}
function fmtUptime(s) {
  const hh = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60);
  return hh ? `${hh} h ${m} min` : m ? `${m} min` : `${s} s`;
}

/* ---------- pixel icons ---------- */
function rng(seed) {
  let x = 0;
  for (const c of seed) x = (x * 31 + c.charCodeAt(0)) >>> 0;
  return () => { x = (x * 1664525 + 1013904223) >>> 0; return x / 4294967296; };
}
function drawIcon(canvas, seed = 'x') {
  const c = canvas.getContext('2d'), r = rng(seed);
  const grass = ['#5da13a', '#6bb044', '#4f8f31', '#74b94c'], dirt = ['#8a5a34', '#7a4d2b', '#966440', '#6e4526'];
  for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) {
    const edge = 3 + (r() < .35 ? 1 : 0) + (r() < .2 ? 1 : 0);
    c.fillStyle = y < edge ? grass[Math.floor(r() * 4)] : (r() < .06 ? '#8c8c8c' : dirt[Math.floor(r() * 4)]);
    c.fillRect(x, y, 1, 1);
  }
}

/* Minecraft colour codes (section sign) to coloured spans */
const MC_COL = { 0: '#7a7f8c', 1: '#5b6bff', 2: '#00aa00', 3: '#00aaaa', 4: '#cc3333', 5: '#aa00aa', 6: '#ffaa00', 7: '#aaaaaa', 8: '#8a8f9c', 9: '#5555ff', a: '#55ff55', b: '#55ffff', c: '#ff5555', d: '#ff55ff', e: '#ffff55', f: 'var(--text)' };
function mcText(raw) {
  const str = String(raw || '').replace(/\\u00[aA]7/g, '§');
  const out = document.createDocumentFragment();
  let style = {}, buf = '';
  const flush = () => {
    if (!buf) return;
    const sp = h('span', { text: buf });
    if (style.c) sp.style.color = MC_COL[style.c];
    if (style.l) sp.style.fontWeight = '700';
    if (style.o) sp.style.fontStyle = 'italic';
    if (style.n) sp.style.textDecoration = 'underline';
    if (style.m) sp.style.textDecoration = (sp.style.textDecoration || '') + ' line-through';
    out.append(sp); buf = '';
  };
  for (let i = 0; i < str.length; i++) {
    if (str[i] === '§' && i + 1 < str.length) {
      const code = str[++i].toLowerCase();
      flush();
      if (code === 'r') style = {};
      else if (MC_COL[code]) style = { c: code };
      else if ('lonm'.includes(code)) style = { ...style, [code]: true };
    } else buf += str[i];
  }
  flush();
  return out;
}

function copyBtn(text, label = 'Copy') {
  return h('button', { class: 'btn small', type: 'button', onclick: async e => {
    try { await navigator.clipboard.writeText(text); e.currentTarget.textContent = 'Copied'; }
    catch { e.currentTarget.textContent = 'Select and copy'; }
    const b = e.currentTarget;
    setTimeout(() => { b.textContent = label; }, 1800);
  }, text: label });
}

function spark(cv, data, max, color, grid = true) {
  const dpr = window.devicePixelRatio || 1, w = cv.clientWidth, hgt = cv.clientHeight;
  if (!w) return;
  cv.width = w * dpr; cv.height = hgt * dpr;
  const c = cv.getContext('2d');
  c.scale(dpr, dpr);
  const css = getComputedStyle(document.documentElement);
  if (grid) {
    c.strokeStyle = css.getPropertyValue('--line').trim() || '#2f3b52'; c.lineWidth = 1;
    for (const f of [0.5]) { c.beginPath(); c.moveTo(0, hgt * f); c.lineTo(w, hgt * f); c.stroke(); }
  }
  if (data.length < 2) return;
  const col = css.getPropertyValue(color).trim() || color;
  const step = w / 89, x0 = w - (data.length - 1) * step;
  const pts = data.map((v, i) => [x0 + i * step, hgt - 3 - Math.min(1, v / max) * (hgt - 6)]);
  c.beginPath(); pts.forEach(([x, y], i) => i ? c.lineTo(x, y) : c.moveTo(x, y));
  c.lineTo(pts[pts.length - 1][0], hgt); c.lineTo(pts[0][0], hgt); c.closePath();
  c.globalAlpha = .18; c.fillStyle = col; c.fill(); c.globalAlpha = 1;
  c.beginPath(); pts.forEach(([x, y], i) => i ? c.lineTo(x, y) : c.moveTo(x, y));
  c.strokeStyle = col; c.lineWidth = 2; c.stroke();
}

/* ---------- selected server ---------- */
const installedServers = () => (S.st ? S.st.servers.filter(s => s.installed) : []);
/* A server is "selected" only when the person opened its card. Nothing is selected by default. */
function currentServer() {
  if (!S.st || !S.sel) return null;
  return installedServers().find(s => s.id === S.sel) || null;
}
const activeId = () => (S.st && S.st.server && BUSY.has(S.st.state) ? S.st.server.id : null);
const isRunning = () => !!S.sel && activeId() === S.sel;
const isOnline = () => isRunning() && S.st.state === 'online';
/* The status as seen from the open server. Only one server runs at a time, so for any other server it reads "offline". */
function viewStatus(st) {
  if (st.server && st.server.id === S.sel) return st;
  const installing = st.install.active && st.install.server_id === S.sel;
  return { ...st, state: installing ? 'installing' : 'offline', server: null, players: [], uptime: 0, metrics: { ...st.metrics, ram_mb: 0, cpu_pct: 0 } };
}
/* The server's own icon when it has one (server-icon.png), otherwise a small pixel picture made from its id. */
function serverIcon(srv, cls = '') {
  if (srv.icon) return h('img', { class: cls, src: `/api/servers/${srv.id}/icon?v=${srv.icon}`, alt: '', width: 64, height: 64 });
  const cv = h('canvas', { width: 16, height: 16, class: cls, 'aria-hidden': 'true' });
  drawIcon(cv, srv.id);
  return cv;
}

/* a page section that needs a server shows this when there is none */
function noServerCard() {
  const cv = h('canvas', { width: 16, height: 16 });
  drawIcon(cv, 'empty');
  return h('div', { class: 'card empty' }, cv, h('h2', { text: 'No server yet' }),
    h('p', { text: 'Create a server first. The panel downloads Java and the server files for you.' }),
    h('button', { class: 'btn primary', onclick: () => go('servers') }, ico('plus'), 'Create a server'));
}

function tabs(items, current, onPick) {
  const bar = h('div', { class: 'tabs', role: 'tablist' });
  const draw = (cur) => {
    bar.replaceChildren(...items.map(([id, label, count]) => h('button', {
      role: 'tab', 'aria-selected': String(id === cur), onclick: () => { draw(id); onPick(id); },
    }, label, count != null ? h('span', { class: 'count', text: count }) : null)));
  };
  draw(current);
  bar.redraw = draw;
  return bar;
}

/* ---------- modal: one overlay for the create wizard, the icon picker and similar big dialogs ---------- */
const Modal = {
  open(content, { label = 'Dialog', full = false, onClose = null } = {}) {
    const back = h('div', { class: 'modal-back' }), box = h('div', { class: 'modal' + (full ? ' full' : ''), role: 'dialog', 'aria-modal': 'true', 'aria-label': label }, content);
    back.append(box);
    const prev = document.activeElement;
    let closed = false;
    const api = {
      el: box,
      close: (result) => {
        if (closed) return; closed = true;
        document.removeEventListener('keydown', key, true);
        back.remove(); document.body.classList.remove('modal-open');
        if (prev && prev.focus) prev.focus();
        if (onClose) onClose(result);
      },
    };
    const key = e => { if (e.key === 'Escape' && !document.querySelector('dialog[open]')) { e.stopPropagation(); (box.onEscape || (() => api.close()))(); } };
    document.addEventListener('keydown', key, true);
    document.body.append(back); document.body.classList.add('modal-open');
    const f = box.querySelector('[autofocus], input, button'); if (f) f.focus();
    return api;
  },
};

/* In the native window, links that open in a new tab go to the normal browser (playit sign-in, downloads pages). */
document.addEventListener('click', e => {
  const a = e.target.closest && e.target.closest('a[target="_blank"]');
  if (a && window.pywebview && window.pywebview.api && window.pywebview.api.open_external) {
    e.preventDefault();
    window.pywebview.api.open_external(a.href);
  }
});
