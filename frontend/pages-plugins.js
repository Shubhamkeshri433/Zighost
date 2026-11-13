'use strict';
/* Plugins and mods: installed list with on/off switch, search and one-click install from Modrinth, upload a jar. */
Pages.plugins = {
  title: 'Plugins and mods', nav: 'Plugins', desc: 'Add features to the selected server. Restart the server after a change.', icon: 'plugins', group: 'Server', needsServer: true,
  sid: null, tab: 'installed', info: null, hits: null, total: 0, offset: 0, query: '', searching: false, installing: new Set(),

  mount(el) { this.body = el; },
  async show() {
    const srv = currentServer();
    if (srv && srv.id !== this.sid) { this.sid = srv.id; this.hits = null; this.query = ''; this.offset = 0; }
    await this.load();
  },
  update() { const srv = currentServer(); if (srv && srv.id !== this.sid) this.show(); },

  async load() {
    try { this.info = await api(srvUrl('/plugins')); } catch (e) { return fail(e); }
    this.draw();
  },

  word() { return this.info && this.info.kind === 'mod' ? 'mod' : 'plugin'; },

  draw() {
    const i = this.info;
    if (!i.supported) {
      this.body.replaceChildren(h('div', { class: 'card empty' }, h('h2', { text: 'This server cannot use plugins or mods' }),
        h('p', { text: 'Vanilla servers run the game exactly as Mojang made it. Create a Paper server for plugins or a Fabric server for mods.' }),
        h('button', { class: 'btn primary', onclick: () => go('servers') }, ico('plus'), 'Create another server')));
      return;
    }
    const t = tabs([['installed', 'Installed', i.items.length], ['find', 'Find new']], this.tab, id => { this.tab = id; this.drawTab(); });
    this.pane = h('div');
    this.body.replaceChildren(t, this.pane);
    this.drawTab();
  },

  drawTab() { this.pane.replaceChildren(this.tab === 'find' ? this.find() : this.installed()); if (this.tab === 'find' && !this.hits) this.search(0); },

  installed() {
    const i = this.info, w = this.word();
    const input = h('input', { type: 'file', accept: '.jar', multiple: true, hidden: true, onchange: async e => {
      for (const f of e.target.files) {
        try { await api(srvUrl(`/files/upload?path=${encodeURIComponent(i.folder)}&name=${encodeURIComponent(f.name)}`), { method: 'POST', body: f }); toast(`${f.name} added.`, 'ok'); }
        catch (err) { fail(err); }
      }
      e.target.value = ''; this.load();
    } });
    const rows = i.items.map(p => {
      const sw = h('input', { type: 'checkbox', checked: p.enabled, 'aria-label': `${p.title} is on`, onchange: async e => {
        try { await api(srvUrl('/plugins/toggle'), { method: 'POST', json: { file: p.file, enabled: e.target.checked } }); toast(`${p.title} ${e.target.checked ? 'turned on' : 'turned off'}. Restart to apply.`, 'ok'); this.load(); }
        catch (err) { e.target.checked = !e.target.checked; fail(err); }
      } });
      return h('li', {}, h('label', { class: 'switch' }, sw, h('i')),
        h('div', { class: 'grow' }, h('div', { class: 't', text: p.title + (p.version ? ' ' + p.version : '') }),
          h('div', { class: 's nowrap', text: p.description || p.file }), p.description ? h('div', { class: 's mono', text: `${p.file}, ${fmtSize(p.size)}` }) : null),
        h('button', { class: 'btn small ghost-danger', type: 'button', 'aria-label': 'Remove ' + p.title, onclick: async () => {
          if (!await confirmBox(`Remove ${p.title}?`, `The file ${p.file} is deleted. Its settings folder stays.`, 'Remove', true)) return;
          busy(null, async () => { await api(srvUrl('/plugins/remove'), { method: 'POST', json: { file: p.file } }); toast('Removed.', 'ok'); this.load(); });
        } }, ico('trash'), 'Remove'));
    });
    return h('div', {},
      h('div', { class: 'tools' }, h('span', { class: 'hint', text: `${i.type === 'fabric' ? 'Fabric' : cap(i.type)} ${i.version}. Files are in the ${i.folder} folder.` }), h('span', { class: 'grow' }),
        h('button', { class: 'btn', type: 'button', onclick: () => input.click() }, ico('upload'), `Add a ${w} file (.jar)`), input),
      h('div', { class: 'card' }, h('ul', { class: 'list' }, rows.length ? rows : [h('li', { class: 'none', text: `No ${w}s yet. Open Find new to add some with one click.` })])));
  },

  find() {
    const w = this.word();
    const q = h('input', { type: 'search', value: this.query, placeholder: `Search ${w}s for this version`, 'aria-label': `Search ${w}s` });
    this.results = h('div', { class: 'stack' });
    const form = h('form', { class: 'tools', onsubmit: e => { e.preventDefault(); this.query = q.value; this.hits = null; this.search(0); } },
      h('div', { style: 'flex:1;max-width:420px' }, q), h('button', { class: 'btn primary', type: 'submit' }, ico('search'), 'Search'),
      h('span', { class: 'hint', text: 'Results come from Modrinth and match your server version.' }));
    if (this.hits) this.drawHits();
    return h('div', {}, form, this.results);
  },

  async search(offset) {
    if (this.searching) return;
    this.searching = true;
    if (!this.hits) this.results.replaceChildren(h('p', { class: 'hint', text: 'Searching...' }));
    try {
      const r = await api(srvUrl(`/plugins/search?q=${encodeURIComponent(this.query)}&offset=${offset}`));
      this.hits = offset ? [...(this.hits || []), ...r.hits] : r.hits; this.total = r.total; this.offset = offset; if (!offset) this.suggest = r.suggest || [];
      if (this.tab === 'find') this.drawHits();
    } catch (e) { fail(e); this.results.replaceChildren(h('p', { class: 'hint', text: e.message })); }
    finally { this.searching = false; }
  },

  drawHits() {
    if (!this.hits.length) {
      const w = this.word(), sg = this.suggest || [];
      this.results.replaceChildren(h('div', { class: 'card empty' }, h('h2', { text: this.query ? 'Nothing found' : `No ${w}s for Minecraft ${this.info.version} yet` }),
        h('p', { text: this.query ? `Try a shorter or different word. Only results made for Minecraft ${this.info.version} are shown.`
          : `${cap(w)}s are made for one Minecraft version at a time, and ${this.info.version} is very new.` + (sg.length ? ` Most popular ${w}s are made for ${sg.join(', ')}. Create a new server with one of those versions to use them.` : ' Create a server with an older version to get more choice.') }),
        h('button', { class: 'btn primary', type: 'button', onclick: () => go('servers') }, ico('plus'), 'Create another server')));
      return;
    }
    const have = new Set(this.info.items.map(p => p.title.toLowerCase()));
    const cards = this.hits.map(p => {
      const icon = p.icon ? h('img', { src: p.icon, alt: '', loading: 'lazy', referrerpolicy: 'no-referrer', onerror: e => e.target.replaceWith(h('div', { class: 'ph' })) }) : h('div', { class: 'ph' });
      const busyNow = this.installing.has(p.id);
      const btn = h('button', { class: 'btn small primary', type: 'button', disabled: busyNow, onclick: e => this.install(p, e.currentTarget) }, busyNow ? 'Installing...' : have.has(p.title.toLowerCase()) ? 'Install again' : 'Install');
      return h('div', { class: 'plug' }, icon, h('div', { class: 'body' },
        h('div', { class: 'row-actions', style: 'justify-content:space-between;flex-wrap:nowrap' }, h('strong', { class: 'nowrap', text: p.title }), btn),
        h('div', { class: 's hint', text: `by ${p.author}, ${Intl.NumberFormat().format(p.downloads)} downloads` }), h('p', { text: p.description })));
    });
    this.results.replaceChildren(h('div', { class: 'grid two' }, cards),
      this.hits.length < this.total ? h('div', { style: 'text-align:center' }, h('button', { class: 'btn', type: 'button', onclick: () => this.search(this.hits.length) }, 'Show more')) : null);
  },

  async install(p, btn) {
    this.installing.add(p.id); btn.disabled = true; btn.textContent = 'Installing...';
    try {
      const r = await api(srvUrl('/plugins/install'), { method: 'POST', json: { project_id: p.id } });
      toast(`${p.title} installed (${r.file}).${r.requires.length ? ' Also needs: ' + r.requires.join(', ') + '.' : ''} Restart the server to load it.`, 'ok');
      this.info = await api(srvUrl('/plugins'));
    } catch (e) { fail(e); }
    finally { this.installing.delete(p.id); if (this.tab === 'find') this.drawHits(); }
  },
};
