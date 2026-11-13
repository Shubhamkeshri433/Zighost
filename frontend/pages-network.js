'use strict';
/* Network: how friends reach the server. Managed playit helper, or your own playit app, plus connection tests. */
Pages.network = {
  title: 'Network', desc: 'The public address friends use to join, and a test to prove it works.', icon: 'network', group: 'Manage', needsServer: false,
  sig: '', tests: { public: null, local: null },

  mount(el) {
    this.modeEl = h('div');
    this.statusEl = h('section', { class: 'card' });
    this.testEl = h('section', { class: 'card', style: 'margin-top:14px' });
    this.manualEl = h('div');
    this.logEl = h('pre', { class: 'minilog' });
    el.append(this.modeEl, this.statusEl, this.testEl, this.manualEl,
      h('details', { class: 'card adv', style: 'margin-top:14px' }, h('summary', { text: 'Helper details and log' }), this.logEl));
  },
  show() { this.sig = ''; this.drawMode(); this.drawTests(); this.drawManual(); this.update(S.st); },
  update(st) {
    const p = st.playit, sig = JSON.stringify([p, currentServer() && currentServer().port, st.state, st.settings.playit_mode, st.settings.playit_auto]);
    if (sig === this.sig) return;
    this.sig = sig;
    this.drawStatus(p);
    this.logEl.textContent = [p.cmdline ? 'Command: ' + p.cmdline : '', p.version ? 'Helper version: ' + p.version : '', ...(p.log.length ? p.log : ['No output yet.'])].filter(Boolean).join('\n');
  },

  async setSetting(patch) { await api('/api/settings', { method: 'PUT', json: patch }); await refresh(); this.sig = ''; this.drawMode(); this.update(S.st); },

  drawMode() {
    const s = S.st.settings, mode = s.playit_mode;
    const opt = (id, title, note) => h('div', {}, h('input', { type: 'radio', name: 'pmode', id: 'pm-' + id, value: id, checked: mode === id, onchange: () => busy(null, () => this.setSetting({ playit_mode: id })) }),
      h('label', { for: 'pm-' + id }, h('b', { text: title }), h('small', { text: note })));
    this.modeEl.replaceChildren(h('section', { class: 'card', style: 'margin-bottom:14px' }, h('h2', { text: 'How do friends reach your server?' }),
      h('div', { class: 'choice' },
        opt('managed', 'Let the panel handle it (recommended)', 'The panel runs its own copy of the playit helper with the server. Your installed playit app is not used.'),
        opt('external', 'Use my own playit app', 'You run playit yourself, make a tunnel there, and paste the address here.'))));
  },

  drawStatus(p) {
    const srv = currentServer(), s = S.st.settings;
    const kids = [];
    if (p.mode === 'external') {
      const port = srv ? srv.port : 25565;
      kids.push(h('div', { class: 'card-h' }, h('h2', { text: 'Using your own playit app' })),
        h('ol', { style: 'margin:0 0 12px;padding-left:20px;display:grid;gap:6px' },
          h('li', { text: 'Open the playit app on this PC and sign in.' }),
          h('li', {}, 'Add a tunnel: choose Minecraft Java, with local address ', h('code', { text: '127.0.0.1' }), ' and port ', h('code', { text: String(port) }), '.'),
          h('li', { text: 'Copy the address playit shows for that tunnel.' }),
          h('li', { text: 'Paste it in the box below and press Save address.' })),
        p.address ? h('div', { class: 'addr-line' }, h('span', { class: 'addr', text: p.address }), copyBtn(p.address)) : h('p', { class: 'hint', text: 'No address saved yet.' }));
      this.statusEl.replaceChildren(...kids);
      return;
    }
    const titles = { stopped: 'The helper is off', downloading: 'Downloading the helper...', starting: 'Connecting to playit.gg...', needs_claim: 'One step left: link the helper', error: 'The helper stopped', online: 'Connected' };
    const title = p.address && p.state !== 'error' ? 'Connected' : (titles[p.state] || p.state);
    kids.push(h('div', { class: 'card-h' }, h('h2', { text: 'Network helper' }), h('span', { class: 'badge ' + (p.address ? 'ok' : p.state === 'error' ? 'bad' : 'warn'), text: p.address ? 'Online' : cap(p.state.replace('_', ' ')) })),
      h('div', { class: 'net-status' }, h('div', { class: 'big-line', text: title }),
        p.address ? h('div', { class: 'addr-line' }, h('span', { class: 'addr', text: p.address }), copyBtn(p.address)) : null,
        p.state === 'needs_claim' ? h('div', { class: 'note' }, h('strong', { text: 'One step on playit.gg' }), h('ol', { style: 'margin:6px 0 0;padding-left:20px;display:grid;gap:4px' },
          h('li', { text: 'Press Open link. A playit page opens.' }), h('li', { text: 'Sign in (a free playit account is needed). Then press Accept. The page only lets this panel manage its own tunnel, nothing else.' }), h('li', { text: 'Come back here. This page updates by itself.' }))) : null,
        p.account === 'guest' && p.address ? h('p', { class: 'hint', text: 'You are using a guest account. It works, but guest accounts are temporary. You can add an email later on playit.gg.' }) : null,
        p.tunnel_note ? h('div', { class: 'note warn', text: p.tunnel_note }) : null,
        p.error ? h('div', { class: 'note bad', text: p.error }) : null,
        p.other_app_installed ? h('p', { class: 'hint', text: 'A playit app is also installed on this PC. The panel leaves it alone and uses its own copy.' }) : null));
    const running = ['downloading', 'starting', 'needs_claim', 'online'].includes(p.state);
    const acts = [];
    if (p.state === 'needs_claim' && p.claim_url) acts.push(h('a', { class: 'btn primary', href: p.claim_url, target: '_blank', rel: 'noopener' }, ico('link'), 'Open link'));
    acts.push(running
      ? h('button', { class: 'btn', type: 'button', onclick: e => busy(e.currentTarget, () => api('/api/network/stop', { method: 'POST' }).then(refresh)) }, ico('stop'), 'Stop helper')
      : h('button', { class: 'btn primary', type: 'button', onclick: e => busy(e.currentTarget, () => api('/api/network/start', { method: 'POST', json: { sid: srv && srv.id } }).then(refresh)) }, ico('play'), 'Start helper'));
    acts.push(h('button', { class: 'btn', type: 'button', onclick: e => busy(e.currentTarget, async () => { const r = await api('/api/network/diagnostics'); await navigator.clipboard.writeText(r.text).catch(() => {}); toast('Report copied. Paste it in the chat.', 'ok'); }) }, ico('copy'), 'Copy report'));
    if (p.linked) acts.push(h('button', { class: 'btn ghost-danger', type: 'button', onclick: async e => {
      if (!await confirmBox('Unlink playit?', 'The panel forgets this playit link. Next time it asks you to link again (guest or account).', 'Unlink', true)) return;
      busy(e.currentTarget, () => api('/api/network/unlink', { method: 'POST' }).then(refresh)); } }, 'Unlink'));
    kids.push(h('div', { class: 'row-actions' }, acts),
      h('label', { class: 'check', style: 'margin-top:14px' }, h('input', { type: 'checkbox', checked: s.playit_auto, onchange: e => busy(null, () => this.setSetting({ playit_auto: e.target.checked })) }),
        h('span', { text: 'Start the helper together with the server' })));
    if (!srv) kids.push(h('p', { class: 'hint', text: 'Create a server first. The helper tunnels the port of the server that is running.' }));
    this.statusEl.replaceChildren(...kids);
  },

  drawTests() {
    const srv = currentServer(), p = S.st.playit;
    const result = (r) => !r ? null : r.error
      ? h('div', { class: 'note bad', text: r.error })
      : h('div', { class: 'note', style: 'background:var(--primary-soft);border-color:var(--primary)' },
        h('strong', { text: `Works. Answered in ${r.latency_ms} ms.` }), h('div', { class: 'hint', text: `${r.version || 'Unknown version'}, ${r.players_online}/${r.players_max} players` }),
        h('div', { class: 'mono', style: 'margin-top:4px', text: r.motd }));
    const run = (target, btn) => busy(btn, async () => {
      this.tests[target] = null; this.drawTests();
      try { this.tests[target] = await api('/api/network/test', { method: 'POST', json: { target, sid: srv && srv.id } }); }
      catch (e) { this.tests[target] = { error: e.message }; }
      this.drawTests();
    });
    this.testEl.replaceChildren(h('div', { class: 'card-h' }, h('div', {}, h('h2', { text: 'Test the connection' }), h('p', { class: 'hint', text: 'Asks the server the way the Minecraft server list does. Start the server first.' }))),
      h('div', { class: 'grid two' },
        h('div', {}, h('p', { class: 'hint', style: 'margin-bottom:8px', text: 'From this PC (checks the server itself)' }),
          h('button', { class: 'btn', type: 'button', disabled: !srv || !isOnline(), onclick: e => run('local', e.currentTarget) }, ico('refresh'), 'Test this PC'), h('div', { style: 'margin-top:10px' }, result(this.tests.local))),
        h('div', {}, h('p', { class: 'hint', style: 'margin-bottom:8px', text: 'Through the public address (what friends use)' }),
          h('button', { class: 'btn', type: 'button', disabled: !p.address || !isOnline(), onclick: e => run('public', e.currentTarget) }, ico('refresh'), 'Test public address'), h('div', { style: 'margin-top:10px' }, result(this.tests.public)))));
  },

  drawManual() {
    const s = S.st.settings;
    const input = h('input', { type: 'text', id: 'net-addr', value: s.playit_address, placeholder: 'name.at.ply.gg:12345', autocomplete: 'off' });
    this.manualEl.replaceChildren(h('form', { class: 'card form', autocomplete: 'off', style: 'margin-top:14px;max-width:620px', onsubmit: e => {
      e.preventDefault();
      busy(e.submitter, async () => { await api('/api/network/address', { method: 'POST', json: { address: input.value } }); toast(input.value.trim() ? 'Address saved.' : 'Address removed.', 'ok'); await refresh(); this.sig = ''; this.update(S.st); });
    } }, h('h2', { text: 'Paste an address yourself' }),
      h('p', { class: 'hint', style: 'margin:4px 0 12px', text: 'Use this if the helper does not find the address, or in "my own app" mode. Empty the box and save to remove it.' }),
      h('div', { class: 'field' }, h('label', { for: 'net-addr', text: 'Address' }), input),
      h('div', { class: 'form-actions' }, h('button', { class: 'btn primary', type: 'submit' }, ico('save'), 'Save address'))));
  },
};
