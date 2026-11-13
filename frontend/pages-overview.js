'use strict';
Pages.overview = {
  title: 'Overview', desc: 'The selected server at a glance.', icon: 'overview', group: 'Server', needsServer: false,
  data: { props: null, backups: null, sid: null },

  mount(el) {
    const R = this.r = {};
    R.empty = noServerCard();
    R.install = h('div', { class: 'card', hidden: true },
      h('div', { class: 'install-row' }, R.istep = h('strong'), R.ipct = h('span')),
      h('div', { class: 'meter-track' }, R.ibar = h('div', { class: 'meter-fill good' })),
      R.inote = h('p', { class: 'hint', style: 'margin-top:8px' }));
    R.err = h('div', { class: 'note bad', hidden: true, style: 'display:flex;gap:12px;align-items:center' },
      R.errText = h('span', { class: 'grow' }), h('button', { class: 'btn small', onclick: () => { S.dismissedErr = S.st.install.error; this.update(S.st); } }, 'Dismiss'));

    R.icon = h('span', { class: 'hero-icon' });
    R.name = h('div', { class: 'hero-name' }); R.motd = h('div', { class: 'hero-motd' }); R.meta = h('div', { class: 'hero-meta' });
    R.bars = h('div', { class: 'bars', 'aria-hidden': 'true' }, [1, 2, 3, 4, 5].map(() => h('i')));
    R.count = h('div', { class: 'hero-count' });
    R.hero = h('article', { class: 'hero off' }, R.icon, h('div', { class: 'hero-info' }, R.name, R.motd, R.meta), h('div', { class: 'hero-side' }, R.bars, R.count));

    const tile = (label, extra) => { const v = h('div', { class: 'tile-v' }); return { v, el: h('div', { class: 'tile' }, h('div', { class: 'tile-l', text: label }), v, extra) }; };
    R.tPlayers = tile('Players'); R.tUp = tile('Running for');
    R.cpuCv = h('canvas'); R.ramCv = h('canvas');
    R.tCpu = tile('Processor', R.cpuCv); R.tRam = tile('Server memory', R.ramCv);
    R.tiles = h('div', { class: 'tiles' }, R.tPlayers.el, R.tUp.el, R.tCpu.el, R.tRam.el);

    R.join = h('div'); R.players = h('ul', { class: 'list' });
    R.say = h('input', { type: 'text', placeholder: 'Message to everyone', maxlength: 200, 'aria-label': 'Message to everyone' });
    R.qa = h('div', { class: 'stack' },
      h('div', { class: 'row-actions' },
        R.bSave = h('button', { class: 'btn', onclick: e => busy(e.currentTarget, async () => { await api('/api/command', { method: 'POST', json: { command: 'save-all' } }); toast('World saved.', 'ok'); }) }, ico('save'), 'Save world'),
        R.bBackup = h('button', { class: 'btn', onclick: e => busy(e.currentTarget, async () => { await api(srvUrl('/backups'), { method: 'POST' }); toast('Backup created.', 'ok'); this.load(); }) }, ico('backups'), 'Back up now'),
        h('button', { class: 'btn', onclick: () => go('console') }, ico('console'), 'Console'),
        h('button', { class: 'btn', onclick: () => go('files') }, ico('files'), 'Files')),
      h('form', { class: 'row-actions', style: 'flex-wrap:nowrap', onsubmit: e => {
        e.preventDefault();
        const t = R.say.value.trim(); if (!t) return;
        busy(null, async () => { await api('/api/command', { method: 'POST', json: { command: 'say ' + t } }); R.say.value = ''; toast('Message sent.', 'ok'); });
      } }, R.say, R.bSay = h('button', { class: 'btn primary', type: 'submit' }, 'Send')));
    R.health = h('ul', { class: 'checks' });
    R.log = h('div', { class: 'mini-log' });

    const card = (title, body, action) => h('section', { class: 'card' }, h('div', { class: 'card-h' }, h('h2', { text: title }), action || null), body);
    R.main = h('div', {}, R.install, R.err, R.hero, R.tiles,
      h('div', { class: 'grid two' }, card('Join address', R.join), card('Players online', R.players, h('button', { class: 'btn small', onclick: () => go('players') }, 'Manage'))),
      h('div', { class: 'grid two', style: 'margin-top:14px' }, card('Quick actions', R.qa), card('Health', R.health)),
      h('div', { style: 'margin-top:14px' }, card('Recent log', R.log, h('button', { class: 'btn small', onclick: () => go('console') }, 'Open console'))));
    el.append(R.empty, R.main);
    window.addEventListener('resize', () => S.st && this.drawGraphs());
  },

  async show() { await this.load(); },

  async load() {
    const srv = currentServer();
    this.data.sid = srv && srv.id;
    if (!srv) return;
    try {
      const [p, b] = await Promise.all([api(srvUrl('/properties')), api(srvUrl('/backups'))]);
      if (this.data.sid === srv.id) { this.data.props = p.properties; this.data.backups = b.backups; }
    } catch { /* the page still works without these */ }
    this.update(S.st);
  },

  update(st) {
    const R = this.r, srv = currentServer();
    const noServers = !installedServers().length && !st.install.active && !(st.server && BUSY.has(st.state));
    R.empty.hidden = !noServers; R.main.hidden = noServers;
    if (noServers) return;
    if (srv && this.data.sid !== srv.id) { this.data = { props: null, backups: null, sid: srv.id }; this.load(); }

    const on = st.state === 'online', working = st.state === 'starting' || st.state === 'stopping';
    R.hero.classList.toggle('off', !on && !working);
    const props = this.data.props || {};
    if (srv) {
      const ik = srv.id + ':' + srv.icon;
      if (R.icon.dataset.k !== ik) { R.icon.replaceChildren(serverIcon(srv)); R.icon.dataset.k = ik; }
      R.name.textContent = srv.name;
      const motd = props.motd !== undefined ? props.motd : srv.motd;
      if (R.motd.dataset.v !== motd) { R.motd.dataset.v = motd; R.motd.replaceChildren(mcText(motd || ' ')); }
      R.meta.textContent = `${cap(srv.type)} ${srv.version}, ${srv.ram_mb} MB memory, port ${srv.port}`;
    } else { R.name.textContent = 'Installing...'; R.motd.textContent = ''; R.meta.textContent = ''; }
    const n = on ? 5 : working ? 2 : 0;
    R.bars.className = 'bars ' + (on ? 'green' : working ? 'gold' : 'red');
    [...R.bars.children].forEach((b, i) => b.classList.toggle('on', i < n));
    const max = props['max-players'] || '20';
    R.count.textContent = on ? `${st.players.length}/${max} online` : cap(st.state);

    const ins = st.install;
    R.install.hidden = !ins.active;
    if (ins.active) {
      R.istep.textContent = ins.step || 'Installing'; R.ipct.textContent = ins.percent + '%'; R.ibar.style.width = ins.percent + '%';
      R.inote.textContent = /Spigot/.test(ins.step) ? 'Spigot is built on this PC and takes 5 to 10 minutes. You can leave this page.' : 'Keep this window open until it finishes.';
    }
    const err = ins.error && !ins.active && ins.error !== S.dismissedErr;
    R.err.hidden = !err;
    if (err) { R.errText.textContent = ins.error; if (S.lastInstallErr !== ins.error) { S.lastInstallErr = ins.error; fail(new Error(ins.error)); } }

    R.tPlayers.v.textContent = on ? `${st.players.length}/${max}` : '-';
    R.tUp.v.textContent = on ? fmtUptime(st.uptime) : '-';
    R.tCpu.v.textContent = isRunning() ? st.metrics.cpu_pct.toFixed(0) + '%' : '-';
    R.tRam.v.textContent = isRunning() ? st.metrics.ram_mb + ' MB' : '-';
    this.drawGraphs();

    [R.bSave, R.bSay].forEach(b => { b.disabled = !on; });
    R.bBackup.disabled = !srv;
    this.renderJoin(srv);
    this.renderPlayers(on);
    this.renderHealth(srv, on);
    this.renderLog();
  },

  drawGraphs() {
    const srv = currentServer();
    spark(this.r.cpuCv, S.hist.cpu, 100, '--accent', false);
    spark(this.r.ramCv, S.hist.ram, srv ? srv.ram_mb : 2048, '--primary', false);
  },

  renderJoin(srv) {
    const st = S.st, p = st.playit, box = this.r.join;
    const sig = JSON.stringify([srv && srv.port, st.state, p.state, p.mode, p.address, p.claim_url, p.error]);
    if (box.dataset.sig === sig) return;
    box.dataset.sig = sig;
    const kids = [], live = BUSY.has(st.state);
    if (p.address && (live || p.manual)) {
      kids.push(h('div', { class: 'addr-line' }, h('span', { class: 'addr', text: p.address }), copyBtn(p.address)));
      kids.push(h('p', { class: 'hint', text: 'Friends paste this in Multiplayer, Add Server.' }));
    } else if (!live) {
      kids.push(h('p', { class: 'hint', text: srv ? 'Start the server to get an address friends can use.' : 'Create a server to get an address.' }));
    } else if (p.mode === 'external') {
      kids.push(h('p', { text: 'You use your own playit app. Paste its address on the Network page.' }));
      kids.push(h('p', { style: 'margin-top:10px' }, h('button', { class: 'btn', onclick: () => go('network') }, 'Open Network')));
    } else if (p.state === 'needs_claim') {
      kids.push(h('p', { text: 'One more step. Link the network helper to playit.gg. You can continue as a guest.' }));
      kids.push(h('p', { style: 'margin-top:10px' }, h('a', { class: 'btn primary', href: p.claim_url, target: '_blank', rel: 'noopener' }, ico('link'), 'Open link')));
    } else if (p.state === 'error') {
      kids.push(h('p', { text: p.error || 'The network helper stopped.' }));
      kids.push(h('p', { style: 'margin-top:10px' }, h('button', { class: 'btn', onclick: () => go('network') }, 'Open Network')));
    } else if (p.state === 'stopped') {
      kids.push(h('p', { class: 'hint', text: 'The network helper is off, so only this PC can join.' }));
      kids.push(h('p', { style: 'margin-top:10px' }, h('button', { class: 'btn', onclick: e => busy(e.currentTarget, () => api('/api/network/start', { method: 'POST' }).then(() => refresh())) }, 'Turn on helper')));
    } else {
      kids.push(h('p', { class: 'hint', text: p.state === 'downloading' ? 'Downloading the network helper...' : 'Connecting to playit.gg. If this takes long, open the Network page.' }));
      if (live) kids.push(h('p', { style: 'margin-top:8px' }, h('button', { class: 'btn small', onclick: () => go('network') }, 'Open Network')));
    }
    if (srv && live) {
      kids.push(h('div', { class: 'addr-line', style: 'margin-top:12px' }, h('span', { class: 'addr', text: 'localhost:' + srv.port }), copyBtn('localhost:' + srv.port)));
      kids.push(h('p', { class: 'hint', text: 'For you, on this PC.' }));
    }
    box.replaceChildren(...kids);
  },

  renderPlayers(on) {
    const ul = this.r.players, names = on ? S.st.players : [];
    const sig = on + names.join(',');
    if (ul.dataset.sig === sig) return;
    ul.dataset.sig = sig;
    if (!names.length) { ul.replaceChildren(h('li', { class: 'none', text: on ? 'Nobody is online.' : 'Start the server to see players.' })); return; }
    ul.replaceChildren(...names.map(n => h('li', {}, avatar(n), h('span', { class: 't', text: n }))));
  },

  renderHealth(srv, on) {
    const st = S.st, items = [];
    const add = (kind, text, detail) => items.push([kind, text, detail]);
    if (srv) {
      const total = (S.sys && S.sys.ram_total_mb) || st.metrics.sys_ram_total_mb;
      add(srv.ram_mb > total * 0.6 ? 'warn' : 'ok', `Memory for this server: ${srv.ram_mb} MB`, srv.ram_mb > total * 0.6 ? `This PC has ${Math.round(total / 1024)} GB. Lower it so Windows and games keep enough.` : `This PC has ${Math.round(total / 1024)} GB.`);
      const b = this.data.backups;
      if (b) {
        if (!b.length) add('warn', 'No backups yet', 'Press Back up now, or set a schedule on the Automation page.');
        else if (Date.now() / 1000 - b[0].created > 3 * 86400) add('warn', 'Last backup ' + fmtAgo(b[0].created), 'Consider an automatic daily backup.');
        else add('ok', 'Last backup ' + fmtAgo(b[0].created));
      }
      const p = this.data.props;
      if (p && p['online-mode'] === 'false') add('warn', 'Real-account check is off', 'Anyone can join with any name. Turn on the whitelist or online mode.');
      if (on) {
        const a = st.playit.address;
        add(a ? 'ok' : 'warn', a ? 'Friends can reach you' : 'No public address yet', a ? 'Share the address above.' : 'Open the Network page to fix this.');
      }
    }
    if (S.sys && S.sys.disk_free_gb < 5) add('warn', `Only ${S.sys.disk_free_gb} GB of disk space is free`, 'Worlds and backups need room.');
    if (!items.length) add('ok', 'Nothing to report');
    const sig = JSON.stringify(items);
    if (this.r.health.dataset.sig === sig) return;
    this.r.health.dataset.sig = sig;
    this.r.health.replaceChildren(...items.map(([k, t, d]) => h('li', { class: k }, h('span', { class: 'dot' }, ico(k === 'ok' ? 'check' : 'alert')), h('div', {}, h('div', { text: t }), d ? h('div', { class: 'd', text: d }) : null))));
  },

  renderLog() {
    const lines = Pages.console.lines.slice(-8).map(l => l.text);
    const sig = lines.join('\n');
    if (this.r.log.dataset.sig === sig) return;
    this.r.log.dataset.sig = sig;
    this.r.log.replaceChildren(...(lines.length ? lines : ['Nothing yet.']).map(t => h('div', { text: t })));
  },
};

/* Player head: the real face from the panel's cache, or a small pixel face made from the name when there is none. */
function pixelFace(name) {
  const seed = [...name].reduce((a, c) => (a * 31 + c.charCodeAt(0)) >>> 0, 7);
  const pick = (k, arr) => arr[(seed >>> k) % arr.length];
  const skin = pick(1, ['#c68b62', '#e0ac82', '#a86f4a', '#f1c9a5']), hair = pick(4, ['#3b2a1a', '#6b4423', '#222', '#a8742a']), eye = pick(7, ['#3a63c9', '#2e8b57', '#4a3a2a']);
  const g = ['hhhhhhhh', 'hhhhhhhh', 'hsssssh', 'ssssssss', 'sesssese', 'ssssssss', 'sssmmsss', 'ssssssss'].map(r => r.padEnd(8, 's'));
  const cv = h('canvas', { class: 'av', width: 8, height: 8, 'aria-hidden': 'true' }), c = cv.getContext('2d');
  g.forEach((row, y) => [...row].forEach((k, x) => { c.fillStyle = k === 'h' ? hair : k === 'e' ? eye : k === 'm' ? '#7a4a3a' : skin; c.fillRect(x, y, 1, 1); }));
  return cv;
}
function avatar(name) {
  const clean = name.replace(/^\./, '');
  if (DEMO || !/^[A-Za-z0-9_]{1,16}$/.test(clean) || name.startsWith('.')) return pixelFace(name);
  const img = h('img', { class: 'av head', alt: '', width: 30, height: 30, loading: 'lazy', src: '/api/head/' + encodeURIComponent(clean) });
  img.onerror = () => img.replaceWith(pixelFace(name));
  return img;
}
