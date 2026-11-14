// Runs cloudflare/worker.js against an in-memory SQLite that imitates the parts of D1 it uses.  node tests/worker_test.mjs
import { DatabaseSync } from "node:sqlite";
import assert from "node:assert/strict";
import worker from "../cloudflare/worker.js";

const raw = new DatabaseSync(":memory:");
const stmt = sql => ({ b: [], bind(...a) { this.b = a; return this; },
  run() { raw.prepare(sql).run(...this.b); return {}; },
  first() { return raw.prepare(sql).get(...this.b) || null; },
  all() { return { results: raw.prepare(sql).all(...this.b) }; } });
const env = { DB: { prepare: stmt, batch: async list => { for (const s of list) s.run(); } }, ADMIN_KEY: "secret-key-123", REPO: "x/y" };
globalThis.fetch = async () => ({ ok: true, json: async () => [{ tag_name: "v0.1.0", published_at: "2026-11-13", assets: [{ name: "Zighost-Setup-0.1.0.exe", download_count: 7 }, { name: "Zighost-0.1.0-portable.zip", download_count: 2 }] }] });

const call = (path, method = "GET", body, headers = {}) => worker.fetch(new Request("https://w.test" + path, { method, body: body ? JSON.stringify(body) : undefined, headers }), env);
const ID = "11111111-2222-3333-4444-555555555555";

assert.equal((await call("/ping", "POST", { id: "bad", v: "0.1.0" })).status, 400);
assert.equal((await call("/ping", "POST", { id: ID, v: "0.1.0; drop" })).status, 400);
assert.equal((await call("/ping", "POST", { id: ID, v: "0.1.0", os: "Windows 11" })).status, 200);
assert.equal((await call("/ping", "POST", { id: ID, v: "0.2.0", os: "Windows 11" })).status, 200);      // same id: updated, not duplicated
assert.equal((await call("/report", "POST", { v: "0.1.0", os: "Windows 11", text: "hello", note: "n", contact: "a@b.c" })).status, 200);
assert.equal((await call("/report", "POST", { v: "0.1.0", text: "   " })).status, 400);
assert.equal((await call("/report", "POST", "x".repeat(50000))).status, 400);                            // too big
assert.equal((await call("/admin/data")).status, 401);
assert.equal((await call("/admin/data", "GET", null, { authorization: "Bearer wrong-key-12345" })).status, 401);
const ok = await call("/admin/data", "GET", null, { authorization: "Bearer secret-key-123" });
const d = await ok.json();
assert.equal(d.total, 1); assert.equal(d.active7, 1); assert.equal(d.versions[0].k, "0.2.0");
assert.equal(d.reports.length, 1); assert.equal(d.downloads[0].count, 7); assert.equal(d.downloads[0].portable, 2);
assert.equal((await call("/forget", "POST", { id: ID })).status, 200);
assert.equal((await (await call("/admin/data", "GET", null, { authorization: "Bearer secret-key-123" })).json()).total, 0);
assert.equal((await call("/admin/delete?id=1", "POST", null, { authorization: "Bearer secret-key-123" })).status, 200);
assert.equal((await (await call("/admin/data", "GET", null, { authorization: "Bearer secret-key-123" })).json()).reports.length, 0);
assert.equal((await call("/nope")).status, 404);
for (let i = 0; i < 3000; i++) raw.prepare("INSERT INTO installs VALUES (?, ?, ?, '0.1.0', 'x')").run("f" + i, Math.floor(Date.now() / 1000), Math.floor(Date.now() / 1000));
assert.equal((await call("/ping", "POST", { id: "99999999-2222-3333-4444-555555555555", v: "0.1.0" })).status, 429);   // flood stopped
const stored = raw.prepare("SELECT sql FROM sqlite_master").all().map(r => r.sql).join(" ");
assert.ok(!/\bip\b/i.test(stored), "no ip column");
console.log("worker ok");
