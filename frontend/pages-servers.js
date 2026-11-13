'use strict';
/* Servers: one card per server. "New server" opens the create wizard (wizard.js). */
Pages.servers = {
  title: 'Servers', desc: 'Pick a server to manage, or create a new one.', icon: 'servers', group: 'Manage', needsServer: false,
  listSig: '',

  mount(el) {
    this.newBtn = h('button', { class: 'btn primary', onclick: () => this.open() }, ico('plus'), 'New server');
    this.list = h('div', { class: 'scards' });
    el.append(h('div', { class: 'tools' }, this.newBtn), this.list);
  },

  async show() {
    if (!S.sys) { try { S.sys = await api('/api/system'); } catch (e) { fail(e); } }
    this.listSig = ''; this.drawList();
    if (!installedServers().length && !S.st.install.active && !Wizard.w) this.open();
  },

  update() {
    this.drawList();
  },

  /* ---------- cards ---------- */
  drawList() {
    const st = S.st, sig = JSON.stringify([st.servers, st.state, st.server && st.server.id, st.install, st.playit.address, st.players.length]);
    if (sig === this.listSig) return;
    this.listSig = sig;
    const act = activeId();
    const cards = st.servers.map(s => this.card(s, st, act));
    const add = h('button', { class: 'scard new', type: 'button', onclick: () => this.open() }, ico('plus'), h('span', { text: 'New server' }));
    const empty = h('div', { class: 'card empty' }, h('h2', { text: 'No servers yet' }),
      h('p', { text: 'Create your first server in a few steps. Pick a type and version, give it a name and icon, and the panel does the rest.' }),
      h('button', { class: 'btn primary', type: 'button', onclick: () => this.open() }, ico('plus'), 'Create your first server'));
    this.list.replaceChildren(...(st.servers.length ? [...cards, add] : [empty]));
    this.newBtn.hidden = !st.servers.length;     // with no servers the card below has the only button
  },

  card(s, st, act) {
    const mine = st.server && st.server.id === s.id;
    const state = mine ? st.state : (st.install.active && st.install.server_id === s.id ? 'installing' : 'offline');
    const live = mine && BUSY.has(st.state);
    const installing = state === 'installing';
    const unfinished = !s.installed && !installing;
    const label = unfinished ? 'Not finished' : (STATE_LABEL[state] || state);
    const stateRow = h('div', { class: 'scard-state' }, h('span', { class: 'dot ' + (unfinished ? 'crashed' : state) }), h('span', { text: label }),
      live && st.state === 'online' ? h('span', { class: 'badge', text: `${st.players.length} online` }) : null);
    const bar = installing ? h('div', { class: 'meter-track' }, h('div', { class: 'meter-fill', style: `width:${st.install.percent || 0}%` })) : null;
    const addr = live && st.playit.address ? h('button', { class: 'chip', type: 'button', title: 'Copy the address friends use', onclick: async () => {
      try { await navigator.clipboard.writeText(st.playit.address); toast('Address copied.', 'ok'); } catch { toast(st.playit.address); } } },
      h('span', { text: st.playit.address }), ico('copy')) : null;
    const head = h('button', { class: 'scard-head', type: 'button', disabled: !s.installed, onclick: () => openServer(s.id) }, serverIcon(s),
      h('div', { class: 'min0' }, h('div', { class: 'scard-name', text: s.name }), h('div', { class: 'scard-sub', text: `${cap(s.type)} ${s.version}` })));
    const power = live
      ? h('button', { class: 'btn danger', type: 'button', disabled: st.state !== 'online', onclick: e => busy(e.currentTarget, async () => { await api('/api/stop', { method: 'POST' }); toast('Stopping. The world is saved first.'); await refresh(); }) }, ico('stop'), 'Stop')
      : h('button', { class: 'btn primary', type: 'button', disabled: !s.installed || !!act || st.install.active, title: act && !live ? 'Only one server can run at a time. Stop the running one first.' : '',
          onclick: e => busy(e.currentTarget, async () => { Pages.console.lines.length = 0; await api(`/api/servers/${s.id}/start`, { method: 'POST' }); toast(`Starting ${s.name}.`); await refresh(); }) }, ico('play'), 'Start');
    const del = h('button', { class: 'btn small ghost-danger', type: 'button', 'aria-label': 'Delete ' + s.name, disabled: live || (installing), onclick: async e => {
      if (!await confirmBox(`Delete ${s.name}?`, 'Its world, plugins and all its backups are deleted. This cannot be undone.', 'Delete server', true)) return;
      busy(e.currentTarget, async () => { await api('/api/servers/' + s.id, { method: 'DELETE' }); toast('Server deleted.', 'ok'); await refresh(); this.listSig = ''; this.drawList(); });
    } }, ico('trash'));
    return h('article', { class: 'scard' + (live ? ' live' : '') }, head, stateRow, bar, addr,
      h('div', { class: 'scard-actions' }, unfinished ? null : power,
        h('button', { class: 'btn', type: 'button', disabled: !s.installed, onclick: () => openServer(s.id) }, 'Open'), h('span', { class: 'grow' }), del));
  },

  /* ---------- wizard ---------- */
  open() { Wizard.open(); },
};
