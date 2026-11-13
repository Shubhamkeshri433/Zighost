'use strict';
/* Server icons.
   - `Icons`: an original set of pixel blocks and items made for this project (drawn by code, nothing copied from the game),
     rendered on a 16x16 grid and exported as the 64x64 PNG Minecraft wants (server-icon.png).
   - `IconPicker.open()`: choose an item or block, or upload a picture and crop it. Resolves to
     null (cancelled), { remove: true }, or { blob } (a 64x64 PNG). */

const Icons = (() => {
  const G = 16;
  const hex = c => [1, 3, 5].map(i => parseInt(c.slice(i, i + 2), 16));
  const css = ([r, g, b]) => '#' + [r, g, b].map(v => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, '0')).join('');
  const shade = (c, f) => css(hex(c).map(v => v * f));
  const rng = seed => { let a = 0; for (const ch of seed) a = (a * 31 + ch.charCodeAt(0)) >>> 0; return () => { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; };

  /* ----- blocks: an isometric cube with a small texture on each face ----- */
  const noise = (cols, r) => cols[Math.floor(r() * cols.length)];
  const BLOCKS = {
    grass: { label: 'Grass', top: (x, y, r) => noise(['#5fae3c', '#58a336', '#69b845', '#4f9830'], r), side: (x, y, r) => y < 7 ? noise(['#5fae3c', '#58a336', '#4f9830'], r) : noise(['#8a5a34', '#7d522f', '#946239'], r) },
    dirt: { label: 'Dirt', top: (x, y, r) => noise(['#8a5a34', '#7d522f', '#946239', '#6f4a2b'], r) },
    stone: { label: 'Stone', top: (x, y, r) => noise(['#8d9096', '#80838a', '#999ca2', '#767980'], r) },
    sand: { label: 'Sand', top: (x, y, r) => noise(['#e3d49a', '#dccb8a', '#ebdda8'], r) },
    planks: { label: 'Planks', top: (x, y, r) => (y % 4 === 3 ? '#8a6234' : noise(['#b98a4e', '#c1925a', '#b3834a'], r)) },
    log: { label: 'Log', top: (x, y, r) => { const d = Math.max(Math.abs(x - 7.5), Math.abs(y - 6)); return Math.floor(d / 1.6) % 2 ? '#b98a4e' : '#9c7040'; }, side: (x, y, r) => (x % 3 === 0 ? '#4e3a22' : noise(['#6a4e2e', '#5f4527', '#725430'], r)) },
    brick: { label: 'Brick', top: (x, y, r) => { const row = Math.floor(y / 4), off = row % 2 ? 4 : 0; return y % 4 === 3 || (x + off) % 8 === 0 ? '#c9c2b8' : noise(['#a8472f', '#9c3f29', '#b34e35'], r); } },
    gold: { label: 'Gold', top: (x, y, r) => ((x + y) % 5 === 0 ? '#fff0a0' : noise(['#f5c71a', '#f0bd10', '#fad02e'], r)) },
    ore: { label: 'Gem ore', top: (x, y, r) => (((x >> 1) * 7 + (y >> 1) * 13) % 11 === 0 ? '#5ff0ff' : noise(['#8d9096', '#80838a', '#999ca2'], r)) },
    lava: { label: 'Lava', top: (x, y, r) => noise(['#ff7a1a', '#ff9a2e', '#e8501a', '#ffc247'], r) },
    water: { label: 'Water', top: (x, y, r) => noise(['#2f6fd0', '#3a7ee0', '#2a63bd', '#5aa0f0'], r) },
    ice: { label: 'Ice', top: (x, y, r) => noise(['#a9d8f5', '#bfe6ff', '#94c9ea', '#e2f4ff'], r) },
    obsidian: { label: 'Obsidian', top: (x, y, r) => (r() < .08 ? '#6b4aa8' : noise(['#1c1430', '#241a3c', '#170f28'], r)) },
    leaves: { label: 'Leaves', top: (x, y, r) => (r() < .15 ? '#1f5a22' : noise(['#3fa34d', '#369644', '#4cb15a'], r)) },
    snow: { label: 'Snow', top: (x, y, r) => noise(['#f4f8fb', '#e6eef4', '#ffffff'], r), side: (x, y, r) => y < 6 ? noise(['#f4f8fb', '#e6eef4', '#ffffff'], r) : noise(['#8a5a34', '#7d522f', '#946239'], r) },
  };
  const FACE_SHADE = { 1: 1, 2: .78, 3: .6 };
  function faceAt(x, y) {
    const px = x + .5, py = y + .5;
    if (Math.abs(px - 8) / 8 + Math.abs(py - 4) / 4 <= 1) return 1;
    if (px < 8 && py >= 4 + px / 2 && py <= 12 + px / 2) return 2;
    if (px >= 8 && py >= 4 + (16 - px) / 2 && py <= 12 + (16 - px) / 2) return 3;
    return 0;
  }
  function cube(id) {
    const spec = BLOCKS[id], r = rng(id), faces = [], out = new Array(G * G).fill(null);
    for (let y = 0; y < G; y++) for (let x = 0; x < G; x++) faces[y * G + x] = faceAt(x, y);
    for (let y = 0; y < G; y++) for (let x = 0; x < G; x++) {
      const f = faces[y * G + x];
      if (!f) continue;
      const edge = [[1, 0], [-1, 0], [0, 1], [0, -1]].some(([dx, dy]) => !(faces[(y + dy) * G + x + dx] && x + dx >= 0 && x + dx < G && y + dy >= 0 && y + dy < G));
      const fn = f === 1 ? spec.top : (spec.side || spec.top);
      let c = fn(f === 1 ? x : x % 8, f === 1 ? y : y - 4 - (f === 2 ? x : 15 - x) / 2 | 0, r);
      c = shade(c, FACE_SHADE[f] * (edge ? .72 : 1));
      out[y * G + x] = c;
    }
    return out;
  }

  /* ----- items: 12x12 sprites placed in the middle of the 16x16 grid ----- */
  const mirror = rows => rows.map(r => r + [...r].reverse().join(''));
  const SPRITES = {
    heart: { label: 'Heart', pal: { r: '#e5383b', d: '#9d1c20', w: '#ff9aa2' }, rows: mirror(['......', '.rrr..', 'rrwrr.', 'rrwrrr', 'rrrrrr', 'rrrrrr', 'drrrrr', '.drrrr', '..drrr', '...drr', '....dr', '.....d']) },
    star: { label: 'Star', pal: { y: '#ffd23f' }, rows: mirror(['.....y', '.....y', '....yy', 'yyyyyy', '.yyyyy', '..yyyy', '...yyy', '...yyy', '..yyy.', '..yy..', '.yy...', '.y....']) },
    gem: { label: 'Gem', pal: { c: '#7ff5ff', b: '#34c3d9', d: '#1b8aa3' }, rows: mirror(['......', '..cccc', '.cccbb', 'cccbbb', 'bbbbbb', 'bbbbbb', '.dbbbb', '..dbbb', '...dbb', '....db', '.....d', '......']) },
    crown: { label: 'Crown', pal: { y: '#ffd23f', d: '#b8860b', r: '#d62828' }, rows: mirror(['......', 'y....y', 'y...yy', 'yy.yyy', 'yyyyyy', 'yyyyyy', 'yyryyy', 'yyyyyy', 'dddddd', 'dddddd', '......', '......']) },
    shield: { label: 'Shield', pal: { s: '#c0c7d1', r: '#c8302f', w: '#ffffff' }, rows: mirror(['......', 'ssssss', 'srrrrr', 'srrrrw', 'srrrrw', 'srrrrr', 'srrrrr', '.srrrr', '..srrr', '...srr', '....ss', '......']) },
    potion: { label: 'Potion', pal: { k: '#8a5a34', g: '#d9f1ff', p: '#9b4dff' }, rows: mirror(['....kk', '....gg', '....gg', '...ggg', '..gggg', '.ggppp', 'ggpppp', 'ggpppp', 'ggpppp', 'ggpppp', '.ggggg', '......']) },
    flame: { label: 'Flame', pal: { o: '#ff7a1a', y: '#ffd23f', r: '#e03c1f' }, rows: mirror(['.....o', '.....o', '....oo', '...ooo', '..oooy', '.ooooy', '.oooyy', 'oooyyy', 'oooyyy', 'roooyy', '.rrooo', '..rrrr']) },
    drop: { label: 'Drop', pal: { b: '#3da5f5', w: '#bfe6ff', d: '#1f6fc4' }, rows: mirror(['.....b', '.....b', '....bb', '....bb', '...bbb', '..bbbb', '.bwbbb', '.bwbbb', 'bbbbbb', 'bbbbbb', '.bbbbd', '..dddd']) },
    apple: { label: 'Apple', pal: { r: '#d62828', w: '#ff8a8a', k: '#6b4423', d: '#9d1c20' }, rows: mirror(['.....k', '..rr.k', '.rrrrr', 'rrwrrr', 'rrwrrr', 'rrrrrr', 'rrrrrr', 'rrrrrr', '.rrrrr', '.drrrr', '..rrrr', '......']) },
    tree: { label: 'Pine', pal: { g: '#3fa34d', k: '#6b4423' }, rows: mirror(['.....g', '....gg', '....gg', '...ggg', '..gggg', '...ggg', '..gggg', '.ggggg', 'gggggg', '.....k', '.....k', '.....k']) },
    bolt: { label: 'Bolt', pal: { y: '#ffd23f' }, rows: ['.....yyyyy..', '....yyyyy...', '...yyyyy....', '..yyyyyyyy..', '.yyyyyyyy...', '.....yyy....', '....yyy.....', '...yyy......', '...yy.......', '..y.........', '............', '............'] },
  };
  /* sword and pickaxe are drawn with a few lines, which is easier to get right than a grid of letters */
  const DRAWN = {
    sword: { label: 'Sword', draw(p) {
      for (let t = 0; t <= 5; t++) { p(10 - t, 1 + t, '#f2f6fa'); p(11 - t, 1 + t, '#aab4c0'); }
      p(11, 0, '#f2f6fa'); p(12, 0, '#aab4c0');
      for (let t = 0; t <= 4; t++) p(3 + t, 5 + t, '#d9a520');
      for (let t = 0; t <= 2; t++) p(4 - t, 8 + t, '#7a4e26');
      p(1, 11, '#d9a520');
    } },
    pickaxe: { label: 'Pickaxe', draw(p) {
      for (let t = 0; t <= 7; t++) p(2 + t, 11 - t, '#7a4e26');
      for (let t = 0; t <= 6; t++) { p(4 + t, 1 + t, '#c4ccd6'); p(5 + t, 1 + t, '#8d97a3'); }
      p(3, 2, '#c4ccd6'); p(4, 2, '#8d97a3'); p(11, 8, '#8d97a3'); p(12, 8, '#8d97a3');
    } },
  };

  function spritePixels(id) {
    const out = new Array(G * G).fill(null), put = (x, y, c) => { if (x >= 0 && x < G && y >= 0 && y < G) out[y * G + x] = c; };
    if (SPRITES[id]) SPRITES[id].rows.forEach((row, y) => [...row].forEach((ch, x) => { if (ch !== '.') put(x + 2, y + 2, SPRITES[id].pal[ch]); }));
    else DRAWN[id].draw((x, y, c) => put(x + 2, y + 2, c));
    return out;
  }

  const LIST = [
    ...Object.keys(BLOCKS).map(id => ({ id, label: BLOCKS[id].label, group: 'Blocks' })),
    ...[...Object.keys(SPRITES), ...Object.keys(DRAWN)].map(id => ({ id, label: (SPRITES[id] || DRAWN[id]).label, group: 'Items' })),
  ];
  const BGS = [
    { id: 'night', label: 'Night', c: '#1f2433' }, { id: 'sky', label: 'Sky', c: '#6aa7e8' }, { id: 'meadow', label: 'Meadow', c: '#4f9a3c' },
    { id: 'desert', label: 'Desert', c: '#d9b86a' }, { id: 'ember', label: 'Ember', c: '#b8442b' }, { id: 'amethyst', label: 'Amethyst', c: '#6a4aa8' },
    { id: 'slate', label: 'Slate', c: '#6b717c' }, { id: 'none', label: 'Clear', c: null },
  ];

  const cache = new Map();
  function pixels(id) {
    if (!cache.has(id)) cache.set(id, BLOCKS[id] ? cube(id) : spritePixels(id));
    return cache.get(id);
  }
  /* draw item `id` on `canvas` (16 grid squares of `scale` pixels) over background `bg` (a colour, or null for clear) */
  function draw(canvas, id, bg, scale = 4) {
    canvas.width = canvas.height = G * scale;
    const c = canvas.getContext('2d');
    c.imageSmoothingEnabled = false;
    c.clearRect(0, 0, canvas.width, canvas.height);
    if (bg) { c.fillStyle = bg; c.fillRect(0, 0, canvas.width, canvas.height); }
    pixels(id).forEach((col, i) => { if (col) { c.fillStyle = col; c.fillRect((i % G) * scale, Math.floor(i / G) * scale, scale, scale); } });
  }
  const toBlob = canvas => new Promise((res, rej) => canvas.toBlob(b => (b ? res(b) : rej(new Error('Could not make the picture.'))), 'image/png'));
  async function png64(id, bg) { const cv = document.createElement('canvas'); draw(cv, id, bg, 4); return toBlob(cv); }
  return { LIST, BGS, draw, png64, toBlob, G };
})();

/* ---------------------------------------------------------------------------------------------------------------- */

const IconPicker = {
  open({ hasIcon = false, name = 'My server', motd = '' } = {}) {
    return new Promise(resolve => {
      const st = { tab: 'items', id: 'grass', bg: Icons.BGS[0].c, img: null, scale: 1, min: 1, ox: 0, oy: 0, pixel: 0, drag: null };
      const STAGE = 256;
      const prev64 = h('canvas', { class: 'ip-prev64', width: 64, height: 64 }), prev32 = h('canvas', { class: 'ip-prev32', width: 32, height: 32 });
      const out = h('canvas', { width: 64, height: 64, hidden: true });
      const status = h('p', { class: 'hint', style: 'min-height:20px' });

      /* the 64x64 result for the current choice */
      function render64() {
        const c = out.getContext('2d');
        c.clearRect(0, 0, 64, 64);
        if (st.tab === 'items') { Icons.draw(out, st.id, st.bg, 4); return out; }
        out.width = out.height = 64;
        if (!st.img) return null;
        const px = [64, 32, 16][st.pixel], small = document.createElement('canvas');
        small.width = small.height = px;
        const sc = small.getContext('2d');
        if (st.bg) { sc.fillStyle = st.bg; sc.fillRect(0, 0, px, px); }
        sc.imageSmoothingQuality = 'high';
        const k = px / STAGE;
        sc.drawImage(st.img, st.ox * k, st.oy * k, st.img.width * st.scale * k, st.img.height * st.scale * k);
        const oc = out.getContext('2d');
        oc.imageSmoothingEnabled = px === 64;
        oc.drawImage(small, 0, 0, 64, 64);
        return out;
      }
      function paintPreview() {
        const src = render64();
        for (const cv of [prev64, prev32]) { const c = cv.getContext('2d'); c.imageSmoothingEnabled = false; c.clearRect(0, 0, cv.width, cv.height); if (src) c.drawImage(src, 0, 0, cv.width, cv.height); }
        okBtn.disabled = !src;
        if (st.tab === 'upload') drawStage();
      }

      /* ---- items tab ---- */
      const grid = h('div', { class: 'ip-grid', role: 'listbox', 'aria-label': 'Items and blocks' });
      const tiles = Icons.LIST.map(it => {
        const cv = h('canvas', {}); Icons.draw(cv, it.id, null, 3);
        const b = h('button', { type: 'button', class: 'ip-tile', role: 'option', title: it.label, 'aria-label': it.label, onclick: () => { st.id = it.id; sync(); } }, cv);
        b.dataset.id = it.id; return b;
      });
      grid.append(...tiles);
      const swatches = h('div', { class: 'ip-swatches', role: 'radiogroup', 'aria-label': 'Background' }, Icons.BGS.map(b => {
        const s = h('button', { type: 'button', class: 'ip-sw' + (b.c ? '' : ' clear'), role: 'radio', title: b.label, 'aria-label': b.label, style: b.c ? 'background:' + b.c : '', onclick: () => { st.bg = b.c; sync(); } });
        s.dataset.c = b.c || ''; return s;
      }));
      const itemsPane = h('div', {}, grid, h('p', { class: 'hint', style: 'margin:14px 0 6px', text: 'Background' }), swatches);

      /* ---- upload tab ---- */
      const stage = h('canvas', { class: 'ip-stage', width: STAGE, height: STAGE, tabindex: 0, 'aria-label': 'Crop area. Drag to move the picture, arrow keys also work.' });
      const zoom = h('input', { type: 'range', min: 100, max: 400, value: 100, 'aria-label': 'Zoom', disabled: true, oninput: e => setScale(st.min * (+e.target.value / 100)) });
      const file = h('input', { type: 'file', accept: 'image/png,image/jpeg,image/webp,image/gif', hidden: true, onchange: e => load(e.target.files[0]) });
      const pixelSel = h('select', { 'aria-label': 'Style', onchange: e => { st.pixel = +e.target.value; paintPreview(); } },
        [['Smooth', 0], ['Blocky (32 px)', 1], ['Chunky (16 px)', 2]].map(([t, v]) => h('option', { value: v, text: t })));
      const drop = h('div', { class: 'ip-drop' }, h('p', { text: 'Drop a picture here' }), h('button', { class: 'btn', type: 'button', onclick: () => file.click() }, ico('upload'), 'Choose a picture'),
        h('p', { class: 'hint', text: 'PNG, JPG, WEBP or GIF. You can move and zoom it next.' }));
      const cropBox = h('div', { class: 'ip-crop', hidden: true }, stage,
        h('div', { class: 'ip-crop-tools' }, h('label', { class: 'hint', text: 'Zoom' }), zoom, h('label', { class: 'hint', text: 'Style' }), pixelSel,
          h('button', { class: 'btn small', type: 'button', onclick: () => file.click() }, 'Other picture')));
      const uploadPane = h('div', { class: 'ip-upload' }, drop, cropBox, file);
      for (const t of ['dragover', 'dragenter']) uploadPane.addEventListener(t, e => { e.preventDefault(); uploadPane.classList.add('over'); });
      for (const t of ['dragleave', 'drop']) uploadPane.addEventListener(t, e => { e.preventDefault(); uploadPane.classList.remove('over'); });
      uploadPane.addEventListener('drop', e => load(e.dataTransfer.files[0]));

      function load(f) {
        if (!f) return;
        if (!f.type.startsWith('image/')) { status.textContent = 'That file is not a picture.'; return; }
        if (f.size > 12 * 1024 * 1024) { status.textContent = 'That picture is larger than 12 MB. Choose a smaller one.'; return; }
        const url = URL.createObjectURL(f), img = new Image();
        img.onload = () => {
          URL.revokeObjectURL(url);
          st.img = img; st.min = Math.max(STAGE / img.width, STAGE / img.height); st.scale = st.min;
          st.ox = (STAGE - img.width * st.scale) / 2; st.oy = (STAGE - img.height * st.scale) / 2;
          zoom.disabled = false; zoom.value = 100; drop.hidden = true; cropBox.hidden = false; status.textContent = '';
          paintPreview();
        };
        img.onerror = () => { URL.revokeObjectURL(url); status.textContent = 'That picture could not be opened.'; };
        img.src = url;
      }
      const clamp = () => { const w = st.img.width * st.scale, hh = st.img.height * st.scale; st.ox = Math.min(0, Math.max(STAGE - w, st.ox)); st.oy = Math.min(0, Math.max(STAGE - hh, st.oy)); };
      function setScale(s) {
        const cx = (STAGE / 2 - st.ox) / st.scale, cy = (STAGE / 2 - st.oy) / st.scale;
        st.scale = s; st.ox = STAGE / 2 - cx * s; st.oy = STAGE / 2 - cy * s; clamp(); paintPreview();
      }
      function drawStage() {
        const c = stage.getContext('2d');
        c.clearRect(0, 0, STAGE, STAGE);
        c.fillStyle = '#2a2f3a'; c.fillRect(0, 0, STAGE, STAGE);
        if (st.img) c.drawImage(st.img, st.ox, st.oy, st.img.width * st.scale, st.img.height * st.scale);
        c.strokeStyle = 'rgba(255,255,255,.25)'; c.lineWidth = 1;
        for (const k of [1, 2]) { c.beginPath(); c.moveTo(STAGE * k / 3, 0); c.lineTo(STAGE * k / 3, STAGE); c.moveTo(0, STAGE * k / 3); c.lineTo(STAGE, STAGE * k / 3); c.stroke(); }
      }
      stage.addEventListener('pointerdown', e => { if (!st.img) return; stage.setPointerCapture(e.pointerId); st.drag = { x: e.clientX, y: e.clientY, ox: st.ox, oy: st.oy }; });
      stage.addEventListener('pointermove', e => { if (!st.drag) return; st.ox = st.drag.ox + e.clientX - st.drag.x; st.oy = st.drag.oy + e.clientY - st.drag.y; clamp(); paintPreview(); });
      stage.addEventListener('pointerup', () => { st.drag = null; });
      stage.addEventListener('keydown', e => {
        const d = { ArrowLeft: [-8, 0], ArrowRight: [8, 0], ArrowUp: [0, -8], ArrowDown: [0, 8] }[e.key];
        if (!d || !st.img) return; e.preventDefault(); st.ox += d[0]; st.oy += d[1]; clamp(); paintPreview();
      });
      stage.addEventListener('wheel', e => { if (!st.img) return; e.preventDefault(); const v = Math.max(100, Math.min(400, +zoom.value - Math.sign(e.deltaY) * 10)); zoom.value = v; setScale(st.min * v / 100); }, { passive: false });

      /* ---- frame ---- */
      const tabBar = tabs([['items', 'Items and blocks'], ['upload', 'Your picture']], st.tab, id => { st.tab = id; sync(); });
      const pane = h('div');
      const mock = h('div', { class: 'ip-mock' }, h('span', { class: 'ip-mock-icon' }, prev32),
        h('div', { class: 'min0' }, h('div', { class: 'ip-mock-name', text: name }), h('div', { class: 'ip-mock-motd', text: motd || 'A Minecraft Server' })));
      const okBtn = h('button', { class: 'btn primary', type: 'button', disabled: true, onclick: async () => {
        const src = render64(); if (!src) return;
        try { dlg.close({ blob: await Icons.toBlob(src) }); } catch (e) { status.textContent = e.message; }
      } }, 'Use this icon');
      const removeBtn = hasIcon ? h('button', { class: 'btn ghost-danger', type: 'button', onclick: () => dlg.close({ remove: true }) }, ico('trash'), 'Remove icon') : null;
      const body = h('div', { class: 'modal-body ip-body' },
        h('div', { class: 'ip-left' }, prev64, mock, h('p', { class: 'hint', text: 'Minecraft shows this next to your server in the Multiplayer list. It is saved as a 64 by 64 picture.' })),
        h('div', { class: 'ip-right' }, tabBar, pane));
      const box = h('div', { class: 'ip' }, h('div', { class: 'modal-head' }, h('h2', { text: 'Server icon' })), body,
        h('div', { class: 'modal-foot' }, removeBtn, h('span', { class: 'grow' }), status, h('button', { class: 'btn', type: 'button', onclick: () => dlg.close(null) }, 'Cancel'), okBtn));
      const dlg = Modal.open(box, { label: 'Server icon', onClose: r => resolve(r || null) });
      function sync() {
        pane.replaceChildren(st.tab === 'items' ? itemsPane : uploadPane);
        tabBar.querySelectorAll('button').forEach((b, i) => b.setAttribute('aria-selected', String((i === 0) === (st.tab === 'items'))));
        tiles.forEach(t => t.setAttribute('aria-selected', String(t.dataset.id === st.id)));
        swatches.querySelectorAll('.ip-sw').forEach(s => s.setAttribute('aria-checked', String((s.dataset.c || null) === (st.bg || null) || (!s.dataset.c && !st.bg))));
        status.textContent = '';
        paintPreview();
      }
      sync();
    });
  },
};
