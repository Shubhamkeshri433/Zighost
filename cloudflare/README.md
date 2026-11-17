# Zighost reports Worker

Holds the support reports people chose to send (the Send button in Support) and shows installer download counts from
GitHub. It does not count users: there is no usage message any more. Free Cloudflare plan is enough. No IP addresses are stored.

Set up (all in the Cloudflare dashboard, no command line):
1. Workers & Pages > Create > Worker > name it `zighost-stats` (the existing name is kept so the address stays the same) > Deploy, then Edit code, paste `worker.js`, Deploy.
2. Storage & databases > D1 > Create database `zighost-stats`. (The table is created by the Worker itself.)
3. Worker > Settings > Bindings > Add > D1 database: variable name `DB`, pick `zighost-stats`.
4. Worker > Settings > Variables and secrets: add a Secret `ADMIN_KEY` (a long random text) and a Text variable `REPO` = `Shubhamkeshri433/Zighost`.
5. Copy the Worker address (`https://zighost-stats.<name>.workers.dev`) into `REPORTS_URL` in `backend/brand.py`, then publish a new version.
6. Open `<address>/admin`, type the admin key. You see reports and download counts.

If this Worker ran an earlier version that counted usage: paste the new `worker.js`, then in the D1 console run
`DROP TABLE IF EXISTS installs;` to delete the old usage numbers.

Test locally: `node --no-warnings tests/worker_test.mjs`.
