'use strict';
/* Privacy and support: the first-run screen (policy, consent, get-ready downloads), the Support dialog,
   and the Privacy card used in Panel settings. */

const Privacy = {
  state: null,

  async load() { this.state = await api('/api/consent'); return this.state; },

  /* Runs at start. Resolves when the person has accepted the current policy. */
  async ensure() {
    try { await this.load(); } catch { return; }
    if (this.state.accepted) return;
    await new Promise(done => this.gate(done));
  },

  gate(done) {
    const root = h('div', { class: 'gate' });
    const m = Modal.open(root, { label: 'Welcome' });
    m.el.onEscape = () => {};                              // cannot be skipped
    let accept, heads;
    const step1 = () => {
      accept = h('input', { type: 'checkbox', id: 'g-accept' });
      heads = h('input', { type: 'checkbox', id: 'g-heads' });
      const go = h('button', { class: 'btn primary', type: 'button', disabled: true, onclick: e => busy(e.currentTarget, async () => {
        this.state = await api('/api/consent', { method: 'PUT', json: { accept: true, heads: heads.checked } });
        step2();
      }) }, 'Accept and continue');
      accept.addEventListener('change', () => { go.disabled = !accept.checked; });
      root.replaceChildren(
        h('div', { class: 'modal-head' }, h('h2', { text: `Welcome to ${BRAND.name}` })),
        h('div', { class: 'modal-body' },
          h('p', { class: 'lead', text: `${BRAND.tagline} Before you start, here is what ${BRAND.name} does with your data. It is short.` }),
          h('div', { class: 'gate-points' },
            gatePoint('shield', 'Everything stays on your PC', `No account. Nothing is sent to ${BRAND.publisher}. Your worlds and settings live in your Windows user folder.`),
            gatePoint('network', 'It goes online only to get things', 'Minecraft files, Java, plugins and mods, and the public address from playit.gg. Each is listed in the policy below.'),
            gatePoint('settings', 'You stay in control', 'Optional features are off until you switch them on. You can delete your data at any time.')),
          h('details', { class: 'gate-policy' }, h('summary', { text: 'Read the full privacy policy' }), policyView())),
        h('div', { class: 'modal-foot gate-foot' },
          h('label', { class: 'check', for: 'g-accept' }, accept, h('span', { text: 'I have read and accept the privacy policy.' })),
          h('label', { class: 'check', for: 'g-heads' }, heads, h('span', {}, 'Show player head pictures. ', h('span', { class: 'hint', text: 'Optional. Sends player names to minotar.net and mc-heads.net. You can change it later.' }))),
          h('span', { class: 'grow' }), go));
    };
    const step2 = () => {
      const rows = { java: h('div'), playit: h('div') };
      const btn = h('button', { class: 'btn primary', type: 'button', onclick: () => busy(btn, async () => { paint(await api('/api/components/prepare', { method: 'POST' })); poll(); }) }, ico('arrow'), 'Download now');
      const fin = h('button', { class: 'btn', type: 'button', onclick: () => { stop(); m.close(); done(); } }, 'Skip for now');
      let timer = null;
      const stop = () => { if (timer) clearInterval(timer); timer = null; };
      const label = (c, name, what) => {
        const t = { ready: 'Ready', missing: 'Not downloaded yet', installing: c.text ? `${c.text} ${c.percent ? c.percent + '%' : ''}` : 'Downloading...', error: c.text || 'Failed. It will be tried again when needed.', unknown: '' }[c.state] || '';
        return [h('strong', { text: name }), h('span', { class: 'hint', text: what }), h('span', { class: 'gate-state ' + c.state, text: t })];
      };
      const paint = st => {
        rows.java.replaceChildren(...label(st.java, 'Java', 'Runs Minecraft servers.'));
        rows.playit.replaceChildren(...label(st.playit, 'playit helper', 'Gives friends a public address.'));
        const ready = st.java.state === 'ready' && st.playit.state === 'ready';
        btn.hidden = ready || st.running;
        fin.textContent = ready ? 'Start using ' + BRAND.name : st.running ? 'Continue in the background' : 'Skip for now';
        fin.className = ready ? 'btn primary' : 'btn';
        if (ready) stop();
      };
      const poll = () => { stop(); timer = setInterval(async () => { try { paint(await api('/api/components')); } catch { /* try again */ } }, 800); };
      root.replaceChildren(
        h('div', { class: 'modal-head' }, h('h2', { text: 'Get ready' })),
        h('div', { class: 'modal-body' },
          h('p', { class: 'lead', text: `${BRAND.name} needs two small downloads to run Minecraft servers. You can download them now so your first server starts faster, or skip: they download by themselves when needed.` }),
          h('div', { class: 'gate-rows' }, h('div', { class: 'gate-row' }, rows.java), h('div', { class: 'gate-row' }, rows.playit))),
        h('div', { class: 'modal-foot' }, h('span', { class: 'grow' }), btn, fin));
      api('/api/components').then(st => { paint(st); if (st.running) poll(); }).catch(() => {});
    };
    step1();
  },

  /* Panel settings card: read the policy, change the optional switch. */
  card(onChange) {
    const c = this.state || { accepted: false, heads: false, accepted_at: 0 };
    const heads = h('input', { type: 'checkbox', checked: !!c.heads, onchange: e => {
      const on = e.target.checked;
      busy(null, async () => { try { this.state = await api('/api/consent', { method: 'PUT', json: { heads: on } }); toast('Saved.', 'ok'); if (onChange) onChange(); } catch (err) { e.target.checked = !on; throw err; } });
    } });
    return h('section', { class: 'card', style: 'margin-top:14px' }, h('div', { class: 'card-h' }, h('h2', { text: 'Privacy' })),
      h('p', { class: 'hint', style: 'margin-top:0', text: c.accepted_at ? `You accepted the privacy policy on ${fmtDate(c.accepted_at)}. Everything stays on this PC unless a feature below says otherwise.` : 'Everything stays on this PC unless a feature says otherwise.' }),
      h('label', { class: 'check' }, heads, h('span', { text: 'Show player head pictures' })),
      h('p', { class: 'hint', style: 'margin:-6px 0 12px 28px', text: 'Sends player names to minotar.net and mc-heads.net. When off, a simple drawn face is shown.' }),
      h('div', { class: 'row-actions' },
        h('button', { class: 'btn', type: 'button', onclick: () => this.readPolicy() }, ico('shield'), 'Read privacy policy'),
        h('button', { class: 'btn', type: 'button', onclick: () => busy(null, () => api('/api/open-folder', { method: 'POST', json: { which: 'data' } })) }, ico('files'), 'Open my data folder')));
  },

  readPolicy() {
    const body = h('div', { class: 'modal-body' }, policyView());
    const m = Modal.open(h('div', { class: 'gate' },
      h('div', { class: 'modal-head' }, h('h2', { text: 'Privacy policy' }), h('span', { class: 'grow' }), h('button', { class: 'btn', type: 'button', onclick: () => m.close() }, 'Close')), body), { label: 'Privacy policy' });
  },
};

function gatePoint(icon, title, text) {
  return h('div', { class: 'gate-point' }, ico(icon), h('div', {}, h('strong', { text: title }), h('p', { text })));
}

/* ---------- Support dialog (top bar, right side) ---------- */
const Support = {
  open() {
    const mail = BRAND.supportEmail;
    const report = h('textarea', { class: 'support-report', readonly: true, rows: 9, hidden: true, spellcheck: 'false' });
    const copy = async (text, ok) => {
      try { await navigator.clipboard.writeText(text); toast(ok, 'ok'); }
      catch { report.hidden = false; report.value = text; report.select(); toast('Select the text and copy it (Ctrl+C).'); }
    };
    const m = Modal.open(h('div', { class: 'support' },
      h('div', { class: 'modal-head' }, ico('help'), h('h2', { text: 'Support' }), h('span', { class: 'grow' }), h('button', { class: 'btn icon-only', type: 'button', 'aria-label': 'Close', onclick: () => m.close() }, ico('close'))),
      h('div', { class: 'modal-body' },
        h('p', { class: 'lead', text: 'Something broken, or a question? Write to us. Nothing is sent from this app: you choose what to share.' }),
        h('div', { class: 'support-mail' }, h('strong', { text: mail }),
          h('button', { class: 'btn', type: 'button', onclick: () => copy(mail, 'Email address copied.') }, ico('copy'), 'Copy'),
          h('a', { class: 'btn primary', href: `mailto:${mail}?subject=${encodeURIComponent(BRAND.name + ' ' + BRAND.version + ' support')}`, target: '_blank', rel: 'noopener' }, ico('link'), 'Write an email')),
        h('h3', { text: 'Include a support report' }),
        h('p', { class: 'hint', text: `The report has your ${BRAND.name} and Windows version, Java status and the last log lines. It leaves out your Windows user name and secrets. Paste it into your email.` }),
        h('div', { class: 'row-actions' },
          h('button', { class: 'btn', type: 'button', onclick: e => busy(e.currentTarget, async () => { const r = await api('/api/support/report'); report.value = r.text; await copy(r.text, 'Report copied. Paste it in your email.'); }) }, ico('copy'), 'Copy support report'),
          h('button', { class: 'btn', type: 'button', onclick: () => busy(null, () => api('/api/open-folder', { method: 'POST', json: { which: 'logs' } })) }, ico('files'), 'Open logs folder')),
        report,
        h('h3', { text: `About ${BRAND.name}` }),
        h('p', { class: 'hint', text: `Version ${BRAND.version}. Made by ${BRAND.publisher} (${BRAND.publisherName}). ${BRAND.copyright}.` }),
        h('div', { class: 'row-actions' },
          h('button', { class: 'btn', type: 'button', onclick: () => { m.close(); Privacy.readPolicy(); } }, ico('shield'), 'Privacy policy')))), { label: 'Support' });
  },
};
