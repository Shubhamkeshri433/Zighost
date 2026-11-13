'use strict';
/* One settings form used by the Create-server wizard and the Settings page.
   Shows every known server.properties setting in groups, with search, advanced toggle, reset-to-default and presets. */
const PropForm = (() => {
  const MC_KEYS = new Set(['motd']);   // stored with § for the section sign, shown with the real sign
  const dec = (k, v) => MC_KEYS.has(k) ? String(v).replace(/\\u00[aA]7/g, '§') : String(v);
  const enc = (k, v) => MC_KEYS.has(k) ? String(v).replace(/§/g, '\\u00A7') : String(v);

  function build({ values = {}, wizard = false, hide = [], onChange = () => {} }) {
    const root = h('div', { class: 'pf' });
    const rows = [];                    // {f, el, input, get, set, def, orig, adv}
    const known = new Set();
    let showAdv = false, query = '';

    function makeRow(f, other) {
      known.add(f.k);
      const id = 'pf-' + f.k.replace(/\W/g, '_');
      const def = dec(f.k, f.def ?? '');
      const val = dec(f.k, values[f.k] !== undefined ? values[f.k] : (f.def ?? ''));
      let input, control, get, set;
      if (f.type === 'bool') {
        input = h('input', { type: 'checkbox', id }); input.checked = val === 'true';
        get = () => input.checked ? 'true' : 'false'; set = v => { input.checked = v === 'true'; };
        control = h('label', { class: 'switch' }, input, h('i'));
      } else if (f.type === 'select') {
        input = h('select', { id }, f.opts.map(o => h('option', { value: o, text: o.replace('minecraft:', '').replace(/_/g, ' ') })));
        if (val && !f.opts.includes(val)) input.append(h('option', { value: val, text: val }));
        input.value = val || f.opts[0];
        get = () => input.value; set = v => { input.value = v; }; control = input;
      } else {
        input = h('input', { id, type: f.type === 'number' ? 'number' : f.type === 'password' ? 'password' : 'text', min: f.min, max: f.max, value: val, autocomplete: 'off' });
        get = () => input.value; set = v => { input.value = v; }; control = input;
      }
      const reset = other ? null : h('button', { type: 'button', class: 'btn ghost small pf-reset', title: 'Back to the default', 'aria-label': 'Reset ' + f.label, onclick: () => { set(def); update(); } }, ico('refresh'));
      const left = h('div', { class: 'pf-l' }, h('label', { for: id, text: f.label }), f.hint ? h('p', { class: 'hint', text: f.hint }) : null);
      const el = h('div', { class: 'pf-row', 'data-search': `${f.label} ${f.k} ${f.hint || ''}`.toLowerCase() }, left, h('div', { class: 'pf-r' }, control, reset));
      const row = { f, el, input, get, set, def, orig: val, adv: !!f.adv, other };
      function update() {
        const v = get();
        el.classList.toggle('is-changed', v !== row.orig);
        el.classList.toggle('not-default', !other && v !== def);
        onChange();
      }
      input.addEventListener('input', update); input.addEventListener('change', update);
      el.classList.toggle('not-default', !other && val !== def);
      rows.push(row);
      return row;
    }

    const groupEls = [];
    hide.forEach(k => known.add(k));     // edited somewhere else on the page, so also not listed under "Other"
    for (const g of MCP_SCHEMA.groups) {
      const fields = g.fields.filter(f => !(wizard && f.noWizard) && !hide.includes(f.k));
      if (!fields.length) continue;
      const body = h('div', { class: 'pf-rows' }, fields.map(f => makeRow(f, false).el));
      const el = h('section', { class: 'card pf-group', style: 'padding:0' }, h('header', {}, h('h2', { text: g.title }), h('p', { class: 'hint', text: g.desc })), body);
      groupEls.push(el); root.append(el);
    }
    function applyVisibility() {
      const q = query.trim().toLowerCase();
      for (const r of rows) r.el.hidden = q ? !r.el.dataset.search.includes(q) : (r.adv && !showAdv);
      groupEls.forEach(g => { g.hidden = !$$('.pf-row', g).some(x => !x.hidden); });
    }
    applyVisibility();

    return {
      el: root,
      get: () => Object.fromEntries(rows.map(r => [r.f.k, enc(r.f.k, r.get())])),
      changed: () => Object.fromEntries(rows.filter(r => r.get() !== r.orig).map(r => [r.f.k, enc(r.f.k, r.get())])),
      nonDefault: () => Object.fromEntries(rows.filter(r => !r.other && r.get() !== r.def).map(r => [r.f.k, enc(r.f.k, r.get())])),
      hasChanges: () => rows.some(r => r.get() !== r.orig),
      set(patch) {
        for (const r of rows) if (r.f.k in patch) { r.set(dec(r.f.k, patch[r.f.k])); r.input.dispatchEvent(new Event('change')); }
      },
      markSaved() { rows.forEach(r => { r.orig = r.get(); r.el.classList.remove('is-changed'); }); onChange(); },
      discard() { rows.forEach(r => { r.set(r.orig); r.el.classList.remove('is-changed'); r.el.classList.toggle('not-default', !r.other && r.get() !== r.def); }); onChange(); },
      setAdvanced(b) { showAdv = b; applyVisibility(); },
      filter(q) { query = q; applyVisibility(); },
    };
  }

  /* toolbar shared by both users: search, advanced toggle, presets */
  function toolbar(form, { presets = true } = {}) {
    const search = h('input', { type: 'search', placeholder: 'Search settings', 'aria-label': 'Search settings', oninput: e => form.filter(e.target.value) });
    const sel = h('select', { 'aria-label': 'Apply a preset', onchange: e => {
      const p = MCP_SCHEMA.presets.find(x => x.id === e.target.value);
      if (p) { form.set(p.set); toast(`Preset applied: ${p.title}. Nothing is saved until you press the button.`); }
      e.target.value = '';
    } }, h('option', { value: '', text: 'Apply a preset...' }), MCP_SCHEMA.presets.map(p => h('option', { value: p.id, text: `${p.title} (${p.note})` })));
    return h('div', { class: 'tools' }, h('div', { style: 'flex:1;min-width:180px;max-width:280px' }, search),
      presets ? sel : null);
  }

  return { build, toolbar };
})();
