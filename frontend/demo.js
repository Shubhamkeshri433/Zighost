'use strict';
/* Preview mode: a pretend server so the dashboard can be viewed and clicked without the backend. */
(() => {
  const now = () => Math.floor(Date.now() / 1000);
  const D = {
    consent: { accepted: true, version: 2, current: 2, accepted_at: now() - 86400, heads: false, updates: true, stats: true, usage_id: 'preview-0000-0000-0000' },
    comp: { running: false, java: { state: 'missing', percent: 0, text: '' }, playit: { state: 'missing', percent: 0, text: '' } },
    win: { autostart: false, keep_awake: true, toasts: true },
    state: 'online', started: now() - 1860, active: 'a1b2c3d4', players: ['Aarav', 'CreeperKing', 'Steve_Rao'],
    servers: [
      { id: 'a1b2c3d4', name: 'Friends SMP', type: 'paper', version: '1.21.4', ram_mb: 2048, port: 25565, motd: 'Welcome to Friends SMP', installed: true, created: now() - 86400 * 9 },
      { id: 'e5f6a7b8', name: 'Creative Build', type: 'vanilla', version: '1.21.4', ram_mb: 2048, port: 25566, motd: 'Build anything', installed: true, created: now() - 86400 * 3 },
    ],
    install: { active: false, step: '', percent: 0, error: '', server_id: '' },
    cpu: 14, ram: 1310,
    playit: { state: 'online', claim_url: '', detected_address: 'friends-smp.at.ply.gg:41872', address: 'friends-smp.at.ply.gg:41872', manual: false, error: '', log: ['tunnel running', 'friends-smp.at.ply.gg:41872 => 127.0.0.1:25565'], has_binary: true, mode: 'managed', version: '1.0.0-demo', cmdline: 'playit-agent --demo', other_app_installed: true, account: 'guest', tunnel_note: '', linked: true },
    settings: { theme: 'deepslate', playit_mode: 'managed', discord_webhook_set: false, notify_server: false, notify_players: false, java_path: '', playit_path: '', playit_address: '', playit_secret_set: false, contact: '', auto_restart: true, tuned_flags: true, default_ram_mb: 2048, playit_auto: true, last_active: 'a1b2c3d4', playit_mode: 'managed', theme: 'deepslate', jvm_args: '', discord_webhook_set: false, notify_server: false, notify_players: false, contact: '' },
    props: { motd: 'Welcome to Friends SMP', gamemode: 'survival', difficulty: 'normal', 'max-players': '20', pvp: 'true', 'online-mode': 'true', 'white-list': 'false', 'view-distance': '10', 'simulation-distance': '10', 'allow-flight': 'false', 'spawn-protection': '16', 'level-seed': '', 'enable-command-block': 'false', 'server-port': '25565', 'level-name': 'world', 'enable-rcon': 'false' },
    whitelist: ['Aarav', 'Steve_Rao'], ops: [{ name: 'Aarav', level: 4 }], bans: [{ name: 'Griefer99', reason: 'Griefing', created: '2026-11-05', source: 'Aarav' }], ipbans: [],
    known: ['Aarav', 'CreeperKing', 'Steve_Rao', 'Griefer99', 'Alex_M'],
    schedules: [{ id: 'j1', kind: 'backup', mode: 'at', at: '04:00', keep: 7, enabled: true }],
    plugins: [
      { file: 'EssentialsX.jar', enabled: true, size: 1_900_000, title: 'EssentialsX', version: '2.20.1', description: 'Essential commands for servers' },
      { file: 'WorldEdit.jar.disabled', enabled: false, size: 4_100_000, title: 'WorldEdit', version: '7.3.8', description: 'In-game map editor' },
    ],
    files: { '': [['plugins', 1], ['world', 1], ['logs', 1], ['server.properties', 0, 1200], ['ops.json', 0, 120], ['eula.txt', 0, 60]], plugins: [['EssentialsX.jar', 0, 1_900_000], ['WorldEdit.jar.disabled', 0, 4_100_000]], world: [['level.dat', 0, 2200]], logs: [['latest.log', 0, 18000]] },
    text: { 'server.properties': '#Minecraft server properties\nmotd=Welcome to Friends SMP\nmax-players=20\n', 'eula.txt': 'eula=true\n', 'ops.json': '[]', 'logs/latest.log': '[10:02:11] [Server thread/INFO]: Done (3.4s)!\n' },
    extra: {
      whitelist: [{ name: 'Aarav', uuid: 'a' }, { name: 'Steve_Rao', uuid: 'b' }], ops: [{ name: 'Aarav', level: 4 }],
      bans: [{ name: 'Griefer99', reason: 'Griefing', created: '2026-11-01', source: 'Aarav' }], ipbans: [], known: ['Aarav', 'CreeperKing', 'Steve_Rao', 'Griefer99'], wl_on: false,
      schedules: [{ id: 'j1', kind: 'backup', mode: 'at', at: '04:00', keep: 7, enabled: true }],
      plugins: [{ file: 'EssentialsX.jar', enabled: true, size: 2_100_000, title: 'EssentialsX', version: '2.20', description: 'Essential commands' }, { file: 'LuckPerms.jar', enabled: false, size: 1_500_000, title: 'LuckPerms', version: '5.4', description: 'Permissions' }],
      files: { '': [{ name: 'plugins', dir: true, size: 0, modified: now() - 900, editable: false }, { name: 'world', dir: true, size: 0, modified: now() - 60, editable: false }, { name: 'server.properties', dir: false, size: 1200, modified: now() - 7200, editable: true }, { name: 'paper.jar', dir: false, size: 48_000_000, modified: now() - 86400, editable: false }], plugins: [{ name: 'EssentialsX.jar', dir: false, size: 2_100_000, modified: now() - 900, editable: false }] },
    },
    backups: [
      { name: '20261109-210000_manual.zip', size: 148_000_000, created: now() - 3600 * 3 },
      { name: '20261108-183000_before-restore.zip', size: 141_000_000, created: now() - 86400 },
    ],
  };
  window.MCP_DEMO_HISTORY = {
    cpu: Array.from({ length: 70 }, (_, i) => 12 + 8 * Math.sin(i / 6) + (i % 7)),
    ram: Array.from({ length: 70 }, (_, i) => 1100 + i * 3 + 60 * Math.sin(i / 9)),
  };
  let emit = () => {};
  const log = t => emit(t);
  const stamp = () => new Date().toTimeString().slice(0, 8);
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const err = m => { throw new Error(m); };

  setInterval(() => {
    if (D.state === 'online') {
      D.cpu = Math.max(3, Math.min(60, D.cpu + (Math.random() - .5) * 8));
      D.ram = Math.max(1000, Math.min(1900, D.ram + (Math.random() - .45) * 40));
      if (Math.random() < .25) {
        const p = D.players[Math.floor(Math.random() * D.players.length)];
        if (p) log(`[${stamp()} INFO]: <${p}> ${['anyone near the village?', 'brb', 'found diamonds!', 'nice build'][Math.floor(Math.random() * 4)]}`);
      }
    }
  }, 1500);

  function status() {
    const running = ['starting', 'online', 'stopping'].includes(D.state);
    return {
      version: '0.1.0', state: D.install.active && !running ? 'installing' : D.state,
      server: D.servers.find(s => s.id === D.active) || null,
      players: D.state === 'online' ? D.players : [], uptime: running ? now() - D.started : 0,
      install: { ...D.install }, servers: D.servers, playit: { ...D.playit }, settings: { ...D.settings }, now: now(),
      metrics: { sys_ram_total_mb: 16384, sys_ram_used_pct: 58, sys_cpu_pct: 22, ram_mb: running ? Math.round(D.ram) : 0, cpu_pct: running ? Math.round(D.cpu * 10) / 10 : 0 },
    };
  }

  const TYPES = {
    paper: { label: 'Paper', speed: 5, extends: 'plugins', note: 'Fast, plugin support. Best for most people.' },
    vanilla: { label: 'Vanilla', speed: 3, extends: null, note: 'Official Mojang server, no plugins.' },
    purpur: { label: 'Purpur', speed: 5, extends: 'plugins', note: 'Paper with extra settings.' },
    fabric: { label: 'Fabric', speed: 5, extends: 'mods', note: 'Mods (lightweight).' },
    spigot: { label: 'Spigot', speed: 3, extends: 'plugins', note: 'Plugins. Built on your PC, takes 5-10 minutes.' },
  };

  async function demoStart(sid) {
    if (D.state !== 'offline') err('A server is already running or installing. Stop it first.');
    D.active = sid; D.state = 'starting'; D.started = now();
    const s = D.servers.find(x => x.id === sid);
    log(`[panel] Starting ${s.name} (${s.type} ${s.version}, ${s.ram_mb} MB)`);
    setTimeout(() => log(`[${stamp()} INFO]: Starting minecraft server version ${s.version}`), 400);
    setTimeout(() => log(`[${stamp()} INFO]: Preparing level "world"`), 1200);
    setTimeout(() => { D.state = 'online'; log(`[${stamp()} INFO]: Done (3.412s)! For help, type "help"`); }, 2600);
  }
  function demoStop() {
    if (D.state !== 'online') err('The server is not running.');
    D.state = 'stopping'; log('[panel] Stopping. Saving the world...');
    setTimeout(() => { D.state = 'offline'; log('[panel] Server stopped.'); }, 2200);
  }

  window.demoConsole = add => {
    emit = add;
    ['[panel] Preview mode: this is a pretend server. Nothing is installed or started on your PC.',
      `[${stamp()} INFO]: Starting minecraft server version 1.21.4`,
      `[${stamp()} INFO]: Loading properties`,
      `[${stamp()} WARN]: Can't keep up! Is the server overloaded? Running 2300ms behind`,
      `[${stamp()} INFO]: Done (3.412s)! For help, type "help"`,
      `[${stamp()} INFO]: Aarav joined the game`, `[${stamp()} INFO]: Steve_Rao joined the game`,
      `[${stamp()} INFO]: <Aarav> welcome back`,
      '> save-all'].forEach(add);
  };

  const m_sid = p => p.split('/')[3];
  window.demoApi = async function (path, method, json) {
    await sleep(60);
    const u = new URL(path, 'http://x'), p = u.pathname;
    let m;
    if (p === '/api/status') return status();
    if (p === '/api/system') return { platform: 'win32', ram_total_mb: 16384, cpus: 8, disk_free_gb: 120, git: false, types: TYPES, version: '0.1.0', data_dir: 'C:\\Users\\you\\AppData\\Roaming\\zighost' };
    if (p === '/api/versions') return { versions: ['1.21.4', '1.21.3', '1.21.1', '1.20.6', '1.20.4', '1.19.4', '1.18.2', '1.16.5'] };
    if (p === '/api/windows') { if (method === 'PUT') Object.assign(D.win, json || {}); return { available: true, ...D.win }; }
    if (p === '/api/consent') { if (method === 'PUT') { if (json.accept) Object.assign(D.consent, { accepted: true, heads: !!json.heads, updates: true, stats: true, accepted_at: now() }); else for (const k of ['heads', 'updates', 'stats']) if (k in json) D.consent[k] = !!json[k]; } return { ...D.consent }; }
    if (p === '/api/support/report') return { text: 'Zighost 0.1.0 (preview)\nWindows/OS: Windows-11\nJava: Java 21\n\n--- last log lines ---\n(preview)', can_send: true };
    if (p === '/api/support/send') return { ok: true };
    if (p === '/api/update') return { enabled: D.consent.updates, current: '0.1.0', latest: '0.2.0', available: true, url: 'https://github.com/', file: '', notes: 'Preview notes:\n- Faster start\n- Fixes', error: '', checked_at: now() };
    if (p === '/api/components/prepare') { D.comp.running = true; D.comp.java = { state: 'installing', percent: 10, text: 'Downloading Java 21' }; D.comp.playit = { state: 'missing', percent: 0, text: '' }; D.comp.t = Date.now(); return { ...D.comp }; }
    if (p === '/api/components') {
      if (D.comp.running) { const k = (Date.now() - D.comp.t) / 1000; if (k > 4) { D.comp.running = false; D.comp.java = { state: 'ready', percent: 100, text: '' }; D.comp.playit = { state: 'ready', percent: 100, text: '' }; } else if (k > 2) { D.comp.java = { state: 'ready', percent: 100, text: '' }; D.comp.playit = { state: 'installing', percent: 0, text: '' }; } else D.comp.java.percent = Math.round(k * 45); }
      return { ...D.comp };
    }
    if (p === '/api/open-folder') return { ok: true, path: 'C:\\Users\\you\\AppData\\Roaming\\zighost' };
    if (p === '/api/servers' && method === 'POST') {
      if (!json.eula) err('You need to accept the Minecraft EULA to create a server.');
      if (!json.name.trim()) err('Give the server a name (up to 40 characters).');
      if (D.install.active) err('Another server is still being installed. Wait for it to finish.');
      const id = Math.random().toString(16).slice(2, 10).padEnd(8, '0');
      const meta = { id, name: json.name.trim(), type: json.type, version: json.version, ram_mb: json.ram_mb, port: json.port, motd: json.motd || json.name, jvm_args: json.jvm_args || '', notes: '', installed: false, created: now() };
      D.servers.push(meta);
      D.install = { active: true, step: 'Downloading server', percent: 5, error: '', server_id: id };
      const t = setInterval(() => {
        D.install.percent += 12;
        if (D.install.percent >= 100) { clearInterval(t); meta.installed = true; D.install = { active: false, step: 'Done', percent: 100, error: '', server_id: id }; log(`[panel] ${meta.name} is ready. Press Start server.`); }
      }, 700);
      return { server: meta };
    }
    if ((m = p.match(/^\/api\/servers\/(\w+)$/)) && method === 'PATCH') { Object.assign(D.servers.find(s => s.id === m[1]), json); return { server: D.servers.find(s => s.id === m[1]) }; }
    if ((m = p.match(/^\/api\/servers\/(\w+)\/icon$/)) && method !== 'GET') { const sv = D.servers.find(x => x.id === m[1]); if (sv) sv.icon = method === 'PUT' ? Date.now() : 0; return { icon: sv ? sv.icon : 0 }; }
    if ((m = p.match(/^\/api\/servers\/(\w+)$/)) && method === 'DELETE') { D.servers = D.servers.filter(s => s.id !== m[1]); return { ok: true }; }
    if ((m = p.match(/^\/api\/servers\/(\w+)\/start$/))) { await demoStart(m[1]); return { ok: true }; }
    if (p === '/api/stop') { demoStop(); return { ok: true }; }
    if (p === '/api/restart') { demoStop(); setTimeout(() => demoStart(D.active), 2600); return { ok: true }; }
    if (p === '/api/kill') { D.state = 'offline'; log('[panel] Force closing the server.'); return { ok: true }; }
    if (p === '/api/command') {
      if (!['online', 'starting'].includes(D.state)) err('Start the server first.');
      log('> ' + json.command);
      if (json.command === 'list') log(`[${stamp()} INFO]: There are ${D.players.length} of a max of 20 players online: ${D.players.join(', ')}`);
      return { ok: true };
    }
    if ((m = p.match(/^\/api\/servers\/(\w+)\/properties$/))) {
      if (method === 'PUT') { Object.assign(D.props, json.properties); return { ok: true }; }
      return { properties: { ...D.props }, running: D.state === 'online' };
    }
    if ((m = p.match(/^\/api\/servers\/(\w+)\/backups$/))) {
      if (method === 'POST') { const b = { name: `${new Date().toISOString().slice(0, 10).replace(/-/g, '')}-${Date.now() % 1e6}_manual.zip`, size: 150_000_000, created: now() }; D.backups.unshift(b); return { backup: b }; }
      return { backups: D.backups };
    }
    if ((m = p.match(/^\/api\/servers\/(\w+)\/backups\/([^/]+)\/restore$/))) {
      if (D.state !== 'offline') err('Stop the server before restoring a backup.');
      return { ok: true };
    }
    if ((m = p.match(/^\/api\/servers\/(\w+)\/backups\/([^/]+)$/)) && method === 'DELETE') { D.backups = D.backups.filter(b => b.name !== decodeURIComponent(m[2])); return { ok: true }; }

    if ((m = p.match(/^\/api\/servers\/(\w+)$/)) && method === 'PATCH') { Object.assign(D.servers.find(s => s.id === m[1]), json); return { server: D.servers.find(s => s.id === m[1]) }; }
    if (p.endsWith('/players') && method === 'GET') return { whitelist: D.whitelist.map(name => ({ name, uuid: '' })), ops: D.ops, bans: D.bans, ipbans: D.ipbans, known: D.known, whitelist_on: D.props['white-list'] === 'true', online_mode: true, max_players: 20, online: D.state === 'online' ? D.players : [], running: D.state === 'online' };
    if (p.endsWith('/players/action')) {
      const { action: a, name: n, value: v } = json;
      if (a === 'whitelist_toggle') { D.props['white-list'] = D.props['white-list'] === 'true' ? 'false' : 'true'; return { message: 'Whitelist updated.' }; }
      if (a === 'whitelist_add') { D.whitelist.push(n); return { message: `${n} added to the whitelist.` }; }
      if (a === 'whitelist_remove') { D.whitelist = D.whitelist.filter(x => x !== n); return { message: `${n} removed.` }; }
      if (a === 'op') { D.ops.push({ name: n, level: 4 }); return { message: `${n} is now an operator.` }; }
      if (a === 'deop') { D.ops = D.ops.filter(x => x.name !== n); return { message: `${n} is no longer an operator.` }; }
      if (a === 'ban') { D.bans.push({ name: n, reason: v || '', created: '2026-11-11', source: 'panel' }); return { message: `Banned ${n}.` }; }
      if (a === 'pardon') { D.bans = D.bans.filter(x => x.name !== n); return { message: `Unbanned ${n}.` }; }
      if (a === 'kick') { D.players = D.players.filter(x => x !== n); return { message: `Kicked ${n}.` }; }
      return { message: 'Done.' };
    }
    if (p.endsWith('/schedules')) { if (method === 'PUT') { D.schedules = json.schedules.map((j, i) => ({ ...j, id: j.id || 'j' + Date.now() + i })); } return { schedules: D.schedules }; }
    if (p.endsWith('/worlds/reset')) { if (D.state !== 'offline') err('Stop the server first.'); return { ok: true }; }
    if (p.endsWith('/worlds')) return { worlds: [{ name: 'world', size: 140_000_000, main: true }, { name: 'world_nether', size: 9_000_000 }, { name: 'world_the_end', size: 6_000_000 }], running: D.state === 'online' };
    if (p.endsWith('/plugins/search')) return { hits: ['LuckPerms', 'Vault', 'Dynmap', 'CoreProtect'].map((t, i) => ({ id: 'p' + i, slug: t.toLowerCase(), title: t, description: 'A popular plugin for your server.', icon: '', downloads: 1_000_000 - i * 150_000, author: 'author' + i })), total: 4, offset: 0 };
    if (p.endsWith('/plugins/toggle')) { const x = D.plugins.find(q => q.file === json.file); if (x) x.enabled = json.enabled; return { ok: true }; }
    if (p.endsWith('/plugins/remove')) { D.plugins = D.plugins.filter(q => q.file !== json.file); return { ok: true }; }
    if (p.endsWith('/plugins/install')) { D.plugins.push({ file: json.project_id + '.jar', enabled: true, size: 800_000, title: json.project_id, version: '1.0', description: '' }); return { file: json.project_id + '.jar', version: '1.0', requires: [] }; }
    if (p.endsWith('/plugins')) { const t = D.servers.find(s => s.id === m_sid(p)).type; return ['vanilla'].includes(t) ? { supported: false, kind: '', folder: '', items: [], type: t } : { supported: true, kind: t === 'fabric' ? 'mod' : 'plugin', folder: t === 'fabric' ? 'mods' : 'plugins', items: D.plugins, type: t, version: '1.21.4' }; }
    if (p.endsWith('/files/upload') || p.endsWith('/files/rename') || p.endsWith('/files/delete') || p.endsWith('/files/mkdir')) return { ok: true };
    if (p.endsWith('/files')) { const path = u.searchParams.get('path') || ''; const list = D.files[path] || []; return { path, entries: list.map(([name, dir, size = 0]) => ({ name, dir: !!dir, size, modified: now() - 3600, editable: !dir && !/\.jar/.test(name) })), truncated: false }; }
    if (p.endsWith('/file')) { const path = u.searchParams.get('path') || json?.path; if (method === 'PUT') { D.text[path] = json.content; return { ok: true }; } const c = D.text[path] ?? ''; return { path, content: c, size: c.length }; }
    if (p === '/api/network/test') return json.target === 'public' && !D.playit.address ? err('There is no public address yet.') : D.state !== 'online' ? err('The server did not answer. Is it running?') : { ok: true, latency_ms: json.target === 'public' ? 64 : 3, version: 'Paper 1.21.4', players_online: D.players.length, players_max: 20, motd: D.props.motd };
    if (p === '/api/network/diagnostics') return { text: 'Zighost 0.1.0 playit report (demo)' };
    if (p === '/api/network/unlink') return D.playit;
    if (p === '/api/notify/test') { if (!D.settings.discord_webhook_set) err('Save a Discord link first.'); return { ok: true }; }
    if (p === '/api/settings' && method === 'PUT') {
      const { playit_secret, clear_playit_secret, discord_webhook, clear_discord_webhook, ...rest } = json;
      if (discord_webhook) D.settings.discord_webhook_set = true;
      if (clear_discord_webhook) D.settings.discord_webhook_set = false;
      if (rest.playit_mode) D.playit.mode = rest.playit_mode;
      Object.assign(D.settings, rest);
      if (playit_secret) D.settings.playit_secret_set = true;
      if (clear_playit_secret) D.settings.playit_secret_set = false;
      return { ...D.settings };
    }
    if (p === '/api/network/start') { D.playit.state = 'online'; return { ...D.playit }; }
    if (p === '/api/network/stop') { D.playit.state = 'stopped'; D.playit.detected_address = ''; D.playit.address = D.settings.playit_address; return { ...D.playit }; }
    if (p === '/api/network/address') {
      D.settings.playit_address = json.address; D.playit.manual = !!json.address;
      D.playit.address = json.address || D.playit.detected_address; return { ...D.playit };
    }

    const E = D.extra;
    if ((m = p.match(/^\/api\/servers\/(\w+)\/players$/))) return { whitelist: E.whitelist, ops: E.ops, bans: E.bans, ipbans: E.ipbans, known: E.known, whitelist_on: E.wl_on, online_mode: true, max_players: +D.props['max-players'] || 20, online: D.state === 'online' ? D.players : [], running: D.state === 'online' };
    if ((m = p.match(/^\/api\/servers\/(\w+)\/players\/action$/))) {
      const { action, name } = json;
      if (action === 'whitelist_toggle') { E.wl_on = !E.wl_on; return { message: E.wl_on ? 'Whitelist is on.' : 'Whitelist is off.' }; }
      if (action === 'whitelist_add') E.whitelist.push({ name, uuid: name });
      if (action === 'whitelist_remove') E.whitelist = E.whitelist.filter(x => x.name !== name);
      if (action === 'op') E.ops.push({ name, level: 4 });
      if (action === 'deop') E.ops = E.ops.filter(x => x.name !== name);
      if (action === 'ban') { E.bans.push({ name, reason: json.value || '', created: '2026-11-11', source: 'Panel' }); D.players = D.players.filter(x => x !== name); }
      if (action === 'pardon') E.bans = E.bans.filter(x => x.name !== name);
      if (action === 'kick') D.players = D.players.filter(x => x !== name);
      return { message: `Done: ${action} ${name || ''}`.trim() + '.' };
    }
    if ((m = p.match(/^\/api\/servers\/(\w+)\/schedules$/))) {
      if (method === 'PUT') { E.schedules = json.schedules.map((j, i) => ({ ...j, id: j.id || 'j' + Date.now() + i })); }
      return { schedules: E.schedules };
    }
    if ((m = p.match(/^\/api\/servers\/(\w+)\/plugins\/search$/))) return { total: 2, offset: 0, hits: [
      { id: 'p1', slug: 'worldedit', title: 'WorldEdit', description: 'In-game map editor.', icon: '', downloads: 9_000_000, author: 'EngineHub' },
      { id: 'p2', slug: 'chunky', title: 'Chunky', description: 'Pre-generate chunks fast.', icon: '', downloads: 3_200_000, author: 'pop4959' }] };
    if (p.endsWith('/plugins/install')) { E.plugins.push({ file: 'New.jar', enabled: true, size: 900_000, title: 'New plugin', version: '1.0', description: '' }); return { file: 'New.jar', version: '1.0', requires: [] }; }
    if (p.endsWith('/plugins/toggle')) { const x = E.plugins.find(q => q.file === json.file); if (x) x.enabled = json.enabled; return { ok: true }; }
    if (p.endsWith('/plugins/remove')) { E.plugins = E.plugins.filter(q => q.file !== json.file); return { ok: true }; }
    if ((m = p.match(/^\/api\/servers\/(\w+)\/plugins$/))) { const s = D.servers.find(x => x.id === m[1]); const sup = s && s.type !== 'vanilla'; return { supported: sup, kind: s && s.type === 'fabric' ? 'mod' : 'plugin', folder: 'plugins', items: sup ? E.plugins : [], type: s ? s.type : 'paper', version: s ? s.version : '' }; }
    if ((m = p.match(/^\/api\/servers\/(\w+)\/worlds$/))) return { worlds: [{ name: 'world', size: 120_000_000, main: true }, { name: 'world_nether', size: 18_000_000, main: false }, { name: 'world_the_end', size: 6_000_000, main: false }], running: D.state === 'online' };
    if (p.endsWith('/worlds/reset')) { if (D.state !== 'offline') err('Stop the server first.'); return { ok: true }; }
    if (p.endsWith('/files') ) return { path: u.searchParams.get('path') || '', entries: E.files[u.searchParams.get('path') || ''] || [], truncated: false };
    if (p.endsWith('/file') && method === 'GET') return { path: u.searchParams.get('path'), content: '# demo file\nmotd=Welcome\n', size: 24 };
    if (/\/(file|files\/(rename|delete|mkdir|upload))$/.test(p)) return { ok: true };
    if (p === '/api/network/test') return { ok: true, latency_ms: 38, version: 'Paper 1.21.4', players_online: D.players.length, players_max: 20, motd: 'Welcome to Friends SMP' };
    if (p === '/api/notify/test') { if (!D.settings.discord_webhook_set) err('Save a webhook link first.'); return { ok: true }; }
    err('Not available in preview mode.');
  };
})();
