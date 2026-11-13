'use strict';
/* Automation: scheduled jobs for the selected server (restart, back up, run a command) and Discord notices. */
Pages.automation = {
  title: 'Automation', desc: 'Jobs that run by themselves, and notices in Discord.', icon: 'automation', group: 'Server', needsServer: false,
  sid: null, jobs: [], saved: '', loaded: false,

  PRESETS: [
    { t: 'Daily backup at 04:00, keep 7', job: { kind: 'backup', mode: 'at', at: '04:00', keep: 7 } },
    { t: 'Restart every 12 hours', job: { kind: 'restart', mode: 'every', every_min: 720 } },
    { t: 'Save the world every 30 minutes', job: { kind: 'command', mode: 'every', every_min: 30, command: 'save-all' } },
    { t: 'Message players every hour', job: { kind: 'command', mode: 'every', every_min: 60, command: 'say Remember to take a break and drink water.' } },
  ],

  mount(el) { this.body = el; },
  async show() { this.loaded = false; await this.load(); },
  update() {
    const srv = currentServer();
    if (srv && srv.id !== this.sid && this.loaded) this.load();
    if (!srv && this.loaded && this.sid) this.load();
  },

  async load() {
    const srv = currentServer();
    this.sid = srv ? srv.id : null;
    this.jobs = [];
    if (srv) {
      try {
        const r = await api(srvUrl('/schedules'));
        this.jobs = r.schedules.map(j => this.fromApi(j));
      } catch (e) { fail(e); }
    }
    this.saved = JSON.stringify(this.jobs.map(j => this.toApi(j)));
    this.loaded = true;
    this.draw();
  },

  fromApi(j) {
    const o = { ...j };
    const m = j.every_min || 60;
    o._unit = m % 1440 === 0 ? 1440 : m % 60 === 0 ? 60 : 1;
    o._val = m / o._unit;
    return o;
  },
  toApi(j) {
    const o = { id: j.id, kind: j.kind, mode: j.mode, enabled: !!j.enabled };
    if (j.mode === 'every') o.every_min = Math.round((+j._val || 0) * (+j._unit || 1));
    else o.at = j.at || '04:00';
    if (j.kind === 'command') o.command = (j.command || '').trim();
    if (j.kind === 'backup') o.keep = +j.keep || 5;
    return o;
  },
  isDirty() { return JSON.stringify(this.jobs.map(j => this.toApi(j))) !== this.saved; },
  touch() { if (this.bar) this.bar.hidden = !this.isDirty(); },

  draw() {
    this.body.replaceChildren(this.jobsCard(), this.discordCard());
  },

  newJob(base) {
    const j = this.fromApi({ enabled: true, mode: 'every', every_min: 60, keep: 5, at: '04:00', kind: 'backup', ...base });
    this.jobs.push(j);
    this.draw();
    this.touch();
  },

  jobRow(j) {
    const sel = (opts, val, on) => h('select', { onchange: e => on(e.target.value) }, opts.map(([v, t]) => h('option', { value: v, text: t, selected: v === val })));
    const params = h('div', { class: 'params' });
    const drawParams = () => {
      const kids = [];
      if (j.mode === 'every') {
        kids.push(h('span', { class: 'hint', text: 'every' }),
          h('input', { type: 'number', min: 1, value: j._val, style: 'width:80px', 'aria-label': 'Repeat every', oninput: e => { j._val = e.target.value; this.touch(); } }),
          sel([[1, 'minutes'], [60, 'hours'], [1440, 'days']], j._unit, v => { j._unit = +v; this.touch(); }));
      } else {
        kids.push(h('span', { class: 'hint', text: 'at' }), h('input', { type: 'time', value: j.at || '04:00', 'aria-label': 'Time of day', style: 'width:120px', oninput: e => { j.at = e.target.value; this.touch(); } }));
      }
      if (j.kind === 'backup') kids.push(h('span', { class: 'hint', text: 'keep' }), h('input', { type: 'number', min: 1, max: 50, value: j.keep, style: 'width:70px', 'aria-label': 'Backups to keep', oninput: e => { j.keep = e.target.value; this.touch(); } }));
      if (j.kind === 'command') kids.push(h('input', { type: 'text', value: j.command || '', placeholder: 'say Hello', maxlength: 200, 'aria-label': 'Command', oninput: e => { j.command = e.target.value; this.touch(); } }));
      params.replaceChildren(...kids);
    };
    drawParams();
    return h('div', { class: 'job' },
      h('label', { class: 'switch' }, h('input', { type: 'checkbox', checked: j.enabled, 'aria-label': 'Job is on', onchange: e => { j.enabled = e.target.checked; this.touch(); } }), h('i')),
      sel([['backup', 'Back up the world'], ['restart', 'Restart the server'], ['command', 'Run a command']], j.kind, v => { j.kind = v; drawParams(); this.touch(); }),
      sel([['every', 'Repeat'], ['at', 'Every day']], j.mode, v => { j.mode = v; drawParams(); this.touch(); }),
      params,
      h('button', { class: 'btn small ghost-danger', type: 'button', 'aria-label': 'Remove job', onclick: () => { this.jobs.splice(this.jobs.indexOf(j), 1); this.draw(); this.touch(); } }, ico('trash')));
  },

  jobsCard() {
    if (!currentServer()) return h('section', { class: 'card' }, h('h2', { text: 'Scheduled jobs' }), h('p', { class: 'hint', style: 'margin-top:6px', text: 'Create a server first. Jobs belong to a server.' }));
    const preset = h('select', { 'aria-label': 'Add a ready-made job', onchange: e => { const p = this.PRESETS[+e.target.value]; if (p) this.newJob(p.job); e.target.value = ''; } },
      h('option', { value: '', text: 'Add a ready-made job...' }), this.PRESETS.map((p, i) => h('option', { value: i, text: p.t })));
    this.bar = h('div', { class: 'savebar', hidden: true }, h('span', { text: 'You have unsaved changes.' }), h('span', { class: 'grow' }),
      h('button', { class: 'btn', type: 'button', onclick: () => this.load() }, 'Discard'),
      h('button', { class: 'btn primary', type: 'button', onclick: e => this.save(e.currentTarget) }, ico('save'), 'Save jobs'));
    return h('section', { class: 'card' },
      h('div', { class: 'card-h' }, h('div', {}, h('h2', { text: `Scheduled jobs for ${currentServer().name}` }),
        h('p', { class: 'hint', text: 'Jobs run while this panel is open and the server is online. Restarts warn players 60, 30 and 10 seconds ahead.' })),
        preset, h('button', { class: 'btn', type: 'button', onclick: () => this.newJob({}) }, ico('plus'), 'Add job')),
      this.jobs.length ? h('div', {}, this.jobs.map(j => this.jobRow(j))) : h('p', { class: 'hint', text: 'No jobs yet. A daily backup is a good first one.' }),
      this.bar);
  },

  async save(btn) {
    await busy(btn, async () => {
      const r = await api(srvUrl('/schedules'), { method: 'PUT', json: { schedules: this.jobs.map(j => this.toApi(j)) } });
      this.jobs = r.schedules.map(j => this.fromApi(j));
      this.saved = JSON.stringify(this.jobs.map(j => this.toApi(j)));
      toast('Jobs saved.', 'ok');
      this.draw();
    });
  },

  discordCard() {
    const s = S.st.settings;
    const url = h('input', { type: 'password', id: 'dc-url', autocomplete: 'off', placeholder: s.discord_webhook_set ? 'A link is saved. Leave empty to keep it.' : 'https://discord.com/api/webhooks/...' });
    const ns = h('input', { type: 'checkbox', id: 'dc-server', checked: s.notify_server });
    const np = h('input', { type: 'checkbox', id: 'dc-players', checked: s.notify_players });
    return h('form', { class: 'card form', autocomplete: 'off', style: 'margin-top:14px;max-width:680px', onsubmit: e => {
      e.preventDefault();
      busy(e.submitter, async () => {
        await api('/api/settings', { method: 'PUT', json: { discord_webhook: url.value.trim(), notify_server: ns.checked, notify_players: np.checked } });
        url.value = ''; toast('Discord settings saved.', 'ok'); await refresh(); this.draw();
      });
    } },
      h('div', { class: 'card-h' }, h('div', {}, h('h2', { text: 'Discord notices' }), h('p', { class: 'hint', text: 'Post a message in a Discord channel when something happens. Works for every server.' }))),
      h('div', { class: 'field' }, h('label', { for: 'dc-url', text: 'Webhook link' }), url,
        h('p', { class: 'hint', text: (s.discord_webhook_set ? 'A link is saved on this PC. ' : '') + 'In Discord: channel settings, Integrations, Webhooks, New webhook, Copy link. The link is kept on this PC and never shown again.' })),
      h('label', { class: 'check' }, ns, h('span', { text: 'Server starts, stops or crashes' })),
      h('label', { class: 'check' }, np, h('span', { text: 'A player joins or leaves' })),
      h('div', { class: 'form-actions' }, h('button', { class: 'btn primary', type: 'submit' }, ico('save'), 'Save'),
        h('button', { class: 'btn', type: 'button', disabled: !s.discord_webhook_set, onclick: e => busy(e.currentTarget, async () => { await api('/api/notify/test', { method: 'POST', json: {} }); toast('Test message sent. Check Discord.', 'ok'); }) }, 'Send a test message'),
        s.discord_webhook_set ? h('button', { class: 'btn ghost-danger', type: 'button', onclick: async e => {
          if (!await confirmBox('Remove the Discord link?', 'The link is deleted from this PC. Notices stop until you paste a new link.', 'Remove link', true)) return;
          busy(e.currentTarget, async () => { await api('/api/settings', { method: 'PUT', json: { clear_discord_webhook: true } }); url.value = ''; toast('Discord link removed.', 'ok'); await refresh(); this.draw(); });
        } }, ico('trash'), 'Remove link') : null));
  },
};
