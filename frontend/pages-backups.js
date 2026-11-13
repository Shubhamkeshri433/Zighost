'use strict';
/* Backups and worlds: make, download, restore, delete backups. Start a fresh world (with a backup first). */
Pages.backups = {
  title: 'Backups and worlds', nav: 'Backups', desc: 'Copies of your worlds, plugins and settings, so nothing is ever lost.', icon: 'backups', group: 'Server', needsServer: true,
  sid: null, data: null, worlds: null,

  mount(el) { this.body = el; },
  show() { const srv = currentServer(); if (srv) this.sid = srv.id; return this.load(); },
  update() {
    const srv = currentServer();
    if (srv && srv.id !== this.sid) { this.show(); return; }
    if (this.resetBtn) this.resetBtn.disabled = isRunning() && S.st.server && S.st.server.id === this.sid;
  },

  async load() {
    try {
      const [b, w] = await Promise.all([api(srvUrl('/backups')), api(srvUrl('/worlds'))]);
      this.data = b.backups; this.worlds = w.worlds;
    } catch (e) { return fail(e); }
    this.draw();
  },

  label(name) {
    const m = name.match(/_([a-z-]+)\.zip$/);
    const map = { manual: 'Manual', scheduled: 'Scheduled', 'before-restore': 'Safety copy before a restore', 'before-reset': 'Safety copy before a reset' };
    return m ? (map[m[1]] || cap(m[1].replace(/-/g, ' '))) : 'Backup';
  },

  draw() {
    const srv = currentServer(), running = isRunning() && S.st.server && S.st.server.id === srv.id;
    const total = this.data.reduce((a, b) => a + b.size, 0);
    const rows = this.data.map(b => h('li', {},
      h('div', { class: 'grow' }, h('div', { class: 't', text: fmtDate(b.created) }), h('div', { class: 's', text: `${this.label(b.name)}, ${fmtSize(b.size)}` })),
      h('a', { class: 'btn small', href: srvUrl(`/backups/${encodeURIComponent(b.name)}/download`), 'aria-label': 'Download backup' }, ico('download'), 'Download'),
      h('button', { class: 'btn small', type: 'button', disabled: running, title: running ? 'Stop the server first' : '', onclick: async e => {
        if (!await confirmBox('Restore this backup?', 'Your current world and settings are replaced. A safety copy is made first.', 'Restore')) return;
        busy(e.currentTarget, async () => { await api(srvUrl(`/backups/${encodeURIComponent(b.name)}/restore`), { method: 'POST' }); toast('Backup restored.', 'ok'); this.load(); });
      } }, 'Restore'),
      h('button', { class: 'btn small ghost-danger', type: 'button', 'aria-label': 'Delete backup', onclick: async e => {
        if (!await confirmBox('Delete this backup?', 'This cannot be undone.', 'Delete', true)) return;
        busy(e.currentTarget, async () => { await api(srvUrl(`/backups/${encodeURIComponent(b.name)}`), { method: 'DELETE' }); this.load(); });
      } }, ico('trash'))));

    this.resetBtn = h('button', { class: 'btn ghost-danger', type: 'button', disabled: running, onclick: async () => {
      const t = await promptBox('Start a fresh world?', `Type the server name (${srv.name}) to confirm`, '', 'Delete world',
        'The current world, nether and end are deleted. A backup is made first, so you can bring it back. A new world is created the next time the server starts.');
      if (t === null) return;
      if (t.trim() !== srv.name) return toast('The name did not match. Nothing was deleted.', 'bad');
      busy(this.resetBtn, async () => { await api(srvUrl('/worlds/reset'), { method: 'POST', json: { confirm: true } }); toast('World deleted. A backup was saved first.', 'ok'); this.load(); });
    } }, ico('trash'), 'Start a fresh world');

    this.body.replaceChildren(
      h('section', { class: 'card' }, h('div', { class: 'card-h' }, h('div', {}, h('h2', { text: 'Backups' }),
        h('p', { class: 'hint', text: this.data.length ? `${this.data.length} backups, ${fmtSize(total)} in total.` : 'None yet.' })),
        h('div', { class: 'row-actions' }, h('button', { class: 'btn', type: 'button', onclick: e => busy(e.currentTarget, async () => { const r = await api('/api/open-folder', { method: 'POST', json: { which: 'backups', sid: srv.id } }); toast('Opened the backups folder.', 'ok'); }) }, ico('files'), 'Open folder'),
        h('button', { class: 'btn primary', type: 'button', onclick: e => busy(e.currentTarget, async () => { await api(srvUrl('/backups'), { method: 'POST' }); toast('Backup created.', 'ok'); this.load(); }) }, ico('plus'), 'Back up now'))),
        h('ul', { class: 'list' }, rows.length ? rows : [h('li', { class: 'none', text: 'No backups yet. Press Back up now, or set a schedule on the Automation page.' })])),
      h('section', { class: 'card' }, h('div', { class: 'card-h' }, h('div', {}, h('h2', { text: 'Worlds' }),
        h('p', { class: 'hint', text: running ? 'Stop the server to reset the world.' : 'The folders of this server that hold your worlds.' })), this.resetBtn),
        h('ul', { class: 'list' }, this.worlds.length ? this.worlds.map(w => h('li', {}, ico('files'), h('div', { class: 'grow' }, h('div', { class: 't mono', text: w.name }),
          h('div', { class: 's', text: w.main ? 'Main world' : w.name.endsWith('_nether') ? 'Nether' : 'The End' })), h('span', { class: 'badge', text: fmtSize(w.size) })))
          : [h('li', { class: 'none', text: 'No world yet. It is created the first time the server starts.' })])));
  },
};
