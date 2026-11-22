'use strict';
/* Plugins and mods: installed list with on/off switch, search and one-click install from Modrinth, upload a jar. */
Pages.plugins = {
  title: 'Plugins and mods', nav: 'Plugins', desc: 'Add features to the selected server. Restart the server after a change.', icon: 'plugins', group: 'Server', needsServer: true,
  sid: null, tab: 'installed', info: null, chk: null, checking: false, updating: new Set(), hits: null, total: 0, offset: 0, query: '', searching: false, installing: new Set(),

  mount(el) { this.body = el; },
  async show() {
    const srv = currentServer();
    if (srv && srv.id !== this.sid) { this.sid = srv.id; this.hits = null; this.query = ''; this.offset = 0; this.chk = null; }
    await this.load();
  },
  update() { const srv = currentServer(); if (srv && srv.id !== this.sid) this.show(); },

  async load() {
    try { this.info = await api(srvUrl('/plugins')); } catch (e) { return fail(e); }
    this.draw();
    this.runCheck();
  },

  /* Ask Modrinth which installed files have a newer version, or none at all for this Minecraft version. */
  async runCheck() {
    if (!this.info || !this.info.supported || !this.info.items.length || this.checking) return;
    this.checking = true; const sid = this.sid;
    try { const r = await api(srvUrl('/plugins/check')); if (sid === this.sid) this.chk = r; }
    catch (e) { if (sid === this.sid) this.chk = { error: e.message, items: {}, counts: {} }; }
    finally { this.checking = false; if (sid === this.sid && this.tab === 'installed' && this.pane) this.pane.replaceChildren(this.installed()); }
  },

  stat(file) { return this.chk && this.chk.items ? this.chk.items[file] : null; },

  async updateOne(p, btn) {
    this.updating.add(p.file);
    await busy(btn, async () => {
      const r = await api(srvUrl('/plugins/update'), { method: 'POST', json: { file: p.file } });
      toast(`${p.title} updated to ${r.version}.${r.requires.length ? ' Also needs: ' + r.requires.join(', ') + '.' : ''} Restart the server to load it.`, 'ok');
    }).finally(() => this.updating.delete(p.file));
    this.chk = null; this.info = await api(srvUrl('/plugins')); this.draw(); this.runCheck();
  },

  async updateAll(btn) {
    await busy(btn, async () => {
      const r = await api(srvUrl('/plugins/update-all'), { method: 'POST' });
      if (r.updated.length) toast(`${r.updated.length} ${this.word()}${r.updated.length === 1 ? '' : 's'} updated. Restart the server to load them.`, 'ok');
      if (r.failed.length) fail(new Error(r.failed.map(f => `${f.file}: ${f.error}`).join(' ')));
    });
    this.chk = null; this.info = await api(srvUrl('/plugins')); this.draw(); this.runCheck();
  },

  banners() {
    const c = this.chk, w = this.word(), out = [];
    if (this.checking && !c) out.push(h('p', { class: 'hint', text: `Checking for ${w} updates...` }));
    if (!c) return out;
    if (c.error) { out.push(h('p', { class: 'hint', text: `Could not check for updates: ${c.error}` })); return out; }
    const title = f => (this.info.items.find(i => i.file === f) || {}).title || f;
    const bad = Object.values(c.items).filter(i => i.status === 'no_build').map(i => title(i.file));
    if (bad.length) out.push(h('div', { class: 'note warn' }, h('strong', { text: `${bad.length} ${w}${bad.length === 1 ? '' : 's'} may not work on Minecraft ${c.version}. ` }),
      h('span', { text: `${bad.join(', ')}: no version for ${c.version} was found. Turn them off or remove them, or change the server version to one they support.` })));
    const n = (c.counts || {}).update || 0;
    if (n) out.push(h('div', { class: 'note', style: 'display:flex;gap:12px;align-items:center' },
      h('span', { class: 'grow', text: `${n} ${w}${n === 1 ? ' has' : 's have'} an update for Minecraft ${c.version}.` }),
      h('button', { class: 'btn small primary', type: 'button', onclick: e => this.updateAll(e.currentTarget) }, ico('download'), 'Update all')));
    return out;
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
      const st = this.stat(p.file);
      const badge = !st ? null : st.status === 'update' ? h('span', { class: 'badge info', text: `Update ${st.current || ''} to ${st.latest}` })
        : st.status === 'no_build' ? h('span', { class: 'badge warn', title: st.note, text: `No version for ${this.chk.version}` })
        : st.status === 'ok' ? h('span', { class: 'badge ok', text: 'Up to date' }) : null;
      const upd = st && st.status === 'update' ? h('button', { class: 'btn small primary', type: 'button', 'aria-label': 'Update ' + p.title, onclick: e => this.updateOne(p, e.currentTarget) }, ico('download'), 'Update') : null;
      return h('li', {}, h('label', { class: 'switch' }, sw, h('i')),
        h('div', { class: 'grow' }, h('div', { class: 't' }, p.title + (p.version ? ' ' + p.version : ''), badge ? ' ' : null, badge),
          h('div', { class: 's nowrap', text: p.description || p.file }), p.description ? h('div', { class: 's mono', text: `${p.file}, ${fmtSize(p.size)}` }) : null),
        st && st.project_id ? h('button', { class: 'btn small', type: 'button', title: 'See all versions', onclick: () => this.openProject(st.project_id, p) }, 'Versions') : null,
        upd,
        h('button', { class: 'btn small ghost-danger', type: 'button', 'aria-label': 'Remove ' + p.title, onclick: async () => {
          if (!await confirmBox(`Remove ${p.title}?`, `The file ${p.file} is deleted. Its settings folder stays.`, 'Remove', true)) return;
          busy(null, async () => { await api(srvUrl('/plugins/remove'), { method: 'POST', json: { file: p.file } }); toast('Removed.', 'ok'); this.load(); });
        } }, ico('trash'), 'Remove'));
    });
    return h('div', {}, ...this.banners(),
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
        h('div', { class: 'row-actions', style: 'justify-content:space-between;flex-wrap:nowrap' }, h('button', { class: 'linklike nowrap', type: 'button', title: 'See all versions', onclick: () => this.openProject(p.id, p), text: p.title }), btn),
        h('div', { class: 's hint', text: `by ${p.author}, ${Intl.NumberFormat().format(p.downloads)} downloads` }), h('p', { text: p.description })));
    });
    this.results.replaceChildren(h('div', { class: 'grid two' }, cards),
      this.hits.length < this.total ? h('div', { style: 'text-align:center' }, h('button', { class: 'btn', type: 'button', onclick: () => this.search(this.hits.length) }, 'Show more')) : null);
  },

  /* ---------- project page: description, pictures and every version, like Modrinth ---------- */
  installedOf(projectId) {
    const c = this.chk && this.chk.items ? Object.values(this.chk.items).find(i => i.project_id === projectId) : null;
    return c ? { file: c.file, number: c.current } : null;
  },

  async openProject(id, hint = {}) {
    this.body.replaceChildren(h('div', { class: 'tools' }, h('button', { class: 'btn', type: 'button', onclick: () => this.draw() }, ico('back'), 'Back'), h('strong', { text: hint.title || '' })),
      h('p', { class: 'hint', text: 'Loading...' }));
    let pr;
    try { pr = await api(srvUrl('/plugins/project?id=' + encodeURIComponent(id))); } catch (e) { fail(e); return this.draw(); }
    this.drawProject(pr);
  },

  drawProject(pr) {
    const w = this.word(), mc = pr.minecraft;
    const mine = this.installedOf(pr.id);
    const icon = pr.icon ? h('img', { src: pr.icon, alt: '', referrerpolicy: 'no-referrer', class: 'proj-icon', onerror: e => e.target.replaceWith(h('div', { class: 'ph proj-icon' })) }) : h('div', { class: 'ph proj-icon' });
    const nice = n => Intl.NumberFormat().format(n);
    const links = Object.entries(pr.links || {}).map(([k, u]) => h('a', { class: 'btn small', href: u, target: '_blank', rel: 'noopener noreferrer' }, cap(k)));
    const head = h('div', { class: 'proj-head' }, icon, h('div', { class: 'grow min0' }, h('h2', { text: pr.title }),
      h('p', { text: pr.summary }), h('p', { class: 'hint', text: `${nice(pr.downloads)} downloads${pr.license ? ', ' + pr.license : ''}${(pr.categories || []).length ? ', ' + pr.categories.join(', ') : ''}` }),
      links.length ? h('div', { class: 'row-actions' }, links) : null));
    const compat = pr.versions.filter(v => v.compatible);
    let showAll = !compat.length;
    const list = h('div', { class: 'card' });
    const drawVersions = () => {
      const vs = showAll ? pr.versions : compat;
      const rows = vs.map(v => {
        const isMine = mine && mine.number === v.number;
        const gv = v.game_versions.filter(x => /^\d+\.\d+(\.\d+)?$/.test(x));
        const range = gv.length > 1 ? `${gv[0]} to ${gv[gv.length - 1]}` : (gv[0] || v.game_versions[0] || '');
        const btn = isMine ? h('span', { class: 'badge ok', text: 'Installed' })
          : h('button', { class: 'btn small' + (v.compatible ? ' primary' : ''), type: 'button', onclick: e => this.installVersion(pr, v, mine, e.currentTarget) }, ico('download'), mine ? 'Switch to this' : 'Install');
        return h('li', { class: 'ver' },
          h('div', { class: 'grow min0' },
            h('div', { class: 't' }, v.number || v.name, ' ', h('span', { class: 'badge ' + (v.type === 'release' ? 'ok' : v.type === 'beta' ? 'warn' : 'bad'), text: v.type || 'release' }), ' ',
              v.compatible ? h('span', { class: 'badge info', text: `Works on ${mc}` }) : h('span', { class: 'badge', text: `Not made for ${mc}` })),
            h('div', { class: 's', text: `Minecraft ${range}, ${v.loaders.join(', ')}, ${(v.date || '').slice(0, 10)}, ${nice(v.downloads)} downloads` }),
            v.changelog ? h('details', {}, h('summary', { text: 'Changes' }), Md.render(v.changelog)) : null),
          btn);
      });
      list.replaceChildren(h('ul', { class: 'list' }, rows.length ? rows : [h('li', { class: 'none', text: 'No versions found.' })]));
    };
    const filter = h('label', { class: 'check' }, h('input', { type: 'checkbox', checked: showAll, onchange: e => { showAll = e.target.checked; drawVersions(); } }),
      h('span', { text: ` Show every version, also the ones not made for Minecraft ${mc}` }));
    drawVersions();
    const gallery = pr.gallery.length ? h('div', { class: 'gallery' }, pr.gallery.map(g => h('img', { src: g.url, alt: g.title || '', loading: 'lazy', referrerpolicy: 'no-referrer' }))) : null;
    const panes = {
      versions: () => h('div', {}, mine ? h('p', { class: 'hint', text: `Installed now: ${mine.number}. Choose another version below to switch. Its settings stay.` }) : null, filter, list),
      about: () => h('div', { class: 'card', style: 'padding:16px' }, gallery, Md.render(pr.body)),
    };
    const pane = h('div');
    const show = id => { pane.replaceChildren(panes[id]()); };
    const t = tabs([['versions', `Versions`, pr.versions.length], ['about', 'Description']], 'versions', show);
    this.body.replaceChildren(h('div', { class: 'tools' }, h('button', { class: 'btn', type: 'button', onclick: () => this.draw() }, ico('back'), 'Back to ' + w + 's')), head, t, pane);
    show('versions');
  },

  async installVersion(pr, v, mine, btn) {
    const w = this.word();
    if (!v.compatible && !await confirmBox(`Install ${pr.title} ${v.number}?`, `This version is not made for Minecraft ${pr.minecraft}. It may not load or may break the server. Install it only if you know it works.`, 'Install anyway', true)) return;
    await busy(btn, async () => {
      const r = await api(srvUrl('/plugins/install'), { method: 'POST', json: { project_id: pr.id, version_id: v.id, allow_other_version: !v.compatible, replace_file: mine ? mine.file : '' } });
      toast(`${pr.title} ${r.version} ${mine ? 'is now installed' : 'installed'}.${r.requires.length ? ' Also needs: ' + r.requires.join(', ') + '.' : ''} Restart the server to load it.`, 'ok');
    });
    this.chk = null; this.info = await api(srvUrl('/plugins'));
    try { this.chk = await api(srvUrl('/plugins/check')); } catch { /* offline: the page still works */ }
    this.openProject(pr.id, { title: pr.title });
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
