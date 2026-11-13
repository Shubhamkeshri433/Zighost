'use strict';
/* Create-server wizard: a full-screen popup, one question per step.
   Steps: Type -> Name and icon -> Plugins or Mods (only when the type has them) -> World -> Performance -> Review. */

const Wizard = {
  w: null,
  TYPE_ORDER: ['paper', 'purpur', 'vanilla', 'fabric', 'spigot'],
  TYPE_ICON: { paper: 'bolt', purpur: 'potion', vanilla: 'grass', fabric: 'pickaxe', spigot: 'sword' },
  TYPE_TEXT: {
    paper: 'Fast and friendly. Runs plugins. The best choice for most people.',
    purpur: 'Paper plus many extra switches to change how the game plays.',
    vanilla: 'The game exactly as Mojang made it. No plugins and no mods.',
    fabric: 'For mods that change the game. Every player needs the same mods.',
    spigot: 'The classic plugin server. It is built on your PC, so the first setup takes 5 to 10 minutes.',
  },
  STARTERS: {
    plugins: [
      ['essentialsx', 'EssentialsX', 'Homes, warps, kits and many handy commands.'],
      ['luckperms', 'LuckPerms', 'Permissions: decide who can do what.'],
      ['worldedit', 'WorldEdit', 'Build big things fast.'],
      ['chunky', 'Chunky', 'Pre-make the map so it does not lag when people explore.'],
      ['viaversion', 'ViaVersion', 'Let players with a newer game version join.'],
      ['spark', 'spark', 'Find out what is causing lag.'],
    ],
    mods: [
      ['fabric-api', 'Fabric API', 'Needed by almost every mod.'],
      ['lithium', 'Lithium', 'Makes the server run faster.'],
      ['ferritecore', 'FerriteCore', 'Uses less memory.'],
      ['spark', 'spark', 'Find out what is causing lag.'],
    ],
  },
  WORLD_TYPES: [['minecraft:normal', 'Normal'], ['minecraft:flat', 'Flat'], ['minecraft:large_biomes', 'Large biomes'], ['minecraft:amplified', 'Amplified']],
  MODES: [['survival', 'Survival'], ['creative', 'Creative'], ['adventure', 'Adventure'], ['spectator', 'Spectator']],
  LEVELS: [['peaceful', 'Peaceful'], ['easy', 'Easy'], ['normal', 'Normal'], ['hard', 'Hard']],
  VIEWS: [[8, 'Cozy', 'Less lag. Good for weaker PCs.'], [10, 'Balanced', 'The usual choice.'], [12, 'Far', 'Looks great, needs a strong PC.']],
  SIZES: [[2048, 'Small', 'Up to about 5 friends'], [4096, 'Medium', 'Up to about 15 players'], [6144, 'Large', 'Up to about 30 players']],

  types() { const t = (S.sys && S.sys.types) || {}; return this.TYPE_ORDER.filter(k => t[k]).map(k => [k, t[k]]); },
  extras() { const t = this.types().find(([k]) => k === this.w.type); return t ? t[1].extends : null; },
  steps() {
    const s = [['type', 'Type'], ['id', 'Name and icon']];
    const ex = this.extras();
    if (ex) s.push(['addons', cap(ex)]);
    s.push(['world', 'World'], ['perf', 'Performance'], ['review', 'Review']);
    return s;
  },
  cur() { return this.steps()[this.w.step][0]; },

  async open() {
    if (this.w) return;
    if (!S.sys) { try { S.sys = await api('/api/system'); } catch (e) { return fail(e); } }
    const total = S.sys.ram_total_mb || 8192;
    const used = new Set(S.st.servers.map(s => s.port));
    let port = 25565; while (used.has(port)) port++;
    const blocks = Icons.LIST.filter(i => i.group === 'Blocks');
    const w = this.w = {
      step: 0, type: 'paper', version: '', versions: null, versionError: '', name: '', motd: '',
      icon: { kind: 'item', id: blocks[Math.floor(Math.random() * blocks.length)].id, bg: Icons.BGS[Math.floor(Math.random() * 6)].c, blob: null, url: '' },
      starter: new Set(), seed: '', worldType: 'minecraft:normal', mode: 'survival', level: 'normal', hardcore: false, structures: true, nether: true,
      players: 10, view: 10, ram: Math.min(S.st.settings.default_ram_mb || 2048, Math.max(1024, Math.floor(total * 0.6 / 256) * 256)), port, jvm: '', eula: false, error: '',
    };
    this.body = h('div', { class: 'modal-body' });
    this.bar = h('div', { class: 'wz-steps' });
    this.err = h('span', { class: 'wz-err grow' });
    this.back = h('button', { class: 'btn', type: 'button', onclick: () => this.go(w.step - 1) }, ico('back'), 'Back');
    this.next = h('button', { class: 'btn primary', type: 'button', onclick: e => this.advance(e.currentTarget) });
    const box = h('div', { class: 'wz' },
      h('div', { class: 'modal-head' }, h('h2', { text: 'Create a server' }), h('span', { class: 'grow' }),
        h('button', { class: 'btn small', type: 'button', 'aria-label': 'Close', onclick: () => this.close() }, ico('close'))),
      this.bar, this.body, h('div', { class: 'modal-foot' }, this.back, this.err, this.next));
    this.dlg = Modal.open(box, { full: true, label: 'Create a server', onClose: () => { if (w.icon.url) URL.revokeObjectURL(w.icon.url); this.w = null; } });
    this.dlg.el.onEscape = () => this.close();
    this.draw();
    this.loadVersions();
  },

  async close() {
    const w = this.w; if (!w) return;
    if ((w.name.trim() || w.step > 0) && !await confirmBox('Stop creating this server?', 'What you chose so far is thrown away.', 'Stop', true)) return;
    this.dlg.close();
  },

  async loadVersions() {
    const w = this.w; if (!w) return;
    w.versions = null; w.versionError = ''; w.version = '';
    if (this.cur() === 'type') this.drawStep();
    try {
      const v = (await api('/api/versions?type=' + w.type)).versions;
      if (this.w !== w) return;
      w.versions = v; w.version = v[0] || '';
    } catch (e) { w.versionError = e.message; w.versions = []; }
    if (this.w === w && this.cur() === 'type') { this.drawStep(); this.footer(); }
  },

  go(n) { const w = this.w; if (n < 0 || n >= this.steps().length) return; w.error = ''; w.step = n; this.draw(); },

  /* what is wrong on this step (empty string = fine) */
  problem() {
    const w = this.w, step = this.cur();
    if (step === 'type') return w.versions === null ? 'Loading versions...' : !w.version ? (w.versionError || 'No versions found.') : '';
    if (step === 'id') { const n = w.name.trim(); return !n ? 'Give the server a name.' : n.length > 40 ? 'The name can be up to 40 characters.' : ''; }
    if (step === 'perf') {
      const total = (S.sys && S.sys.ram_total_mb) || 8192;
      if (!(w.ram >= 512)) return 'Memory must be at least 512 MB.';
      if (w.ram > total * 0.8) return `This PC has ${total} MB. Choose ${Math.floor(total * 0.6)} MB or less.`;
      if (!(w.port >= 1024 && w.port <= 65535)) return 'The port must be between 1024 and 65535.';
      if (S.st.servers.some(s => s.port === w.port)) return 'Another server already uses this port.';
      if (!(w.players >= 1 && w.players <= 500)) return 'Players must be between 1 and 500.';
    }
    if (step === 'review') return S.st.install.active ? 'Another server is still being installed. Wait for it to finish.' : !w.eula ? 'Accept the Minecraft EULA to continue.' : '';
    return '';
  },

  async advance(btn) {
    const w = this.w, p = this.problem();
    if (p && this.cur() !== 'review') { w.error = p; this.footer(); return; }
    if (this.cur() !== 'review') { this.go(w.step + 1); return; }
    if (p) { w.error = p; this.footer(); return; }
    await busy(btn, () => this.create());
  },

  draw() {
    const steps = this.steps(), w = this.w;
    this.bar.replaceChildren(...steps.map(([id, label], i) => h('button', { type: 'button', class: 'wz-step' + (i === w.step ? ' on' : '') + (i < w.step ? ' done' : ''), disabled: i > w.step, 'aria-current': i === w.step ? 'step' : null,
      onclick: () => this.go(i) }, h('span', { class: 'wz-n' }, i < w.step ? ico('check') : String(i + 1)), h('span', { class: 'wz-l', text: label }))));
    this.drawStep();
    this.footer();
  },

  footer() {
    const w = this.w, last = this.cur() === 'review';
    this.back.hidden = w.step === 0;
    this.err.textContent = w.error;
    this.next.replaceChildren(...(last ? [ico('plus'), 'Create server'] : ['Next', ico('arrow')]));
    this.next.disabled = last && (!!S.st.install.active || !w.eula);
    this.next.disabled = this.next.disabled || (this.cur() === 'type' && !w.version);
  },

  /* ---------- steps ---------- */
  drawStep() {
    const step = this.cur();
    const el = this['step_' + step]();
    this.body.replaceChildren(h('div', { class: 'wz-page' }, el));
    this.body.scrollTop = 0;
  },
  title(t, sub) { return h('div', { class: 'wz-title' }, h('h3', { text: t }), sub ? h('p', { text: sub }) : null); },
  seg(items, value, on, label) {
    return h('div', { class: 'seg', role: 'radiogroup', 'aria-label': label }, items.map(([v, t]) => h('button', { type: 'button', role: 'radio', 'aria-checked': String(v === value), onclick: () => { on(v); } }, t)));
  },
  field(label, input, hint, id) { return h('div', { class: 'field' }, h('label', { for: id, text: label }), input, hint ? h('p', { class: 'hint', text: hint }) : null); },

  step_type() {
    const w = this.w, types = this.types();
    const cards = types.map(([k, t]) => {
      const cv = h('canvas', {}); Icons.draw(cv, this.TYPE_ICON[k] || 'grass', null, 4);
      return h('button', { type: 'button', class: 'wz-type', 'aria-pressed': String(w.type === k), onclick: () => { if (w.type !== k) { w.type = k; w.starter.clear(); this.draw(); this.loadVersions(); } } },
        k === 'paper' ? h('span', { class: 'wz-rec', text: 'Recommended' }) : null,
        cv, h('strong', { text: t.label }), h('span', { class: 'wz-desc', text: this.TYPE_TEXT[k] || t.note }),
        h('div', { class: 'wz-facts' },
          h('span', { class: 'wz-speed', title: `Speed ${t.speed} of 5` }, h('small', { text: 'Speed' }), ...[1, 2, 3, 4, 5].map(i => h('i', { class: i <= t.speed ? 'on' : '' }))),
          h('span', { class: t.extends === 'plugins' ? 'yes' : 'no', text: (t.extends === 'plugins' ? '✓ ' : '✗ ') + 'Plugins' }),
          h('span', { class: t.extends === 'mods' ? 'yes' : 'no', text: (t.extends === 'mods' ? '✓ ' : '✗ ') + 'Mods' })));
    });
    const sel = h('select', { id: 'wz-ver', 'aria-label': 'Minecraft version', disabled: !w.versions || !w.versions.length, onchange: e => { w.version = e.target.value; this.footer(); } },
      (w.versions || []).map((v, i) => h('option', { value: v, selected: v === w.version, text: i === 0 ? v + ' (latest)' : v })));
    return h('div', {}, this.title('What kind of server?', 'You can not change the type later, but you can always make another server.'),
      h('div', { class: 'wz-ver' }, this.field('Minecraft version', sel, w.versionError ? w.versionError : w.versions === null ? 'Loading versions...' : 'The newest version is a good pick. Pick an older one if your friends use it.', 'wz-ver')),
      h('div', { class: 'wz-types' }, cards));
  },

  iconPreview() {
    const w = this.w, cv = h('canvas', { class: 'wz-icon' });
    if (w.icon.kind === 'item') Icons.draw(cv, w.icon.id, w.icon.bg, 4);
    else if (w.icon.kind === 'blob') { const img = h('img', { class: 'wz-icon', src: w.icon.url, alt: '' }); return img; }
    else { cv.width = cv.height = 64; }
    return cv;
  },

  step_id() {
    const w = this.w;
    const name = h('input', { type: 'text', id: 'wz-name', maxlength: 40, value: w.name, placeholder: 'Friends SMP', autocomplete: 'off', autofocus: true, oninput: e => { w.name = e.target.value; w.error = ''; this.err.textContent = ''; } });
    const motd = h('input', { type: 'text', id: 'wz-motd', maxlength: 120, value: w.motd, placeholder: 'Shown under the name in the Minecraft server list', autocomplete: 'off', oninput: e => { w.motd = e.target.value; } });
    const holder = h('div', { class: 'wz-iconbox' }, this.iconPreview());
    const choose = h('button', { class: 'btn', type: 'button', onclick: async () => {
      const r = await IconPicker.open({ hasIcon: w.icon.kind !== 'none', name: w.name.trim() || 'My server', motd: w.motd });
      if (!r) return;
      if (w.icon.url) URL.revokeObjectURL(w.icon.url);
      if (r.remove) w.icon = { kind: 'none', id: '', bg: null, blob: null, url: '' };
      else if (r.blob) w.icon = { kind: 'blob', id: '', bg: null, blob: r.blob, url: URL.createObjectURL(r.blob) };
      this.drawStep();
    } }, ico('image'), 'Change icon');
    return h('div', {}, this.title('Name your server', 'Friends see the name and icon in their Minecraft server list.'),
      h('div', { class: 'wz-id' }, h('div', { class: 'wz-icon-col' }, holder, choose),
        h('div', { class: 'grow min0' }, this.field('Server name', name, '', 'wz-name'),
          this.field('Message of the day (optional)', motd, 'Leave empty to use the server name.', 'wz-motd'))));
  },

  step_addons() {
    const w = this.w, kind = this.extras(), list = this.STARTERS[kind] || [];
    const ver = w.version || 'this version';
    return h('div', {}, this.title(kind === 'mods' ? 'Add some mods?' : 'Add some plugins?',
      kind === 'mods' ? 'Mods change the game. Players who join need to install the same mods that add new blocks or items.' : 'Plugins add features. Nothing is chosen for you, and you can add more later on the Plugins page.'),
      h('div', { class: 'wz-picks' }, list.map(([id, name, desc]) => h('label', { class: 'wz-pick' }, h('input', { type: 'checkbox', checked: w.starter.has(id), onchange: e => { if (e.target.checked) w.starter.add(id); else w.starter.delete(id); } }),
        h('div', {}, h('strong', { text: name }), h('span', { text: desc }))))),
      h('p', { class: 'hint', text: `They are downloaded from Modrinth for Minecraft ${ver}. If one is not made for this version it is skipped and the rest still install.` }));
  },

  step_world() {
    const w = this.w;
    const seed = h('input', { type: 'text', id: 'wz-seed', value: w.seed, maxlength: 64, placeholder: 'Empty = a random world', autocomplete: 'off', oninput: e => { w.seed = e.target.value; } });
    const sw = (label, key, hint) => h('label', { class: 'check' }, h('input', { type: 'checkbox', checked: w[key], onchange: e => { w[key] = e.target.checked; } }), h('span', {}, label, hint ? h('small', { class: 'hint', text: ' ' + hint }) : null));
    return h('div', {}, this.title('Set up the world'),
      this.field('World seed', seed, 'The same seed always makes the same map. Paste one from a friend or from the internet.', 'wz-seed'),
      h('div', { class: 'field' }, h('label', { text: 'World type' }), this.seg(this.WORLD_TYPES, w.worldType, v => { w.worldType = v; this.drawStep(); }, 'World type')),
      h('div', { class: 'field' }, h('label', { text: 'Game mode' }), this.seg(this.MODES, w.mode, v => { w.mode = v; this.drawStep(); }, 'Game mode')),
      h('div', { class: 'field' }, h('label', { text: 'Difficulty' }), this.seg(this.LEVELS, w.level, v => { w.level = v; this.drawStep(); }, 'Difficulty')),
      sw('Generate villages and other structures', 'structures'), sw('Allow the Nether', 'nether'), sw('Hardcore: players are banned when they die', 'hardcore'));
  },

  step_perf() {
    const w = this.w, total = (S.sys && S.sys.ram_total_mb) || 8192, max = Math.floor(total * 0.8 / 256) * 256;
    const sizes = this.SIZES.filter(([mb]) => mb <= total * 0.6);
    const ramVal = h('strong', { class: 'mono', text: (w.ram / 1024).toFixed(1) + ' GB' });
    const slider = h('input', { type: 'range', min: 1024, max: Math.max(1536, max), step: 256, value: w.ram, 'aria-label': 'Memory', oninput: e => { w.ram = +e.target.value; ramVal.textContent = (w.ram / 1024).toFixed(1) + ' GB'; paintSizes(); } });
    const sizeBox = h('div', { class: 'wz-sizes' });
    const paintSizes = () => sizeBox.replaceChildren(...sizes.map(([mb, t, d]) => h('button', { type: 'button', class: 'wz-size', 'aria-pressed': String(w.ram === mb), onclick: () => { w.ram = mb; slider.value = mb; ramVal.textContent = (mb / 1024).toFixed(1) + ' GB'; paintSizes(); } }, h('strong', { text: t }), h('span', { text: `${mb / 1024} GB` }), h('small', { text: d }))));
    paintSizes();
    const players = h('input', { type: 'number', id: 'wz-pl', min: 1, max: 500, value: w.players, style: 'max-width:120px', oninput: e => { w.players = +e.target.value; } });
    const port = h('input', { type: 'number', id: 'wz-port', min: 1024, max: 65535, value: w.port, style: 'max-width:140px', oninput: e => { w.port = +e.target.value; } });
    const jvm = h('input', { type: 'text', id: 'wz-jvm', value: w.jvm, placeholder: 'For example -Dfile.encoding=UTF-8', autocomplete: 'off', oninput: e => { w.jvm = e.target.value; } });
    return h('div', {}, this.title('How strong should it be?', `This PC has ${(total / 1024).toFixed(1)} GB of memory. Leave some for Windows and your browser.`),
      sizeBox, h('div', { class: 'field' }, h('label', { text: 'Memory for this server' }), h('div', { class: 'wz-ram' }, slider, ramVal)),
      h('div', { class: 'field' }, h('label', { text: 'How far can players see?' }), h('div', { class: 'seg', role: 'radiogroup', 'aria-label': 'View distance' }, this.VIEWS.map(([v, t, d]) => h('button', { type: 'button', role: 'radio', title: d, 'aria-checked': String(w.view === v), onclick: () => { w.view = v; this.drawStep(); } }, t))),
        h('p', { class: 'hint', text: (this.VIEWS.find(x => x[0] === w.view) || [])[2] })),
      this.field('Most players at the same time', players, '', 'wz-pl'),
      h('details', { class: 'adv' }, h('summary', { text: 'Advanced: port and Java arguments' }),
        h('div', { style: 'margin-top:12px' }, this.field('Port', port, 'Picked for you. Change it only if another program already uses it.', 'wz-port'),
          this.field('Extra Java arguments', jvm, 'Only if you know what they do.', 'wz-jvm'))));
  },

  step_review() {
    const w = this.w, t = this.types().find(([k]) => k === w.type)[1];
    const row = (k, v) => [h('dt', { text: k }), h('dd', { text: v })];
    const eula = h('input', { type: 'checkbox', id: 'wz-eula', checked: w.eula, onchange: e => { w.eula = e.target.checked; w.error = ''; this.footer(); } });
    const view = this.VIEWS.find(x => x[0] === w.view)[1];
    return h('div', {}, this.title('Ready to create', 'Check the summary. Everything here can be changed later in Settings, except the server type.'),
      h('div', { class: 'wz-sum' }, h('div', { class: 'wz-iconbox' }, this.iconPreview()),
        h('dl', { class: 'summary' }, ...row('Name', w.name.trim()), ...row('Server', `${t.label} ${w.version}`),
          ...(this.extras() ? row(cap(this.extras()), w.starter.size ? [...w.starter].join(', ') : 'None for now') : []),
          ...row('World', `${this.WORLD_TYPES.find(x => x[0] === w.worldType)[1]}, ${w.mode}, ${w.level}${w.seed ? ', seed ' + w.seed : ''}`),
          ...row('Memory', `${(w.ram / 1024).toFixed(1)} GB, up to ${w.players} players, view ${view.toLowerCase()}`), ...row('Port', String(w.port)))),
      h('label', { class: 'check', for: 'wz-eula', style: 'margin-top:18px' }, eula, h('span', {}, 'I accept the ', h('a', { href: 'https://www.minecraft.net/eula', target: '_blank', rel: 'noopener', text: 'Minecraft EULA' }), '.')),
      h('p', { class: 'hint', text: 'Creating downloads the server and, if needed, Java. This takes a few minutes. You can keep using the panel meanwhile.' }));
  },

  /* ---------- create ---------- */
  async iconBase64() {
    const w = this.w;
    let blob = null;
    if (w.icon.kind === 'item') blob = await Icons.png64(w.icon.id, w.icon.bg);
    else if (w.icon.kind === 'blob') blob = w.icon.blob;
    if (!blob) return '';
    const buf = new Uint8Array(await blob.arrayBuffer());
    let bin = ''; for (let i = 0; i < buf.length; i += 0x8000) bin += String.fromCharCode(...buf.subarray(i, i + 0x8000));
    return btoa(bin);
  },
  async create() {
    const w = this.w;
    const props = { 'level-type': w.worldType, gamemode: w.mode, difficulty: w.level, hardcore: String(w.hardcore), 'generate-structures': String(w.structures), 'allow-nether': String(w.nether),
      'max-players': String(w.players), 'view-distance': String(w.view), 'simulation-distance': String(Math.min(w.view, 10)) };
    if (w.seed.trim()) props['level-seed'] = w.seed.trim();
    try {
      await api('/api/servers', { method: 'POST', json: { name: w.name.trim(), type: w.type, version: w.version, ram_mb: w.ram, port: w.port, jvm_args: w.jvm.trim(),
        motd: w.motd.trim(), eula: w.eula, properties: props, icon: await this.iconBase64(), starter: this.extras() ? [...w.starter] : [] } });
    } catch (e) { w.error = e.message; this.footer(); return; }
    toast('Installing. This takes a few minutes.', 'ok');
    S.dismissedErr = ''; S.lastInstallErr = '';
    this.dlg.close();
    await refresh();
    Pages.servers.listSig = '';
    go('servers');
  },
};
