'use strict';
Pages.console = {
  title: 'Console', desc: 'Live server log. Type a command at the bottom.', icon: 'console', group: 'Server', needsServer: false,
  lines: [], filter: 'all', query: '', hist: [], hidx: 0,

  classify(text) {
    if (text.startsWith('[panel]') || text.startsWith('[buildtools]')) return 'panel-line';
    if (text.startsWith('> ')) return 'cmd-line';
    if (/\/(ERROR|FATAL)\]/.test(text) || /Exception|\bERROR\b/.test(text)) return 'err';
    if (/\/WARN\]/.test(text) || /\bWARN\b/.test(text)) return 'warn';
    return '';
  },
  isChat: t => /\]:\s<[^>]+>/.test(t) || /(joined|left) the game/.test(t),
  matches(l) {
    if (this.filter === 'chat' && !l.chat) return false;
    if (this.filter === 'problems' && !(l.cls === 'warn' || l.cls === 'err')) return false;
    if (this.filter === 'panel' && !(l.cls === 'panel-line' || l.cls === 'cmd-line')) return false;
    return !this.query || l.text.toLowerCase().includes(this.query);
  },
  node(l) { return h('div', { class: l.cls, text: l.text }); },

  addLine(raw) {
    const text = String(raw).replace(/\x1b\[[0-9;?]*[A-Za-z]|§[0-9a-fk-or]/gi, '');
    const l = { text, cls: this.classify(text), chat: this.isChat(text) };
    this.lines.push(l);
    if (this.lines.length > 3000) this.lines.shift();
    if (!this.log) return;
    if (this.matches(l)) {
      this.log.append(this.node(l));
      while (this.log.childElementCount > 2000) this.log.firstChild.remove();
      if (this.auto.checked) this.log.scrollTop = this.log.scrollHeight;
    }
  },
  redraw() {
    this.log.replaceChildren(...this.lines.filter(l => this.matches(l)).slice(-2000).map(l => this.node(l)));
    this.log.scrollTop = this.log.scrollHeight;
  },

  start() {
    if (DEMO) { window.demoConsole(t => this.addLine(t)); return; }
    const es = new EventSource('/api/console/stream');
    es.onmessage = e => { try { this.addLine(JSON.parse(e.data)); } catch { /* ignore a broken line */ } };
  },

  mount(el) {
    this.log = h('div', { class: 'log', tabindex: '0', role: 'log', 'aria-label': 'Server log' });
    this.auto = h('input', { type: 'checkbox', checked: true });
    const seg = h('div', { class: 'seg', role: 'group', 'aria-label': 'Filter' });
    const modes = [['all', 'All'], ['chat', 'Chat and joins'], ['problems', 'Problems'], ['panel', 'Panel and commands']];
    const drawSeg = () => seg.replaceChildren(...modes.map(([id, label]) => h('button', { type: 'button', 'aria-pressed': String(this.filter === id), onclick: () => { this.filter = id; drawSeg(); this.redraw(); } }, label)));
    drawSeg();
    this.input = h('input', { type: 'text', autocomplete: 'off', spellcheck: 'false', list: 'cmd-list', 'aria-label': 'Command' });
    const cmds = ['say ', 'list', 'save-all', 'stop', 'op ', 'deop ', 'kick ', 'ban ', 'pardon ', 'whitelist add ', 'whitelist remove ', 'whitelist list', 'whitelist on', 'whitelist off',
      'gamemode survival ', 'gamemode creative ', 'difficulty peaceful', 'difficulty normal', 'time set day', 'time set night', 'weather clear', 'tp ', 'give ', 'seed', 'tps', 'plugins', 'version',
      'gamerule keepInventory true', 'gamerule doDaylightCycle false', 'setworldspawn', 'worldborder set ', 'effect give ', 'xp add ', 'title @a title ', 'help'];
    this.quick = ['save-all', 'list', 'time set day', 'weather clear'].map(c => h('button', { class: 'btn small', type: 'button', 'data-cmd': c, onclick: () => this.send(c) }, c));
    this.form = h('form', { class: 'cmd', onsubmit: e => { e.preventDefault(); this.send(this.input.value); this.input.value = ''; } },
      h('span', { class: 'prompt', 'aria-hidden': 'true', text: '>' }), this.input, h('datalist', { id: 'cmd-list' }, cmds.map(c => h('option', { value: c }))),
      h('button', { class: 'btn primary', type: 'submit' }, 'Send'));
    this.input.addEventListener('keydown', e => {
      if (!this.hist.length || (e.key !== 'ArrowUp' && e.key !== 'ArrowDown')) return;
      e.preventDefault();
      this.hidx = Math.max(0, Math.min(this.hist.length, this.hidx + (e.key === 'ArrowUp' ? -1 : 1)));
      this.input.value = this.hist[this.hidx] || '';
    });
    this.dl = h('a', { class: 'btn small', href: '#', onclick: e => { const s = currentServer(); if (!s) { e.preventDefault(); return; } e.currentTarget.href = `/api/servers/${s.id}/download?path=logs/latest.log`; } }, ico('download'), 'latest.log');
    const search = h('input', { type: 'search', placeholder: 'Search the log', 'aria-label': 'Search the log', oninput: e => { this.query = e.target.value.toLowerCase(); this.redraw(); } });
    el.append(
      h('div', { class: 'tools' }, seg, h('div', { style: 'width:200px' }, search), h('span', { class: 'grow' }),
        h('label', { class: 'check', style: 'margin:0;align-items:center' }, this.auto, h('span', { text: 'Follow new lines' })),
        h('button', { class: 'btn small', type: 'button', onclick: () => { this.lines.length = 0; this.redraw(); } }, 'Clear screen'), this.dl),
      this.log, this.form,
      h('div', { class: 'tools', style: 'margin:10px 0 0' }, h('span', { class: 'hint', text: 'Quick:' }), this.quick));
    this.redraw();
  },
  show() { this.log.scrollTop = this.log.scrollHeight; this.input.focus(); },
  update(st) {
    const ok = st.state === 'online' || st.state === 'starting';
    this.input.disabled = !ok;
    this.input.placeholder = ok ? 'Type a command, like say hello or op YourName' : 'Start the server to send commands';
    this.quick.forEach(b => { b.disabled = !ok; });
  },
  async send(text) {
    text = (text || '').trim();
    if (!text) return;
    try {
      await api('/api/command', { method: 'POST', json: { command: text } });
      if (this.hist[this.hist.length - 1] !== text) this.hist.push(text);
      this.hidx = this.hist.length;
    } catch (e) { fail(e); }
  },
};
