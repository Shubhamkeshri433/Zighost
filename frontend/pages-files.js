'use strict';
/* Files: browse the server folder, edit text files, upload (button or drag and drop), download, rename, delete. */
Pages.files = {
  title: 'Files', desc: 'Browse, edit, upload and download everything in the server folder.', icon: 'files', group: 'Server', needsServer: true,
  sid: null, path: '', data: null, edit: null,

  mount(el) { this.body = el; },
  show() {
    const srv = currentServer();
    if (srv && this.sid !== srv.id) { this.sid = srv.id; this.path = ''; }
    this.edit = null;
    return this.load();
  },
  update() { const srv = currentServer(); if (srv && srv.id !== this.sid) this.show(); },

  join(name) { return this.path ? `${this.path}/${name}` : name; },
  q: p => encodeURIComponent(p),

  async load(retry = true) {
    try {
      this.data = await api(srvUrl('/files?path=' + this.q(this.path)));
      this.path = this.data.path;
      this.drawList();
    } catch (e) {
      if (retry && this.path) { this.path = ''; return this.load(false); }
      fail(e);
    }
  },

  crumbs() {
    const parts = this.path ? this.path.split('/') : [];
    const out = [h('button', { type: 'button', onclick: () => { this.path = ''; this.load(); } }, 'server')];
    parts.forEach((p, i) => {
      out.push(h('i', { text: '/' }), h('button', { type: 'button', onclick: () => { this.path = parts.slice(0, i + 1).join('/'); this.load(); } }, p));
    });
    return h('div', { class: 'crumbs', 'aria-label': 'Folder' }, out);
  },

  async upload(files) {
    const list = [...files];
    if (!list.length) return;
    for (const f of list) {
      try {
        toast(`Uploading ${f.name}...`);
        await api(srvUrl(`/files/upload?path=${this.q(this.path)}&name=${this.q(f.name)}`), { method: 'POST', body: f });
        toast(`${f.name} uploaded.`, 'ok');
      } catch (e) { fail(e); }
    }
    this.load();
  },

  drawList() {
    const d = this.data;
    const input = h('input', { type: 'file', multiple: true, hidden: true, onchange: e => { this.upload(e.target.files); e.target.value = ''; } });
    const rows = d.entries.map(f => {
      const full = this.join(f.name);
      const open = () => {
        if (f.dir) { this.path = full; this.load(); }
        else if (f.editable) this.openEditor(full);
        else window.location.href = srvUrl('/download?path=' + this.q(full));
      };
      return h('tr', {},
        h('td', {}, h('button', { class: 'fname' + (f.dir ? ' dir' : ''), type: 'button', onclick: open }, ico(f.dir ? 'files' : 'file'), h('span', { class: 'nowrap', text: f.name }))),
        h('td', { class: 'num hide-sm', text: f.dir ? '' : fmtSize(f.size) }),
        h('td', { class: 'num hide-sm', text: fmtDate(f.modified) }),
        h('td', {}, h('div', { class: 'row-actions', style: 'justify-content:flex-end' },
          f.editable ? h('button', { class: 'btn small', type: 'button', onclick: () => this.openEditor(full) }, ico('edit'), 'Edit') : null,
          !f.dir ? h('a', { class: 'btn small', href: srvUrl('/download?path=' + this.q(full)), 'aria-label': 'Download ' + f.name }, ico('download')) : null,
          h('button', { class: 'btn small', type: 'button', 'aria-label': 'Rename ' + f.name, onclick: async () => {
            const n = await promptBox('Rename', 'New name', f.name, 'Rename'); if (!n || n === f.name) return;
            busy(null, async () => { await api(srvUrl('/files/rename'), { method: 'POST', json: { path: full, name: n } }); this.load(); });
          } }, ico('edit')),
          h('button', { class: 'btn small ghost-danger', type: 'button', 'aria-label': 'Delete ' + f.name, onclick: async () => {
            if (!await confirmBox(`Delete ${f.name}?`, f.dir ? 'The folder and everything in it will be deleted.' : 'This cannot be undone.', 'Delete', true)) return;
            busy(null, async () => { await api(srvUrl('/files/delete'), { method: 'POST', json: { path: full } }); toast('Deleted.', 'ok'); this.load(); });
          } }, ico('trash')))));
    });
    const table = rows.length
      ? h('table', { class: 'table' }, h('thead', {}, h('tr', {}, h('th', { text: 'Name' }), h('th', { class: 'num hide-sm', text: 'Size' }), h('th', { class: 'num hide-sm', text: 'Changed' }), h('th'))), h('tbody', {}, rows))
      : h('p', { class: 'hint', style: 'padding:24px;text-align:center', text: 'This folder is empty. Drop files here to upload them.' });
    const zone = h('div', { class: 'card dropzone', style: 'padding:6px 10px' }, table,
      d.truncated ? h('p', { class: 'hint', style: 'padding:8px', text: 'Only the first 2000 items are shown.' }) : null);
    ['dragenter', 'dragover'].forEach(ev => zone.addEventListener(ev, e => { e.preventDefault(); zone.classList.add('over'); }));
    ['dragleave', 'drop'].forEach(ev => zone.addEventListener(ev, e => { e.preventDefault(); zone.classList.remove('over'); }));
    zone.addEventListener('drop', e => this.upload(e.dataTransfer.files));
    this.body.replaceChildren(
      h('div', { class: 'tools' }, this.crumbs(), h('span', { class: 'grow' }),
        h('button', { class: 'btn', type: 'button', onclick: e => busy(e.currentTarget, () => api('/api/open-folder', { method: 'POST', json: { which: 'server', sid: this.sid || (currentServer() || {}).id } })) }, ico('files'), 'Open on this PC'),
        h('button', { class: 'btn', type: 'button', onclick: () => input.click() }, ico('upload'), 'Upload'),
        h('button', { class: 'btn', type: 'button', onclick: async () => {
          const n = await promptBox('New folder', 'Folder name', '', 'Create'); if (!n) return;
          busy(null, async () => { await api(srvUrl('/files/mkdir'), { method: 'POST', json: { path: this.path, name: n } }); this.load(); });
        } }, ico('plus'), 'New folder'),
        h('button', { class: 'btn ghost', type: 'button', 'aria-label': 'Refresh', onclick: () => this.load() }, ico('refresh')), input),
      zone);
  },

  async openEditor(full) {
    let f;
    try { f = await api(srvUrl('/file?path=' + this.q(full))); } catch (e) { return fail(e); }
    this.edit = full;
    const ta = h('textarea', { class: 'editor', spellcheck: 'false', 'aria-label': 'Contents of ' + full }, f.content);
    const save = h('button', { class: 'btn primary', type: 'button', disabled: true, onclick: () => doSave() }, ico('save'), 'Save');
    const state = h('span', { class: 'hint', text: 'No changes.' });
    const doSave = () => busy(save, async () => {
      await api(srvUrl('/file'), { method: 'PUT', json: { path: full, content: ta.value } });
      f.content = ta.value; save.disabled = true; state.textContent = 'Saved.'; toast('File saved.', 'ok');
    });
    ta.addEventListener('input', () => { const c = ta.value !== f.content; save.disabled = !c; state.textContent = c ? 'Unsaved changes.' : 'No changes.'; });
    ta.addEventListener('keydown', e => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') { e.preventDefault(); if (!save.disabled) doSave(); }
      if (e.key === 'Tab') { e.preventDefault(); const s = ta.selectionStart; ta.setRangeText('  ', s, ta.selectionEnd, 'end'); ta.dispatchEvent(new Event('input')); }
    });
    this.body.replaceChildren(
      h('div', { class: 'tools' },
        h('button', { class: 'btn', type: 'button', onclick: async () => {
          if (!save.disabled && !await confirmBox('Leave without saving?', 'Your changes to this file will be lost.', 'Leave', true)) return;
          this.edit = null; this.load();
        } }, 'Back to files'),
        h('strong', { class: 'mono', text: full }), h('span', { class: 'grow' }), state, save),
      isRunning() ? h('div', { class: 'note warn', text: 'The server is running. Most files are only read at start, so restart after changing them. Some files are overwritten while it runs.' }) : null,
      ta);
    ta.focus();
  },
};
