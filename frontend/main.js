'use strict';
/* Boot: routing, navigation, polling, top bar. Every page registers itself in `Pages` (see core.js).
   Routes:  #/  = all servers (cards)   #/panel = panel settings   #/s/<id>/<page> = one server. Nothing is selected by default. */

const SERVER_PAGES = ['overview', 'console', 'players', 'settings', 'files', 'plugins', 'backups', 'automation', 'network'];
const GLOBAL_PAGES = ['servers', 'panel'];
const STATE_LABEL = { offline: 'Offline', installing: 'Installing', starting: 'Starting', online: 'Online', stopping: 'Stopping', crashed: 'Crashed' };
const sleep = ms => new Promise(r => setTimeout(r, ms));

function applyTheme(name) {
  if (!['deepslate', 'nether', 'daylight'].includes(name)) name = 'deepslate';
  document.documentElement.dataset.theme = name;
  store.set('mcp.theme', name);
}

/* ---------- pages ---------- */
function buildPages() {
  const host = $('#pages');
  for (const id of Object.keys(Pages)) {
    const P = Pages[id];
    P.nosrv = h('div', { hidden: true }, noServerCard());
    P.body = h('div');
    P.section = h('section', { id: 'page-' + id, hidden: true, 'aria-label': P.title },
      h('div', { class: 'page-head' }, h('div', {}, h('h1', { text: P.title }), P.desc ? h('p', { text: P.desc }) : null)), P.nosrv, P.body);
    host.append(P.section);
    P.mount(P.body);
  }
}

/* ---------- routing ---------- */
function parseHash() {
  const parts = location.hash.replace(/^#\/?/, '').split('/').filter(Boolean);
  if (parts[0] === 's' && parts[1]) return { sid: parts[1], page: SERVER_PAGES.includes(parts[2]) ? parts[2] : 'overview' };
  if (parts[0] === 'panel') return { page: 'panel' };
  return { page: 'servers' };
}
function hashFor(page) {
  if (page === 'servers') return '#/';
  if (GLOBAL_PAGES.includes(page)) return '#/' + page;
  return `#/s/${S.sel}/${page}`;
}

/* go('players') opens a page of the open server; go('servers') and go('panel') are the global pages. */
function go(page) {
  if (!Pages[page]) page = 'servers';
  if (SERVER_PAGES.includes(page) && !currentServer()) page = 'servers';
  const target = hashFor(page);
  if (location.hash !== target) history.pushState(null, '', target);
  showPage(page);
}
function openServer(id, page = 'overview') {
  if (!installedServers().some(s => s.id === id)) return;
  if (S.sel !== id) { S.hist.cpu.length = 0; S.hist.ram.length = 0; Pages.console.lines.length = 0; Pages.console.redraw(); }
  S.sel = id;
  go(page);
}
function closeServer() { S.sel = null; go('servers'); }

function fromHash() {
  const r = parseHash();
  if (r.sid) {
    if (installedServers().some(s => s.id === r.sid)) { if (S.sel !== r.sid) { S.sel = r.sid; Pages.console.lines.length = 0; Pages.console.redraw(); } }
    else { S.sel = null; r.page = 'servers'; history.replaceState(null, '', '#/'); }
  } else S.sel = null;
  showPage(r.page);
}

/* 'plugins', 'mods' or null: what this server type can be extended with (the backend table, with a fallback until it loads) */
function extOf(srv) {
  if (!srv) return null;
  const t = S.sys && S.sys.types && S.sys.types[srv.type];
  if (t) return t.extends || null;
  return { paper: 'plugins', purpur: 'plugins', spigot: 'plugins', fabric: 'mods' }[srv.type] || null;
}

function buildNav() {
  const mode = SERVER_PAGES.includes(S.page) ? 'server' : 'home';
  const srv = currentServer();
  const sig = mode + (srv ? srv.id + srv.name + extOf(srv) : '');
  if (S.navSig === sig) return;
  S.navSig = sig;
  const nav = $('#nav');
  nav.replaceChildren();
  document.body.dataset.mode = mode;
  const item = (id, label, icon) => h('button', { type: 'button', 'data-page': id, onclick: () => go(id) }, ico(icon), h('span', { text: label }));
  if (mode === 'server') {
    nav.append(h('button', { type: 'button', class: 'nav-back', onclick: closeServer }, ico('back'), h('span', { text: 'All servers' })),
      h('div', { class: 'nav-group', text: srv ? srv.name : 'Server' }));
    for (const id of SERVER_PAGES) {
      if (!Pages[id]) continue;
      if (id === 'plugins') { const e = extOf(srv); if (!e) continue; nav.append(item(id, cap(e), Pages[id].icon)); continue; }
      nav.append(item(id, Pages[id].nav || Pages[id].title, Pages[id].icon));
    }
  } else {
    nav.append(item('servers', 'Servers', 'servers'), item('panel', 'Panel settings', 'panel'));
  }
}

function showPage(id) {
  S.page = id;
  buildNav();
  for (const pid of Object.keys(Pages)) Pages[pid].section.hidden = pid !== id;
  $$('#nav button[data-page]').forEach(b => { if (b.dataset.page === id) b.setAttribute('aria-current', 'page'); else b.removeAttribute('aria-current'); });
  document.body.classList.remove('menu-open');
  const P = Pages[id], srv = currentServer();
  if (id === 'plugins') P.title = extOf(srv) ? cap(extOf(srv)) : 'Plugins and mods';
  document.title = `${P.title}${srv && SERVER_PAGES.includes(id) ? ' - ' + srv.name : ''} - ${BRAND.name}`;
  $('#tb-title').textContent = P.title;
  if (S.st) { renderTop(viewStatus(S.st)); if (P.show) P.show(); }
  window.scrollTo(0, 0);
}

async function refresh() {
  while (S.polling) await sleep(40);
  await poll();
}

/* ---------- polling ---------- */
async function poll() {
  if (S.polling) return;
  S.polling = true;
  try {
    const st = await api('/api/status');
    $('#banner').hidden = true;
    S.st = st;
    if (S.sel && !installedServers().some(s => s.id === S.sel)) { S.sel = null; if (SERVER_PAGES.includes(S.page)) go('servers'); }
    pushHistory(st);
    render();
  } catch (e) {
    const b = $('#banner');
    b.textContent = e.message; b.className = 'banner bad'; b.hidden = false;
  } finally { S.polling = false; }
}

function pushHistory(st) {
  if (activeId() && activeId() === S.sel) { S.hist.cpu.push(st.metrics.cpu_pct); S.hist.ram.push(st.metrics.ram_mb); }
  else { S.hist.cpu.length = 0; S.hist.ram.length = 0; }
  for (const k of ['cpu', 'ram']) if (S.hist[k].length > 90) S.hist[k].shift();
}

/* ---------- top bar (only used inside a server) ---------- */
function renderTop(V) {
  const srv = currentServer();
  if (!srv) return;
  const live = BUSY.has(V.state);
  $('#tb-name').textContent = srv.name;
  const ic = $('#tb-icon'), ik = srv.id + ':' + srv.icon;
  if (ic.dataset.k !== ik) { ic.replaceChildren(serverIcon(srv)); ic.dataset.k = ik; }

  const pill = $('#top-state');
  pill.textContent = STATE_LABEL[V.state] || V.state;
  pill.className = 'pill only-server ' + V.state;

  const otherId = activeId() && activeId() !== S.sel ? activeId() : null, other = otherId && S.st.servers.find(s => s.id === otherId);
  const oc = $('#tb-other');
  oc.hidden = !other;
  if (other) { oc.textContent = `${other.name} is running`; oc.dataset.id = otherId; oc.title = 'Open the running server'; }

  const a = $('#tb-addr'), addr = V.playit.address;
  a.hidden = !(live && addr);
  if (!a.hidden && a.dataset.v !== addr) { a.dataset.v = addr; a.replaceChildren(h('span', { text: addr }), ico('copy')); }

  const main = $('#btn-main');
  main.replaceChildren();
  main.title = '';
  if (V.state === 'online') { main.className = 'btn danger only-server'; main.append(ico('stop'), 'Stop server'); main.disabled = false; main.dataset.act = 'stop'; }
  else if (V.state === 'starting') { main.className = 'btn primary only-server'; main.append('Starting...'); main.disabled = true; }
  else if (V.state === 'stopping') { main.className = 'btn primary only-server'; main.append('Stopping...'); main.disabled = true; }
  else if (V.install.active && V.install.server_id === srv.id) { main.className = 'btn primary only-server'; main.append('Installing...'); main.disabled = true; }
  else {
    main.className = 'btn primary only-server'; main.append(ico('play'), 'Start server'); main.dataset.act = 'start';
    main.disabled = !!other || V.install.active;
    if (other) main.title = `${other.name} is running. Only one server can run at a time. Stop it first.`;
  }
  $('#btn-restart').disabled = V.state !== 'online';
  $('#btn-kill').hidden = V.state !== 'stopping';
}

function render() {
  const st = S.st, m = st.metrics, V = viewStatus(st);
  $('#ver').textContent = `v${st.version}${DEMO ? ' preview' : ''}`;
  $('#sys-ram-text').textContent = Math.round(m.sys_ram_used_pct) + '%';
  const rb = $('#sys-ram-bar');
  rb.style.width = m.sys_ram_used_pct + '%';
  rb.className = 'meter-fill' + (m.sys_ram_used_pct > 90 ? ' bad' : m.sys_ram_used_pct > 75 ? ' warn' : '');
  if (st.settings.theme && S.theme !== st.settings.theme) { S.theme = st.settings.theme; applyTheme(S.theme); }
  if (SERVER_PAGES.includes(S.page)) { buildNav(); renderTop(V); }
  const P = Pages[S.page];
  if (P && P.update) P.update(SERVER_PAGES.includes(S.page) ? V : st);
}

/* ---------- wiring ---------- */
function wire() {
  $('#menu-btn').replaceChildren(ico('menu'));
  $('#btn-back').replaceChildren(ico('back'));
  $('#btn-restart').replaceChildren(ico('restart'));
  $('#menu-btn').addEventListener('click', () => document.body.classList.add('menu-open'));
  $('#scrim').addEventListener('click', () => document.body.classList.remove('menu-open'));
  window.addEventListener('keydown', e => { if (e.key === 'Escape') document.body.classList.remove('menu-open'); });

  $('#btn-back').addEventListener('click', closeServer);
  $('#tb-other').addEventListener('click', e => openServer(e.currentTarget.dataset.id));
  $('#tb-addr').addEventListener('click', async () => {
    const a = S.st && S.st.playit.address;
    if (!a) return;
    try { await navigator.clipboard.writeText(a); toast('Address copied.', 'ok'); } catch { toast(a); }
  });

  $('#btn-main').addEventListener('click', e => busy(e.currentTarget, async () => {
    if (e.currentTarget.dataset.act === 'stop') {
      await api('/api/stop', { method: 'POST' });
      toast('Stopping. The world is saved first.');
    } else {
      const srv = currentServer(); if (!srv) return;
      Pages.console.lines.length = 0; Pages.console.redraw();
      await api(`/api/servers/${srv.id}/start`, { method: 'POST' });
      toast(`Starting ${srv.name}.`);
    }
    await refresh();
  }));
  $('#btn-restart').addEventListener('click', async e => {
    if (!await confirmBox('Restart the server?', 'Players are disconnected for about a minute.', 'Restart')) return;
    busy(e.currentTarget, async () => { await api('/api/restart', { method: 'POST' }); await refresh(); });
  });
  $('#btn-kill').addEventListener('click', async e => {
    if (!await confirmBox('Force close the server?', 'The last few minutes of progress may be lost. Use this only if Stop is stuck.', 'Force close', true)) return;
    busy(e.currentTarget, async () => { await api('/api/kill', { method: 'POST' }); await refresh(); });
  });
  const sb = $('#btn-support'); sb.querySelector('.ico-slot').replaceWith(ico('help')); sb.addEventListener('click', () => Support.open());
  window.addEventListener('hashchange', () => { if (location.hash !== hashFor(S.page)) fromHash(); });
}

async function init() {
  const t = store.get('mcp.theme');
  if (t) applyTheme(t);
  if (DEMO && window.MCP_DEMO_HISTORY) { S.hist.cpu = [...window.MCP_DEMO_HISTORY.cpu]; S.hist.ram = [...window.MCP_DEMO_HISTORY.ram]; }
  buildPages();
  wire();
  Pages.console.start();
  try { S.sys = await api('/api/system'); } catch { /* the banner from poll() explains it */ }
  await poll();
  fromHash();
  await Privacy.ensure();
  setInterval(() => { if (!document.hidden) poll(); }, 1500);
}
init();
