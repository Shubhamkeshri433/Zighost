# Zighost stats Worker

Counts people using the app (only the anonymous daily message), holds the reports people chose to send, and shows
installer download counts from GitHub. Free Cloudflare plan is enough. No IP addresses are stored.

Set up (all in the Cloudflare dashboard, no command line):
1. Workers & Pages > Create > Worker > name it `zighost-stats` > Deploy, then Edit code, paste `worker.js`, Deploy.
2. Storage & databases > D1 > Create database `zighost-stats`. (Tables are created by the Worker itself.)
3. Worker > Settings > Bindings > Add > D1 database: variable name `DB`, pick `zighost-stats`.
4. Worker > Settings > Variables and secrets: add a Secret `ADMIN_KEY` (a long random text) and a Text variable `REPO` = `Shubhamkeshri433/Zighost`.
5. Copy the Worker address (`https://zighost-stats.<name>.workers.dev`) into `STATS_URL` in `backend/brand.py`, then publish a new version.
6. Open `<address>/admin`, type the admin key. You see users, versions, downloads and reports.

Test locally: `node --no-warnings tests/worker_test.mjs`.
