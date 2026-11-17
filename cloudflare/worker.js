// Zighost reports: one small Cloudflare Worker with a D1 database. Free plan is enough.
// It stores only what the app sends under the privacy policy:
//   /report  the text the person saw and chose to send          (explicit Send button in Support)
// There is no usage counting. It never stores IP addresses. /admin shows the reports and the GitHub download counts; it needs ADMIN_KEY.

const VERSION = /^\d{1,3}(\.\d{1,3}){1,3}$/;
const MAX_BODY = 40000;
const MAX_REPORTS_PER_DAY = 300;
let ready = false;

async function setup(env) {
  if (ready) return;
  await env.DB.batch([
    env.DB.prepare("CREATE TABLE IF NOT EXISTS reports (id INTEGER PRIMARY KEY AUTOINCREMENT, at INTEGER, version TEXT, os TEXT, contact TEXT, note TEXT, text TEXT)"),
  ]);
  ready = true;
}

const json = (obj, status = 200) => new Response(JSON.stringify(obj), { status, headers: { "content-type": "application/json", "cache-control": "no-store" } });
const clean = (v, n) => (typeof v === "string" ? v.slice(0, n) : "");

async function readJson(request) {
  const raw = await request.text();
  if (raw.length > MAX_BODY) throw new Error("too big");
  return JSON.parse(raw);
}

function authorised(request, env) {
  const given = (request.headers.get("authorization") || "").replace(/^Bearer\s+/i, "");
  const want = env.ADMIN_KEY || "";
  if (!want || given.length !== want.length) return false;
  let diff = 0;
  for (let i = 0; i < want.length; i++) diff |= given.charCodeAt(i) ^ want.charCodeAt(i);
  return diff === 0;
}

async function downloads(env) {
  try {
    const r = await fetch(`https://api.github.com/repos/${env.REPO}/releases?per_page=30`, { headers: { "user-agent": "zighost-reports", accept: "application/vnd.github+json" }, cf: { cacheTtl: 600 } });
    if (!r.ok) return [];
    return (await r.json()).map(rel => ({ tag: rel.tag_name, published: rel.published_at, count: (rel.assets || []).filter(a => /setup.*\.exe$/i.test(a.name)).reduce((n, a) => n + a.download_count, 0), portable: (rel.assets || []).filter(a => /portable/i.test(a.name)).reduce((n, a) => n + a.download_count, 0) }));
  } catch { return []; }
}

async function adminData(env) {
  const reports = (await env.DB.prepare("SELECT id, at, version, os, contact, note, text FROM reports ORDER BY id DESC LIMIT 50").all()).results;
  return { reports, downloads: await downloads(env) };
}

const PAGE = `<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Zighost reports</title>
<style>:root{color-scheme:dark light}body{font:15px system-ui,sans-serif;max-width:980px;margin:24px auto;padding:0 16px;background:#10141d;color:#e8edf5}
h1{font-size:22px}h2{font-size:16px;margin:28px 0 8px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.c{background:#171d2b;border:1px solid #2a3243;border-radius:8px;padding:12px}.c b{display:block;font-size:26px}.c span{color:#8c97ab;font-size:13px}
table{width:100%;border-collapse:collapse}td,th{padding:6px 8px;border-bottom:1px solid #2a3243;text-align:left;vertical-align:top}
pre{white-space:pre-wrap;background:#0c1018;border:1px solid #2a3243;border-radius:6px;padding:10px;font-size:12px;max-height:260px;overflow:auto}
input,button{font:inherit;padding:8px 10px;border-radius:6px;border:1px solid #2a3243;background:#171d2b;color:inherit}button{cursor:pointer}.muted{color:#8c97ab}
details{margin:6px 0}</style>
<h1>Zighost reports</h1>
<form id="f"><input id="k" type="password" placeholder="Admin key" autocomplete="current-password"> <button>Open</button> <span id="e" class="muted"></span></form>
<div id="out"></div>
<script>
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const when=t=>new Date(t*1000).toLocaleString();
async function load(key){
  const r=await fetch('/admin/data',{headers:{authorization:'Bearer '+key}});
  if(!r.ok){document.getElementById('e').textContent='Wrong key.';return false}
  const d=await r.json();
  document.getElementById('out').innerHTML=
   '<h2>Installer downloads (from GitHub)</h2>'+(d.downloads.length?'<table><tr><th>Version</th><th>Installer</th><th>Portable zip</th><th>Published</th></tr>'+d.downloads.map(x=>'<tr><td>'+esc(x.tag)+'</td><td>'+x.count+'</td><td>'+x.portable+'</td><td>'+esc((x.published||'').slice(0,10))+'</td></tr>').join('')+'</table>':'<p class="muted">No releases yet.</p>')+
   '<h2>Reports ('+d.reports.length+')</h2>'+(d.reports.map(r=>'<details><summary>#'+r.id+' '+esc(when(r.at))+' v'+esc(r.version)+' '+esc(r.contact||'')+' '+esc((r.note||'').slice(0,80))+'</summary><p class="muted">'+esc(r.os)+'</p><pre>'+esc(r.text)+'</pre><button data-id="'+r.id+'">Delete</button></details>').join('')||'<p class="muted">No reports.</p>');
  document.querySelectorAll('button[data-id]').forEach(b=>b.onclick=async()=>{await fetch('/admin/delete?id='+b.dataset.id,{method:'POST',headers:{authorization:'Bearer '+key}});load(key)});
  return true;
}
document.getElementById('f').onsubmit=async e=>{e.preventDefault();const k=document.getElementById('k').value;document.getElementById('e').textContent='';if(await load(k))try{sessionStorage.setItem('k',k)}catch{}};
try{const k=sessionStorage.getItem('k');if(k)load(k)}catch{}
</script>`;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    try {
      if (url.pathname === "/" || url.pathname === "/admin") return new Response(url.pathname === "/" ? "Zighost" : PAGE, { headers: { "content-type": "text/html;charset=utf-8", "cache-control": "no-store" } });
      await setup(env);
      if (request.method === "POST" && url.pathname === "/report") {
        const d = await readJson(request), now = Math.floor(Date.now() / 1000);
        const text = clean(d.text, 20000);
        if (!text.trim() || !VERSION.test(d.v || "")) return json({ error: "bad" }, 400);
        const recent = (await env.DB.prepare("SELECT COUNT(*) AS n FROM reports WHERE at > ?").bind(now - 86400).first()).n;
        if (recent >= MAX_REPORTS_PER_DAY) return json({ error: "busy" }, 429);
        await env.DB.prepare("INSERT INTO reports (at, version, os, contact, note, text) VALUES (?, ?, ?, ?, ?, ?)")
          .bind(now, d.v, clean(d.os, 80), clean(d.contact, 120), clean(d.note, 1500), text).run();
        return json({ ok: true });
      }
      if (url.pathname.startsWith("/admin/")) {
        if (!authorised(request, env)) return json({ error: "no" }, 401);
        if (request.method === "GET" && url.pathname === "/admin/data") return json(await adminData(env));
        if (request.method === "POST" && url.pathname === "/admin/delete") {
          await env.DB.prepare("DELETE FROM reports WHERE id = ?").bind(Number(url.searchParams.get("id")) || 0).run();
          return json({ ok: true });
        }
      }
      return json({ error: "not found" }, 404);
    } catch (e) {
      return json({ error: "failed" }, 400);
    }
  },
};
