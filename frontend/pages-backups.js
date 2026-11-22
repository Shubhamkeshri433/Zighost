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
      this.info = b; this.data = b.backups; this.worlds = w.worlds;
    } catch (e) { return fail(e); }
    this.draw();
  },

  label(name) {
    const m = name.match(/_([a-z-]+)\.zip$/);
    const map = { manual: 'Manual', scheduled: 'Scheduled', 'on-stop': 'After the server stopped', imported: 'Imported', 'before-restore': 'Safety copy before a restore', 'before-reset': 'Safety copy before a reset', 'before-update': 'Safety copy before a version change' };
    return m ? (map[m[1]] || cap(m[1].replace(/-/g, ' '))) : 'Backup';
  },
  SCOPES: { world: ['Only the worlds', 'Smallest and fastest. Does not include plugins or settings.'], standard: ['Worlds, plugins and settings', 'Recommended. Everything you would miss, without files that can be downloaded again.'], full: ['Everything', 'Also the server program and its libraries. Biggest.'] },

  /* a progress bar that follows the backup while it is being made */
  async makeBackup(btn) {
    const bar = this.progressEl, fill = bar.querySelector('.meter-fill'), msg = bar.querySelector('.hint');
    bar.hidden = false; fill.style.width = '0%'; msg.textContent = 'Starting...';
    const sid = this.sid;
    const timer = setInterval(async () => { try { const p = await api(`/api/servers/${sid}/backups/progress`); fill.style.width = p.pct + '%'; msg.textContent = p.step; } catch { /* ignore */ } }, 600);
    try {
      const r = await api(srvUrl('/backups'), { method: 'POST', json: {} });
      toast('Backup saved and checked.' + (r.backup.removed && r.backup.removed.length ? ` ${r.backup.removed.length} old backup(s) were removed by your clean-up rules.` : ''), 'ok');
    } finally { clearInterval(timer); bar.hidden = true; }
    this.load();
  },

  /* what to restore, and where to put it */
  restoreDialog(b, running) {
    const srv = currentServer(), info = this.info;
    return new Promise(res => {
      const worldOnly = b.scope === 'world';
      const kinds = [['all', 'Everything in the backup', 'World, plugins and settings.'], ['world', 'Only the world', 'Plugins and settings stay as they are.'], ['config', 'Only plugins and settings', 'The world stays as it is.']]
        .filter(k => !(worldOnly && k[0] !== 'world') );
      let mode = kinds[0][0], where = running ? 'new' : 'here';
      const radios = (name, items, get, set) => items.map(([v, t, d]) => h('label', { class: 'check', style: 'align-items:flex-start' },
        h('input', { type: 'radio', name, value: v, checked: get() === v, onchange: () => { set(v); sync(); } }), h('span', {}, h('strong', { text: t }), h('br'), h('span', { class: 'hint', text: d }))));
      const name = h('input', { type: 'text', value: `${srv.name} (restored)`.slice(0, 40), maxlength: 40, 'aria-label': 'Name of the new server' });
      const safety = h('input', { type: 'checkbox', checked: true });
      const mismatch = b.version && (b.version !== info.version || (b.type && b.type !== info.type));
      const warn = mismatch ? h('div', { class: 'note warn' }, `This backup was made on ${cap(b.type || '')} ${b.version}. This server uses ${cap(info.type)} ${info.version}. A world saved by a newer version cannot be opened by an older one. If you are unsure, restore it into a new server.`) : null;
      const ok = h('button', { class: 'btn primary', value: 'ok' }, 'Restore');
      const nameField = h('div', { class: 'field' }, h('label', { text: 'Name of the new server' }), name);
      const safetyRow = h('label', { class: 'check' }, safety, h('span', { text: 'Save a safety copy of the current files first (recommended)' }));
      const sync = () => { nameField.hidden = where !== 'new'; safetyRow.hidden = where !== 'here'; };
      const d = h('dialog', { 'aria-label': 'Restore backup', style: 'max-width:520px' },
        h('form', { method: 'dialog' }, h('h2', { text: 'Restore this backup' }), h('p', { class: 'hint', text: `${fmtDate(b.created)}, ${this.label(b.name)}` }), warn,
          h('div', { class: 'field' }, h('strong', { text: 'What to restore' })), ...radios('mode', kinds, () => mode, v => { mode = v; }),
          h('div', { class: 'field', style: 'margin-top:12px' }, h('strong', { text: 'Where to put it' })),
          ...radios('where', [['here', 'Replace this server\'s files', running ? 'Stop the server first.' : 'The current files are replaced.'], ['new', 'Make a new server from it', 'Your current server is not touched.']].map(x => x), () => where, v => { where = v; }),
          nameField, safetyRow,
          h('div', { class: 'dlg-actions' }, h('button', { class: 'btn', value: 'cancel', formnovalidate: true }, 'Cancel'), ok)));
      d.querySelector('input[name=where][value=here]').disabled = running;
      document.body.append(d); sync();
      d.addEventListener('close', () => { const out = d.returnValue === 'ok' ? { mode, where, name: name.value.trim(), safety: safety.checked } : null; d.remove(); res(out); });
      d.showModal();
    });
  },

  async restore(b, btn) {
    const running = isRunning() && S.st.server && S.st.server.id === this.sid;
    const o = await this.restoreDialog(b, running);
    if (!o) return;
    await busy(btn, async () => {
      if (o.where === 'new') {
        await api(srvUrl(`/backups/${encodeURIComponent(b.name)}/restore-new`), { method: 'POST', json: { mode: o.mode, name: o.name } });
        toast('Making the new server from the backup. It appears on the Servers page.', 'ok'); await refresh();
      } else {
        await api(srvUrl(`/backups/${encodeURIComponent(b.name)}/restore`), { method: 'POST', json: { mode: o.mode, safety: o.safety } });
        toast('Backup restored.' + (o.safety ? ' A safety copy was saved first.' : ''), 'ok');
      }
    });
    this.load();
  },

  async setFolder(path, btn) {
    const move = this.moveBox.checked;
    await busy(btn, async () => {
      const r = await api(srvUrl('/backup-options'), { method: 'PUT', json: { folder: path, move } });
      toast(path ? 'Backups will be saved in that folder.' : 'Backups use the default folder again.', 'ok'); this.info = r; this.data = r.backups;
    });
    this.load();
  },

  folderCard() {
    const i = this.info;
    const where = i.own_folder ? 'Chosen for this server' : i.shared_folder ? 'Your default folder from Panel settings' : 'The default folder inside the app data';
    this.moveBox = h('input', { type: 'checkbox', checked: true });
    return h('section', { class: 'card' }, h('div', { class: 'card-h' }, h('div', {}, h('h2', { text: 'Where backups are saved' }), h('p', { class: 'hint', text: where }))),
      h('div', { class: 'mono pathbox', title: i.folder, text: i.folder }),
      h('div', { class: 'row-actions', style: 'margin-top:10px' },
        h('button', { class: 'btn', type: 'button', onclick: async e => { const r = await pickPath('folder', i.own_folder || i.shared_folder, 'Backup folder for this server'); if (r) this.setFolder(r, e.currentTarget); } }, ico('files'), 'Choose folder'),
        i.own_folder ? h('button', { class: 'btn', type: 'button', onclick: e => this.setFolder('', e.currentTarget) }, 'Use the default') : null,
        h('button', { class: 'btn', type: 'button', onclick: e => busy(e.currentTarget, () => api('/api/open-folder', { method: 'POST', json: { which: 'backups', sid: this.sid } })) }, 'Open folder')),
      h('label', { class: 'check', style: 'margin-top:10px' }, this.moveBox, h('span', { text: 'Move the backups I already have to the new folder' })),
      h('p', { class: 'hint', text: 'Any folder works: another drive, a USB disk or a cloud-synced folder. It must not be inside the server itself.' }));
  },

  optionsCard() {
    const i = this.info, r = i.rules || {};
    let scope = i.scope;
    const num = (v, id) => h('input', { type: 'number', id, min: 0, value: v || 0, style: 'width:90px' });
    const f = { count: num(r.count, 'bk-count'), days: num(r.days, 'bk-days'), gb: num(r.gb, 'bk-gb') };
    const onStop = h('input', { type: 'checkbox', checked: i.on_stop });
    const radios = Object.entries(this.SCOPES).map(([v, [t, d]]) => h('label', { class: 'check', style: 'align-items:flex-start' },
      h('input', { type: 'radio', name: 'bk-scope', value: v, checked: scope === v, onchange: () => { scope = v; } }), h('span', {}, h('strong', { text: t }), h('br'), h('span', { class: 'hint', text: d }))));
    return h('section', { class: 'card' }, h('div', { class: 'card-h' }, h('h2', { text: 'What to save and when' })),
      h('div', { class: 'field' }, h('strong', { text: 'What a backup contains' })), ...radios,
      h('label', { class: 'check', style: 'margin-top:12px' }, onStop, h('span', { text: 'Also make a backup every time the server stops' })),
      h('div', { class: 'field', style: 'margin-top:14px' }, h('strong', { text: 'Clean up old backups automatically' }),
        h('p', { class: 'hint', text: 'Use 0 for no limit. The newest backup is never removed. Safety copies are not counted when they are made.' })),
      h('div', { class: 'row-actions' }, h('label', { for: 'bk-count', text: 'Keep at most' }), f.count, h('span', { text: 'backups' }),
        h('label', { for: 'bk-days', text: 'Remove older than' }), f.days, h('span', { text: 'days' }),
        h('label', { for: 'bk-gb', text: 'Stay under' }), f.gb, h('span', { text: 'GB' })),
      h('div', { class: 'form-actions' }, h('button', { class: 'btn primary', type: 'button', onclick: e => busy(e.currentTarget, async () => {
        const r2 = await api(srvUrl('/backup-options'), { method: 'PUT', json: { scope, on_stop: onStop.checked, rules: { count: +f.count.value, days: +f.days.value, gb: +f.gb.value } } });
        this.info = r2; toast('Backup options saved.', 'ok');
      }) }, ico('save'), 'Save options')));
  },

  async importZip(btn) {
    const p = await pickPath('zip', '', 'Import a backup', 'Full path of a .zip file, for example D:\\old-world.zip');
    if (!p) return;
    await busy(btn, async () => { await api(srvUrl('/backups/import'), { method: 'POST', json: { path: p } }); toast('Backup imported. You can restore it from the list.', 'ok'); });
    this.load();
  },

  draw() {
    const srv = currentServer(), running = isRunning() && S.st.server && S.st.server.id === srv.id;
    const total = this.data.reduce((a, b) => a + b.size, 0);
    this.progressEl = h('div', { hidden: true, style: 'padding:0 16px 12px' }, h('div', { class: 'meter-track' }, h('div', { class: 'meter-fill', style: 'width:0%' })), h('p', { class: 'hint' }));
    const rows = this.data.map(b => h('li', {},
      h('div', { class: 'grow min0' }, h('div', { class: 't' }, fmtDate(b.created), ' ',
          b.damaged ? h('span', { class: 'badge bad', text: 'Damaged' }) : null, b.scope ? h('span', { class: 'badge', text: { world: 'Worlds', standard: 'Standard', full: 'Everything' }[b.scope] || b.scope }) : null,
          b.version ? h('span', { class: 'badge', text: `${cap(b.type || '')} ${b.version}`.trim() }) : null),
        h('div', { class: 's', text: `${this.label(b.name)}, ${fmtSize(b.size)}` })),
      h('button', { class: 'btn small primary', type: 'button', disabled: b.damaged, onclick: e => this.restore(b, e.currentTarget) }, 'Restore'),
      h('a', { class: 'btn small', href: srvUrl(`/backups/${encodeURIComponent(b.name)}/download`), 'aria-label': 'Download backup' }, ico('download'), 'Download'),
      h('button', { class: 'btn small', type: 'button', title: 'Check that the file is not damaged', onclick: e => busy(e.currentTarget, async () => {
        const r = await api(srvUrl(`/backups/${encodeURIComponent(b.name)}/verify`), { method: 'POST' });
        r.ok ? toast(`This backup is fine (${r.files} files checked).`, 'ok') : toast(`This backup is damaged${r.bad ? ': ' + r.bad : ''}.`, 'bad');
      }) }, 'Check'),
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
        h('div', { class: 'row-actions' }, h('button', { class: 'btn', type: 'button', onclick: e => this.importZip(e.currentTarget) }, ico('upload'), 'Import'),
        h('button', { class: 'btn primary', type: 'button', onclick: e => busy(e.currentTarget, () => this.makeBackup()) }, ico('plus'), 'Back up now'))),
        this.progressEl, h('ul', { class: 'list' }, rows.length ? rows : [h('li', { class: 'none', text: 'No backups yet. Press Back up now, or set a schedule on the Automation page.' })])),
      this.folderCard(), this.optionsCard(),
      h('section', { class: 'card' }, h('div', { class: 'card-h' }, h('div', {}, h('h2', { text: 'Worlds' }),
        h('p', { class: 'hint', text: running ? 'Stop the server to reset the world.' : 'The folders of this server that hold your worlds.' })), this.resetBtn),
        h('ul', { class: 'list' }, this.worlds.length ? this.worlds.map(w => h('li', {}, ico('files'), h('div', { class: 'grow' }, h('div', { class: 't mono', text: w.name }),
          h('div', { class: 's', text: w.main ? 'Main world' : w.name.endsWith('_nether') ? 'Nether' : 'The End' })), h('span', { class: 'badge', text: fmtSize(w.size) })))
          : [h('li', { class: 'none', text: 'No world yet. It is created the first time the server starts.' })])));
  },
};
