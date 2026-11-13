'use strict';
Pages.players = {
  title: 'Players', desc: 'Who is online, who may join, and who is banned.', icon: 'players', group: 'Server', needsServer: true,
  tab: 'online', data: null, loading: false,

  mount(el) { this.body = el; },
  async show() { this.data = null; this.body.replaceChildren(h('p', { class: 'hint', text: 'Loading players...' })); await this.load(); },

  async load() {
    if (this.loading || !currentServer()) return;
    this.loading = true;
    try { this.data = await api(srvUrl('/players')); this.draw(); }
    catch (e) { fail(e); }
    finally { this.loading = false; }
  },

  update(st) {
    if (!this.data || S.page !== 'players') return;
    const now = st.state === 'online' ? st.players.join(',') : '';
    if (now !== this.data.online.join(',') || (st.state === 'online') !== this.data.running) this.load();
  },

  async act(action, name, value = '', btn = null) {
    await busy(btn, async () => {
      const r = await api(srvUrl('/players/action'), { method: 'POST', json: { action, name, value } });
      toast(r.message, 'ok');
      setTimeout(() => this.load(), isOnline() ? 1200 : 0);
    });
  },

  draw() {
    const d = this.data;
    const tile = (l, v) => h('div', { class: 'tile' }, h('div', { class: 'tile-l', text: l }), h('div', { class: 'tile-v', text: v }));
    const t = tabs([['online', 'Online', d.online.length], ['whitelist', 'Whitelist', d.whitelist.length], ['ops', 'Operators', d.ops.length],
      ['bans', 'Banned', d.bans.length + d.ipbans.length], ['known', 'Everyone seen', d.known.length]], this.tab, id => { this.tab = id; this.drawTab(); });
    this.pane = h('div');
    this.body.replaceChildren(
      h('div', { class: 'tiles' }, tile('Online now', `${d.online.length}/${d.max_players}`), tile('Whitelist', d.whitelist_on ? 'On' : 'Off'), tile('Operators', d.ops.length), tile('Banned', d.bans.length + d.ipbans.length)),
      t, this.pane);
    this.drawTab();
  },

  drawTab() { this.pane.replaceChildren(this['tab_' + this.tab]()); },

  nameForm(label, action, extra = {}) {
    const name = h('input', { type: 'text', placeholder: 'Player name', maxlength: 33, 'aria-label': 'Player name', required: true });
    const reason = extra.reason ? h('input', { type: 'text', placeholder: 'Reason (optional)', maxlength: 100, 'aria-label': 'Reason' }) : null;
    return h('form', { class: 'row-actions', style: 'flex-wrap:nowrap;margin-bottom:12px', onsubmit: e => {
      e.preventDefault();
      this.act(action, name.value, reason ? reason.value : '', e.submitter).then(() => { name.value = ''; if (reason) reason.value = ''; });
    } }, h('div', { style: 'flex:1;min-width:120px' }, name), reason ? h('div', { style: 'flex:1;min-width:120px' }, reason) : null,
    h('button', { class: 'btn primary' + (extra.danger ? '' : ''), type: 'submit' }, ico('plus'), label));
  },

  badges(n) {
    const d = this.data, l = n.toLowerCase();
    return [d.ops.some(o => o.name.toLowerCase() === l) ? h('span', { class: 'badge info', text: 'Operator' }) : null,
      d.whitelist.some(o => o.name.toLowerCase() === l) ? h('span', { class: 'badge ok', text: 'Whitelisted' }) : null,
      d.bans.some(o => o.name.toLowerCase() === l) ? h('span', { class: 'badge bad', text: 'Banned' }) : null];
  },

  tab_online() {
    const d = this.data;
    if (!d.online.length) return h('div', { class: 'card empty' }, h('h2', { text: d.running ? 'Nobody is online' : 'The server is off' }), h('p', { text: d.running ? 'Players show up here when they join.' : 'Start the server to see and manage players who are online.' }));
    return h('ul', { class: 'list' }, d.online.map(n => {
      const isOp = d.ops.some(o => o.name.toLowerCase() === n.toLowerCase());
      const gm = h('select', { 'aria-label': 'Game mode for ' + n, style: 'width:auto', onchange: e => { if (e.target.value) this.act('gamemode', n, e.target.value); e.target.value = ''; } },
        h('option', { value: '', text: 'Game mode' }), ['survival', 'creative', 'adventure', 'spectator'].map(m => h('option', { value: m, text: cap(m) })));
      return h('li', {}, avatar(n), h('div', { class: 'grow' }, h('div', { class: 't', text: n }), h('div', { class: 'row-actions' }, this.badges(n))),
        h('div', { class: 'row-actions' }, gm,
          h('button', { class: 'btn small', onclick: async () => { const m = await promptBox('Message ' + n, 'Message', '', 'Send'); if (m) this.act('message', n, m); } }, 'Message'),
          h('button', { class: 'btn small', onclick: e => this.act(isOp ? 'deop' : 'op', n, '', e.currentTarget) }, isOp ? 'Remove operator' : 'Make operator'),
          h('button', { class: 'btn small', onclick: async () => { const r = await promptBox('Kick ' + n, 'Reason (optional)', '', 'Kick'); if (r !== null) this.act('kick', n, r); } }, 'Kick'),
          h('button', { class: 'btn small ghost-danger', onclick: async () => { const r = await promptBox('Ban ' + n, 'Reason (optional)', '', 'Ban'); if (r !== null) this.act('ban', n, r); } }, 'Ban')));
    }));
  },

  tab_whitelist() {
    const d = this.data;
    const sw = h('input', { type: 'checkbox', checked: d.whitelist_on, onchange: e => this.act('whitelist_toggle', '', e.target.checked ? 'on' : 'off', e.target) });
    return h('div', {},
      h('div', { class: 'card' }, h('div', { class: 'card-h' }, h('div', { class: 'grow' }, h('h2', { text: 'Only listed players can join' }), h('p', { class: 'hint', text: 'Recommended for private servers. Everyone else is turned away.' })),
        h('label', { class: 'switch' }, sw, h('i')))),
      h('div', { class: 'card' }, this.nameForm('Add to whitelist', 'whitelist_add'),
        h('ul', { class: 'list' }, d.whitelist.length ? d.whitelist.map(p => h('li', {}, avatar(p.name), h('span', { class: 't grow', text: p.name }),
          h('button', { class: 'btn small ghost-danger', onclick: e => this.act('whitelist_remove', p.name, '', e.currentTarget) }, 'Remove'))) : [h('li', { class: 'none', text: 'Nobody is on the whitelist.' })])));
  },

  tab_ops() {
    const d = this.data;
    return h('div', { class: 'card' }, h('p', { class: 'hint', style: 'margin-bottom:10px', text: 'Operators can use admin commands like gamemode, kick and ban. Only add people you trust.' }),
      this.nameForm('Make operator', 'op'),
      h('ul', { class: 'list' }, d.ops.length ? d.ops.map(p => h('li', {}, avatar(p.name), h('span', { class: 't grow', text: p.name }), h('span', { class: 'badge info', text: 'Level ' + p.level }),
        h('button', { class: 'btn small ghost-danger', onclick: e => this.act('deop', p.name, '', e.currentTarget) }, 'Remove'))) : [h('li', { class: 'none', text: 'No operators.' })]));
  },

  tab_bans() {
    const d = this.data;
    return h('div', { class: 'stack' },
      h('div', { class: 'card' }, h('h2', { text: 'Banned players', style: 'margin-bottom:10px' }), this.nameForm('Ban player', 'ban', { reason: true }),
        h('ul', { class: 'list' }, d.bans.length ? d.bans.map(p => h('li', {}, avatar(p.name), h('div', { class: 'grow' }, h('div', { class: 't', text: p.name }), h('div', { class: 's', text: [p.reason, p.created && p.created.slice(0, 10)].filter(Boolean).join(', ') })),
          h('button', { class: 'btn small', onclick: e => this.act('pardon', p.name, '', e.currentTarget) }, 'Unban'))) : [h('li', { class: 'none', text: 'Nobody is banned.' })])),
      d.ipbans.length ? h('div', { class: 'card' }, h('h2', { text: 'Banned IP addresses', style: 'margin-bottom:10px' }),
        h('ul', { class: 'list' }, d.ipbans.map(p => h('li', {}, h('span', { class: 't grow mono', text: p.ip }), h('span', { class: 's', text: p.reason }),
          h('button', { class: 'btn small', onclick: e => this.act('ip_unban', '', p.ip, e.currentTarget) }, 'Unban'))))) : null);
  },

  tab_known() {
    const d = this.data;
    if (!d.known.length) return h('div', { class: 'card empty' }, h('h2', { text: 'Nobody has joined yet' }), h('p', { text: 'Players appear here after their first visit, so you can whitelist or ban them with one click.' }));
    return h('ul', { class: 'list' }, d.known.map(n => h('li', {}, avatar(n), h('div', { class: 'grow' }, h('div', { class: 't', text: n }), h('div', { class: 'row-actions' }, this.badges(n))),
      h('div', { class: 'row-actions' },
        h('button', { class: 'btn small', onclick: e => this.act('whitelist_add', n, '', e.currentTarget) }, 'Whitelist'),
        h('button', { class: 'btn small', onclick: e => this.act('op', n, '', e.currentTarget) }, 'Operator'),
        h('button', { class: 'btn small ghost-danger', onclick: async () => { const r = await promptBox('Ban ' + n, 'Reason (optional)', '', 'Ban'); if (r !== null) this.act('ban', n, r); } }, 'Ban')))));
  },
};
