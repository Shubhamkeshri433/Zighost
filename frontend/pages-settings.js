'use strict';
/* Server settings: the server's own options (name, memory, port, Java arguments, notes) plus every server.properties setting. */
Pages.settings = {
  title: 'Server settings', nav: 'Settings', desc: 'The settings people change most. Nothing is saved until you press Save.',
  icon: 'settings', group: 'Server', needsServer: true,
  sid: null, form: null, saved: false,

  mount(el) { this.body = el; },
  show() { return this.load(); },

  async load() {
    const srv = currentServer();
    if (!srv) return;
    this.sid = srv.id; this.saved = false;
    this.body.replaceChildren(h('p', { class: 'hint', text: 'Loading settings...' }));
    let data;
    try { data = await api(srvUrl('/properties')); } catch (e) { return fail(e); }
    if (this.sid === srv.id) this.draw(srv, data.properties);
  },

  running() { return isRunning() && S.st.server && S.st.server.id === this.sid; },

  update() {
    const srv = currentServer();
    if (srv && srv.id !== this.sid) { this.load(); return; }
    if (!this.cfg) return;
    const run = this.running();
    this.cfg.lock.forEach(i => { i.disabled = run; });
    this.lockNote.hidden = !run;
    this.restartNote.hidden = !(run && this.saved);
  },

  cfgValues() {
    const c = this.cfg;
    return { name: c.name.value.trim(), ram_mb: +c.ram.value, port: +c.port.value, jvm_args: c.jvm.value.trim(), notes: c.notes.value };
  },
  cfgPatch() {
    const now = this.cfgValues(), patch = {};
    for (const k of Object.keys(now)) if (String(now[k]) !== String(this.orig[k])) patch[k] = now[k];
    return patch;
  },
  dirty() {
    this.bar.hidden = !(this.form.hasChanges() || Object.keys(this.cfgPatch()).length);
  },

  draw(srv, props) {
    const total = (S.sys && S.sys.ram_total_mb) || 8192;
    const maxRam = Math.max(1024, Math.floor(total * 0.8 / 256) * 256);
    this.orig = { name: srv.name, ram_mb: srv.ram_mb, port: srv.port, jvm_args: srv.jvm_args || '', notes: srv.notes || '' };
    const c = this.cfg = {};
    const onInput = () => { c.out.textContent = `${c.ram.value} MB`; this.dirty(); };
    c.name = h('input', { type: 'text', maxlength: 40, value: this.orig.name, id: 'sv-name', oninput: onInput });
    c.ram = h('input', { type: 'range', id: 'sv-ram', min: 512, max: maxRam, step: 256, value: Math.min(this.orig.ram_mb, maxRam), oninput: onInput });
    c.out = h('output', { for: 'sv-ram', text: `${c.ram.value} MB` });
    c.port = h('input', { type: 'number', id: 'sv-port', min: 1024, max: 65535, value: this.orig.port, oninput: onInput });
    c.jvm = h('input', { type: 'text', id: 'sv-jvm', value: this.orig.jvm_args, placeholder: 'Leave empty to use the tuned defaults', oninput: onInput });
    c.notes = h('textarea', { id: 'sv-notes', rows: 3, maxlength: 2000, placeholder: 'Anything you want to remember about this server.', oninput: onInput }, this.orig.notes);
    c.lock = [c.name, c.ram, c.port, c.jvm];

    this.lockNote = h('div', { class: 'note warn', hidden: true, text: 'The server is running. Stop it to change its name, memory, port or Java arguments. Game settings below can be edited now and apply after a restart.' });
    this.restartNote = h('div', { class: 'note warn', hidden: true, style: 'display:flex;gap:12px;align-items:center' },
      h('span', { class: 'grow', text: 'Saved. Restart the server so the new settings apply.' }),
      h('button', { class: 'btn small', onclick: e => busy(e.currentTarget, async () => { await api('/api/restart', { method: 'POST' }); this.saved = false; await refresh(); }) }, ico('restart'), 'Restart now'));

    this.form = PropForm.build({ values: props, hide: ['server-port'], onChange: () => this.dirty() });
    const opts = h('section', { class: 'card' },
      h('div', { class: 'card-h' }, h('div', {}, h('h2', { text: 'Server options' }), h('p', { class: 'hint', text: 'How this server runs on your PC.' }))),
      h('div', { class: 'row2' },
        h('div', { class: 'field' }, h('label', { for: 'sv-name', text: 'Name' }), c.name),
        h('div', { class: 'field' }, h('label', { for: 'sv-port', text: 'Port on this PC' }), c.port)),
      h('div', { class: 'field' }, h('label', { for: 'sv-ram' }, 'Memory', c.out), c.ram,
        h('p', { class: 'hint', text: `This PC has ${(total / 1024).toFixed(1)} GB. About 2 GB suits 5 to 10 players. Keep at least a third free for Windows.` })),
      h('details', { class: 'adv' }, h('summary', { text: 'Expert: Java arguments and notes' }),
        h('div', { style: 'margin-top:12px' },
          h('div', { class: 'field' }, h('label', { for: 'sv-jvm', text: 'Extra Java arguments' }), c.jvm,
            h('p', { class: 'hint', text: 'For experts. Added to the start command, for example -Dfile.encoding=UTF-8. Memory is set above, so leave -Xmx out.' })),
          h('div', { class: 'field' }, h('label', { for: 'sv-notes', text: 'Notes' }), c.notes))));

    this.bar = h('div', { class: 'savebar', hidden: true },
      h('span', { text: 'You have unsaved changes.' }), h('span', { class: 'grow' }),
      h('button', { class: 'btn', type: 'button', onclick: () => this.discard() }, 'Discard'),
      h('button', { class: 'btn primary', type: 'button', onclick: e => this.save(e.currentTarget) }, ico('save'), 'Save changes'));

    this.body.replaceChildren(this.lockNote, this.restartNote, this.iconCard(srv), h('div', { style: 'height:14px' }), opts, h('div', { style: 'height:14px' }), PropForm.toolbar(this.form), this.form.el, this.bar);
    this.update();
  },

  iconCard(srv) {
    const holder = h('div', { class: 'wz-iconbox' }, serverIcon(srv));
    const change = h('button', { class: 'btn', type: 'button', onclick: async () => {
      const r = await IconPicker.open({ hasIcon: !!srv.icon, name: srv.name, motd: '' });
      if (!r) return;
      await busy(null, async () => {
        if (r.remove) await api('/api/servers/' + srv.id + '/icon', { method: 'DELETE' });
        else if (r.blob) await api('/api/servers/' + srv.id + '/icon', { method: 'PUT', body: r.blob });
        toast(r.remove ? 'Icon removed.' : 'Icon saved. Minecraft shows it after the next start.', 'ok');
        await refresh(); this.load();
      });
    } }, ico('image'), 'Change icon');
    return h('section', { class: 'card' },
      h('div', { class: 'card-h' }, h('div', {}, h('h2', { text: 'Server icon' }), h('p', { class: 'hint', text: 'Shown here and in your friends\' Minecraft server list.' }))),
      h('div', { class: 'wz-id' }, h('div', { class: 'wz-icon-col' }, holder, change)));
  },

  discard() {
    const o = this.orig, c = this.cfg;
    c.name.value = o.name; c.ram.value = o.ram_mb; c.port.value = o.port; c.jvm.value = o.jvm_args; c.notes.value = o.notes;
    c.out.textContent = `${c.ram.value} MB`;
    this.form.discard();
    this.dirty();
  },

  async save(btn) {
    await busy(btn, async () => {
      const patch = this.cfgPatch(), props = this.form.changed(), wasRunning = this.running();
      if (Object.keys(patch).length) await api('/api/servers/' + this.sid, { method: 'PATCH', json: patch });
      if (Object.keys(props).length) await api(srvUrl('/properties'), { method: 'PUT', json: { properties: props } });
      Object.assign(this.orig, this.cfgValues());
      this.form.markSaved();
      this.saved = wasRunning && (Object.keys(props).length > 0);
      toast('Settings saved.', 'ok');
      await refresh();
      this.dirty(); this.update();
    });
  },
};
