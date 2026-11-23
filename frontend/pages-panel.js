'use strict';
/* Panel settings: look, defaults for new servers, advanced paths, and facts about this PC. */
Pages.panel = {
  title: 'Panel settings', nav: 'Panel', desc: 'How the panel looks and what new servers start with.', icon: 'panel', group: 'Panel', needsServer: false,
  THEMES: [
    ['frost', 'Frosted', 'Soft glass, blue accent', ['#46545a', '#2c373c', '#2f7bff', '#7fb0ff']],
    ['deepslate', 'Deepslate', 'Dark blue and grass green', ['#13161d', '#1a1e29', '#5cbf4a', '#52c7e0']],
    ['nether', 'Nether', 'Dark red and fire orange', ['#1a1214', '#241719', '#ff7a45', '#c58bff']],
    ['daylight', 'Daylight', 'Light, for bright rooms', ['#eef1f6', '#ffffff', '#2f9e44', '#1c7ed6']],
  ],

  mount(el) { this.body = el; },
  async show() {
    if (!S.sys) { try { S.sys = await api('/api/system'); } catch { /* shown by the banner */ } }
    try { this.win = await api('/api/windows'); } catch { this.win = null; }
    try { await Privacy.load(); } catch { /* card shows defaults */ }
    if (!Updates.info) await Updates.check(false);
    this.draw();
  },

  /* Windows only: start with Windows, keep the PC awake, tray notices. Each switch saves at once. */
  windowsCard() {
    const w = this.win;
    if (!w || !w.available) return null;
    const row = (key, text, hint) => h('div', {}, h('label', { class: 'check' },
      h('input', { type: 'checkbox', checked: !!w[key], onchange: e => {
        const on = e.target.checked;
        busy(null, async () => { try { this.win = await api('/api/windows', { method: 'PUT', json: { [key]: on } }); toast('Saved.', 'ok'); } catch (err) { e.target.checked = !on; throw err; } });
      } }), h('span', { text })), h('p', { class: 'hint', style: 'margin:-2px 0 8px 28px', text: hint }));
    return h('section', { class: 'card', style: 'margin-top:14px' }, h('div', { class: 'card-h' }, h('h2', { text: 'Windows' })),
      row('autostart', `Start ${BRAND.name} when I sign in to Windows`, 'It starts quietly in the tray. Only for your Windows user.'),
      row('keep_awake', 'Keep this PC awake while a server is running', 'Windows will not go to sleep and cut your friends off. It sleeps normally when no server runs.'),
      this.win.glass_supported ? row('glass_window', 'Transparent window (experimental)', 'Shows a blurred view of your desktop behind the window. Restart ' + BRAND.name + ' to apply. If anything looks wrong, turn it off.') : null,
      row('toasts', 'Show a notice when a server starts, stops or crashes', 'A small Windows notice from the tray icon. Player joins are never shown.'));
  },

  draw() {
    const s = S.st.settings, y = S.sys || {};
    const themes = h('div', { class: 'themes' }, this.THEMES.map(([id, name, note, sw]) => h('div', { class: 'theme' },
      h('input', { type: 'radio', name: 'theme', id: 'th-' + id, value: id, checked: s.theme === id, onchange: () => {
        applyTheme(id); S.theme = id;
        busy(null, async () => { await api('/api/settings', { method: 'PUT', json: { theme: id } }); toast(`${name} theme saved.`, 'ok'); });
      } }),
      h('label', { for: 'th-' + id }, h('div', { class: 'swatch' }, sw.map(c => h('i', { style: 'background:' + c }))), name, h('div', { class: 'hint', style: 'font-weight:400', text: note })))));

    const f = this.f = {
      ram: h('input', { type: 'number', id: 'p-ram', min: 512, step: 256, value: s.default_ram_mb }),
      restart: h('input', { type: 'checkbox', checked: s.auto_restart }), flags: h('input', { type: 'checkbox', checked: s.tuned_flags }),
      jvm: h('input', { type: 'text', id: 'p-jvm', value: s.jvm_args, placeholder: 'For example -Dfile.encoding=UTF-8' }),
      contact: h('input', { type: 'text', id: 'p-contact', value: s.contact, placeholder: 'you@example.com' }),
      java: h('input', { type: 'text', id: 'p-java', value: s.java_path, placeholder: 'Leave empty to find or download Java automatically' }),
      pp: h('input', { type: 'text', id: 'p-pp', value: s.playit_path, placeholder: 'Leave empty to let the panel download its own helper' }),
      bk: h('input', { type: 'text', id: 'p-bk', value: s.backup_dir || '', placeholder: 'Empty = inside the app data folder' }),
      secret: h('input', { type: 'password', id: 'p-secret', autocomplete: 'new-password' }), clear: h('input', { type: 'checkbox' }),
    };
    const form = h('form', { class: 'card form', autocomplete: 'off', onsubmit: e => {
      e.preventDefault();
      busy(e.submitter, async () => {
        await api('/api/settings', { method: 'PUT', json: { default_ram_mb: +f.ram.value, auto_restart: f.restart.checked, tuned_flags: f.flags.checked, jvm_args: f.jvm.value,
          contact: f.contact.value, backup_dir: f.bk.value, java_path: f.java.value, playit_path: f.pp.value, playit_secret: f.secret.value, clear_playit_secret: f.clear.checked } });
        toast('Settings saved.', 'ok'); await refresh(); this.draw();
      });
    } },
      h('div', { class: 'card-h' }, h('h2', { text: 'Defaults and behaviour' })),
      h('div', { class: 'field' }, h('label', { for: 'p-ram', text: 'Memory for new servers (MB)' }), f.ram),
      h('label', { class: 'check' }, f.restart, h('span', { text: 'Restart a server that crashes (up to 3 times in 10 minutes)' })),
      h('label', { class: 'check' }, f.flags, h('span', { text: 'Use tuned Java settings. They reduce lag spikes on most PCs.' })),
      h('div', { class: 'field' }, h('label', { for: 'p-jvm', text: 'Extra Java arguments for every server' }), f.jvm),
      h('div', { class: 'field' }, h('label', { for: 'p-contact', text: 'Your email or website' }), f.contact,
        h('p', { class: 'hint', text: 'PaperMC asks everyone who downloads from them to say who they are. It is only sent to their download service.' })),
      h('div', { class: 'field' }, h('label', { for: 'p-bk', text: 'Default folder for backups' }),
        h('div', { class: 'row-actions', style: 'flex-wrap:nowrap' }, f.bk,
          h('button', { class: 'btn', type: 'button', onclick: async () => { const r = await pickPath('folder', f.bk.value, 'Backup folder'); if (r) f.bk.value = r; } }, ico('files'), 'Browse')),
        h('p', { class: 'hint', text: 'Every server saves its backups here, in its own sub-folder. Each server can also pick its own folder on its Backups page. Save the settings to apply.' })),
      h('details', { class: 'adv' }, h('summary', { text: 'Advanced: program locations and keys' }),
        h('div', { style: 'margin-top:12px' },
          h('div', { class: 'field' }, h('label', { for: 'p-java', text: 'Java program' }), f.java),
          h('div', { class: 'field' }, h('label', { for: 'p-pp', text: 'playit helper program' }), f.pp),
          h('div', { class: 'field' }, h('label', { for: 'p-secret', text: 'playit secret key' }), f.secret,
            h('p', { class: 'hint', text: s.playit_secret_set ? 'A key is saved. Leave empty to keep it.' : 'Optional. Gives you the same tunnel on every start.' }),
            s.playit_secret_set ? h('label', { class: 'check' }, f.clear, h('span', { text: 'Remove the saved key' })) : null))),
      h('div', { class: 'form-actions' }, h('button', { class: 'btn primary', type: 'submit' }, ico('save'), 'Save settings')));

    const fact = (k, v) => [h('dt', { text: k }), h('dd', { class: 'mono', text: String(v) })];
    this.body.replaceChildren(
      h('section', { class: 'card', style: 'margin-bottom:14px' }, h('div', { class: 'card-h' }, h('h2', { text: 'Appearance' })), themes),
      form,
      this.windowsCard(),
      Updates.card(),
      Privacy.card(),
      h('section', { class: 'card', style: 'margin-top:14px' }, h('div', { class: 'card-h' }, h('h2', { text: 'This PC and this panel' }), h('button', { class: 'btn small', type: 'button', onclick: e => busy(e.currentTarget, () => api('/api/open-folder', { method: 'POST', json: { which: 'data' } })) }, ico('files'), 'Open data folder')),
        h('dl', { class: 'summary' }, fact('Panel version', S.st.version), fact('Memory', y.ram_total_mb ? `${(y.ram_total_mb / 1024).toFixed(1)} GB` : '-'),
          fact('Processor cores', y.cpus || '-'), fact('Free disk space', y.disk_free_gb != null ? `${y.disk_free_gb} GB` : '-'),
          fact('Git (needed for Spigot)', y.git ? 'Found' : 'Not found'), fact('Data folder', y.data_dir || '-'))));
  },
};
