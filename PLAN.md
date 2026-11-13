# MC Panel: project plan

A local dashboard to create and manage Minecraft servers on your own PC.
Public address comes from playit.gg (guest mode possible, no account needed to start).

> This file is the project memory. If you start a new chat, paste or attach this file
> (and `CLAUDE.md`) so the context carries over.

## 1. Goal and decisions

| Topic | Decision |
|---|---|
| Where it runs | The user's own PC (Windows first, Linux/Mac should also work) |
| Cloud / database | None. Everything is local JSON files and folders |
| Backend | Python, **Starlette + uvicorn** (not FastAPI: pip is blocked in the build sandbox, Starlette was already installed) |
| Live console | **Server-Sent Events** (no `websockets` package needed) |
| Frontend | Plain HTML/CSS/JS, no build step, served by the backend at `http://localhost:8765` |
| Public IP | playit.gg official agent binary, started and watched by the panel |
| Rejected | Google Colab (ToS risk, 12h limit, temporary disk), Oracle free VPS (free ARM tier cut to 2 OCPU / 12 GB in 2026, card needed, hard to set up) |
| Later option | Same backend can run on a VPS. Only add a login first |

## 2. Architecture

```
Browser  ->  http://localhost:8765  (frontend/ static files)
                |  JSON API + SSE
          backend/app.py (Starlette)
           |- manager.py    start/stop/kill, console buffer, crash restart, players
           |- providers.py  version lists + download URLs (vanilla, paper, purpur, fabric, spigot)
           |- java_rt.py    find Java, pick the version a Minecraft version needs, auto-download
           |- playit.py     download/run playit agent, parse claim link + address
           |- backups.py    zip / restore worlds safely
           |- props.py      read/write server.properties
           '- store.py      JSON settings + server list (atomic writes)
data/ (created on first run)
  settings.json  servers.json
  servers/<id>/      one folder per Minecraft server
  backups/<id>/      zip files
  runtime/           downloaded Java + playit agent
```

Safety rules built in from day one:
- Listens on `127.0.0.1` only. Rejects other Host headers and any write request without the `X-MCPanel` header (stops random websites from calling the local API).
- Server ids are validated, zip files are checked against path escape (zip-slip).
- Only one Minecraft server runs at a time (same RAM, same default port).
- Stop = `stop` command + wait + only then kill. World is saved before backups.

## 3. Dashboard pages

1. **Overview**: the server as friends see it (server-list style card), big Start/Stop, address with copy button, CPU/RAM graph, players online, install progress.
2. **Console**: live log, command box, history with up/down arrows, auto-scroll toggle.
3. **Properties**: common settings as a form (gamemode, difficulty, max players, MOTD, PvP, online-mode...), the rest under Advanced. Marks "restart needed".
4. **Backups**: create, restore, delete, size and date. Auto backup on a timer (Phase 2).
5. **Servers**: list, create wizard (type, version, RAM, port, EULA), delete.
6. **Network**: playit.gg status, claim/guest link, tunnel address, step by step help.
7. **Settings**: Java path, playit path, contact for download APIs, auto-restart on crash, default RAM.

Copy rules: sentence case, plain words, buttons say what happens ("Start server"), errors say what to do.

## 4. Server types

| Type | How it is obtained | Status |
|---|---|---|
| Vanilla | Mojang version manifest -> server jar | coded, needs live test |
| Paper | `fill.papermc.io/v3` (verified in docs; needs a User-Agent with contact info) | coded, needs live test |
| Purpur | `api.purpurmc.org/v2` | coded from memory, needs live test |
| Fabric | `meta.fabricmc.net/v2` server jar endpoint | coded from memory, needs live test |
| Spigot | Download BuildTools, run it (5-10 min, needs JDK + git) | coded, needs live test |
| Forge / NeoForge | installer based | Phase 4 |

## 5. Phases and status

**Phase 1: MVP** (done in first build)
- [x] Project skeleton, store, settings
- [x] Create server (download jar, EULA, properties), progress
- [x] Start / stop / restart / kill, console stream, commands
- [x] playit agent download + run + claim link + address detection
- [x] Dashboard UI with demo mode (works without backend, for preview)
- [x] Simulated tests (fake Minecraft process) for the process manager
- [x] Sandbox tests + browser end-to-end with fake Java (2026-11-10)
- [ ] **Live test on a real Windows PC** (downloads, Java, playit)  <- next

**Phase 2: Core**
- [x] Properties editor, backups (manual) and restore
- [x] Auto backup every N minutes, keep last N
- [x] Players page: whitelist, ops, bans
- [x] Plugin/mod installer (Modrinth only, no Hangar yet) + drag and drop upload
- [x] File browser

**Phase 3: Polish**
- [ ] Windows `.exe` (PyInstaller) with tray icon and auto-open browser
- [ ] Crash report (graphs history and Discord webhook done)
- [ ] Update server version with backup first
- [ ] Panel password + optional LAN access

**Phase 4: Extras**
- [ ] Forge / NeoForge, modpacks
- [ ] Bedrock (Geyser) helper
- [ ] Multiple servers running at once (needs per-server ports and RAM check)

## 6. Known risks and open questions

- playit guest mode: guest tunnels may be temporary or limited. Not documented in what I could read. Test how long the address stays the same; the UI should offer "link account" if it changes.
- playit agent output format and release asset names are not documented on the official pages I could fetch. The code picks the asset by platform keywords and parses output with loose patterns, plus a manual "paste address" fallback.
- Paper's API requires a contact in the User-Agent. The user sets it in Settings (not hard-coded).
- Minecraft changed to year-based version numbers in 2026 (for example 26.x). Java version is read from Mojang's version JSON, with a fallback table.
- Running a server and playing on the same PC shares RAM/CPU. Default RAM 2 GB, panel warns if RAM is above 60% of the system.
- Not yet verified: any live network call (the build sandbox had no outbound access to the vendor APIs).

## 7. Build log

**2026-11-10: finished Phase 1 code.** When this session started, only `backend/{manager,providers,java_rt,props,backups,store}.py`
existed on disk. This file said `app.py`, `playit.py`, the frontend, tests and `run.py` were done, but they were missing.
They were written now:
- `backend/app.py` (API, SSE console, Host and header guard), `backend/playit.py`, `run.py`, `start.bat`, `requirements.txt`
- `frontend/` (`index.html`, `style.css`, `app.js`, `demo.js`), `tools/make_preview.py` -> `frontend/preview.html`
- `tests/test_manager.py` + `tests/fake_java/` (fake Minecraft process)

Checked here (Linux sandbox, fake Java, no internet): 13 unit and API tests pass (`python -I tests/test_manager.py`);
a real-browser run against the real backend passed start -> live console -> command -> player list -> properties save ->
backup while running -> restore refused while running -> clean stop, with no JS errors; mobile width has no sideways scroll.
Fixed on the way: finished server processes leaked their stdin/stdout handles (`manager._reader`).

**Still NOT checked (needs a real Windows PC with internet):**
- Real downloads: Mojang, Paper, Purpur, Fabric, BuildTools, Temurin Java.
- playit: the GitHub release asset names, and how the agent prints its claim link and address. In the sandbox the GitHub
  call returned 403, so only the error path was seen. The parser is tested on made-up sample lines only.
- Anything on Windows (hidden console windows, `start.bat`, port check behaviour).

**Design notes (frontend):** server card imitates the in-game multiplayer list (pixel icon, signal bars). Palette: deepslate
blue backgrounds, lapis accent, emerald/gold/redstone only for status. System fonts, no external requests.

## 8. Run

```
pip install -r requirements.txt
python run.py            # opens http://localhost:8765
```
Windows: double-click `start.bat`.

## 9. Progress log (newest last; updated after every stage)

**2026-11-11 checkpoint 0 (before continuing).** Found on disk, not recorded before:
- Backend modules written, compile, but NOT yet wired into `app.py` or tested: `players.py`, `plugins.py`, `files.py`, `fsops.py`,
  `scheduler.py`, `notify.py`, `mcping.py`. `playit.py` already reworked for playit v2 (own v1 agent in `runtime/playit`,
  never launches the installed v2 GUI; flags found via `--help`). Not yet tested on a real PC.
- Frontend written: `schema.js`, `propform.js`, `core.js`, `pages-overview.js`, `pages-console.js`, `pages-players.js`.
- `frontend/index.html` loads 9 scripts that do NOT exist yet: `pages-settings/files/plugins/backups/automation/servers/network/panel.js`, `main.js`.
  So the new dashboard cannot open until they are written. (Old Phase 1 `app.js` is no longer loaded.)
- 13 core tests pass.
User feedback driving this round: playit shows no IP (v2 GUI was launched); wants full server settings at creation, an
advanced Players section, better layout/colours, and every option in one place.

**2026-11-11 checkpoint 1 (correction).** `backend/app.py` IS already wired for everything: players, files, plugins, schedules, worlds,
backup download, PATCH server, create with properties and jvm_args, playit mode "external". Only the 9 frontend files were missing.
Page contract used by every `frontend/pages-*.js`: `Pages.<id> = {title, desc, icon, group, needsServer, mount(el), show(), update(st)}`;
`main.js` builds nav from these, polls `/api/status`, draws the top bar and routes (`go(id)`, `refresh()`).

**2026-11-11 stage A done (backend gaps).** Found and fixed: `notify.py` read settings keys that `store.py` did not have, so a Discord
link could never be saved; and neither `notify.py` nor `mcping.py` was called by anything. Now: settings `discord_webhook`,
`notify_server`, `notify_players`; the link is never sent back to the browser (`discord_webhook_set`); `manager.on_event` fires on
online / stopped / crashed / join / leave; new routes `POST /api/notify/test` and `POST /api/network/test` (server-list ping of the
public address or of this PC). 13 core tests still pass.
Next: stage B `main.js`, `pages-settings.js`, `pages-servers.js` (wizard with all settings).

**2026-11-11 stage B written (not yet run in a browser).** `frontend/main.js` (boot, nav grouped Server/Manage/Panel, polling, top bar with
server switcher + Start/Stop/Restart + copy-address chip, routing, themes), `pages-settings.js` (server options + every
server.properties setting, search, advanced toggle, presets, per-field reset, sticky Save bar, restart reminder),
`pages-servers.js` (4-step wizard: type+version, memory+port+Java args, ALL game settings with presets, review+EULA; server list).
`propform.js` got a `hide` option so the port is edited in one place only.
Next: stage C `pages-files/plugins/backups/automation/network/panel.js`.

**2026-11-11 stage C written (not yet run in a browser).** `pages-files.js` (browse, edit with Ctrl+S, upload by button or drag and drop,
download, rename, delete, new folder), `pages-plugins.js` (installed list with on/off switch, Modrinth search + one-click install,
upload a jar; vanilla explains why not), `pages-backups.js` (backups: make/download/restore/delete; worlds: sizes + fresh world with typed confirmation),
`pages-automation.js` (scheduled jobs: backup/restart/command, presets; Discord notices with test button), `pages-network.js`
(managed helper vs own playit app, claim link, connection tests via server-list ping, manual address), `pages-panel.js`
(3 themes, defaults, advanced paths/keys, facts about this PC). All 16 scripts that `index.html` loads now exist.
Next: stage D = rewrite `demo.js` for the full API, update `tools/make_preview.py`, open it in a browser, screenshots, fix.

**2026-11-11 stage D started.** `demo.js` extended for players, files, plugins, schedules, worlds, PATCH, network/notify tests, new settings keys.
`tools/make_preview.py` now inlines every script listed in index.html, in order. Next: open preview in a real browser, screenshot all pages, fix errors.

**2026-11-11 stage D started (saved).** `demo.js` rewritten for the new API (players, files, plugins, schedules, worlds, PATCH, network/notify test, settings extras).
`tools/make_preview.py` now inlines every script listed in `index.html`, in order. Not yet opened in a browser; next: screenshots of all pages and 3 themes, fix errors, e2e with fake Java, new tests.
- preview builder fixed (str.replace bug), preview.html regenerated.
- style.css: nowrap buttons, wider job selects.

**2026-11-11 stage D: browser check of preview done.** All 11 pages load with no JS errors (Chromium, preview mode). Wizard checked end to end
(name required, 4 steps, create shows install progress). Themes deepslate/nether/daylight switch and save. Mobile drawer opens.
Not yet done: real-backend run (fake Java), new tests, playit on a real Windows PC.

**2026-11-11 stage D: real backend run.** Backend started on a temp data dir with a seeded server + fake Java. In a real browser (not demo): all 11 pages load,
Start -> Online and Stop -> Offline work from the top bar, console and players pages open. Network test shows a clear error when nothing listens (expected with fake Java).
mcping checked against a fake server-list server: OK. Tests: test_manager 13/13, test_backend2 19/19.
Still unverified: playit on a real Windows PC, real downloads of server jars/Java/playit (sandbox has no access).

---
## 10. Round 2 plan (still version 0.1.0). Written 2026-11-12, NOT started yet

Source: user feedback after seeing the dashboard, plus two reference screenshots in `docs/refs/`
(`ref-create-wizard.png` = full-screen create wizard with step bar; `ref-tunnel-page.png` = server workspace with back arrow, Start button,
address chip and a tunnel table). Rule: take the *concept* (easy, attractive), never copy the look. Our own theme, icons and wording stay.

### 10.1 The 13 requests, what we will do, and how we know it is done

| # | Request | Plan | Done when |
|---|---------|------|-----------|
| 1 | playit guest account does not work | See 10.2. Panel drives the claim itself through playit's API and opens the claim page. Guest first, normal sign-in is the same page (fallback). Tunnel is created by the panel, per server. | User on Windows gets an address with guest, and with an account. Error text is human, never raw. |
| 2 | Create server as a popup with steps | Full-screen modal wizard: 1 Type and version, 2 Name and icon, 3 Plugins or mods (skipped when the type has none), 4 World, 5 Performance, 6 Review. Step bar on top, back/next at the bottom, remembers choices. | Can create every type from the modal, keyboard works, mobile width works. |
| 3 | Online visibility (public server list) | NOT now. Written down for a later version only. Do not add UI or fields. | - |
| 4 | Plugins and mods only where supported, by version | Capability table per type (10.4). Page and nav entry hidden for vanilla. Search is filtered by loader and game version. Label says Plugins or Mods. | Vanilla shows no plugin page; Paper shows plugins only; Fabric shows mods only. |
| 5 | Automation layout overlaps | Rebuild the job row as a wrapping grid, fixed control widths, header buttons wrap under the title on narrow screens. | No overlap from 360 px to 1920 px. |
| 6 | Backups: open file location | Button "Open folder" on Backups (also Files, and Panel for the data folder). Backend opens only folders from a fixed allow-list by key (`backups`, `server`, `data`), never a path from the browser. | Click opens Explorer at the right folder on Windows. |
| 7 | Players show Minecraft heads | Head image (face only) next to every name in all lists. Backend fetches and caches heads on disk, so the browser only talks to localhost. Fallback: our own pixel face when offline or name unknown. | Heads show for online, whitelist, ops, bans, known lists. |
| 8 | No default selected server, cards instead | Home = grid of server cards (icon, name, type, version, status dot, players, address, Start/Stop, Open). Opening a card enters the server workspace (sidebar of that server, back arrow to the list). Top-bar server dropdown removed. | App opens on cards. No server is selected until the user opens one. |
| 9 | Server logo | Icon picker: set of original pixel items and blocks, plus upload with crop and zoom (client side, exported as 64x64 PNG). Saved as `server-icon.png` in the server folder (Minecraft shows it in the multiplayer list) and used on cards and headers. | Logo shows on card, header and in the Minecraft server list. |
| 10 | Settings: only what users use | Audit `schema.js`. Keep about 25 fields in 5 groups (10.5). Everything else is removed from the UI, and unknown keys in the file are never touched. JVM args and similar move into one collapsed "Expert" box under Performance. | Settings page fits in two screens, no field a player has never heard of. |
| 11 | Keep version 0.1.0 | Revert 0.2.0 to 0.1.0 everywhere (backend VERSION, demo.js, preview, UI). Never bump unless asked. | `grep 0.2.0` finds nothing. |
| 12 | Fix overlapping UI on every page | Automated overlap check (Playwright at 360, 768, 1024, 1280, 1920 px, all pages, all 3 themes): flags horizontal scroll, clipped text, overlapping boxes. Fix all, re-run until clean. | Check script reports zero issues; screenshots reviewed. |
| 13 | Must be able to become desktop software later | Design rules in 10.6, applied from now on. Website-style start.bat stays for now. | Rules written in CLAUDE.md and followed in every new file. |

### 10.2 playit: why it fails and how we fix it
Facts found (sources at the end):
- The agent pairing flow is: make a random claim code, show the user a link, the user opens it and accepts, the agent exchanges the code for a secret key.
- The playit API has `claim_setup`, `claim_exchange`, `claim_accept`, a `login_guest` call and an account status `guest`. So guest accounts exist and an agent can be linked to one.
- A guest cannot be created without a browser step: the person must open the claim page once and choose guest or sign in. That step cannot be skipped by us.
- Tunnels can be created through the API (`tunnels_create`: type, tcp/udp/both, local ip and port). Guests have small limits (the reference app shows Java 1 of 4 tunnels).
Unknown (cannot test from this sandbox, no access to playit.gg): the exact reason it failed on the user's PC. Needed from the user: the text in Network, "Helper details and log".
Plan:
1. Add a clear log and "Copy diagnostics" button, so one paste tells us what happened.
2. Stop depending on the old v1 agent printing a claim link. Panel does the claim itself: generate code, `claim_setup`, open `https://playit.gg/claim/<code>`, poll `claim_exchange`, store the secret (never shown again).
3. Panel creates one tunnel per server through the API (Java, tcp, `127.0.0.1:<server port>`), reads the public address from the tunnel list, shows it everywhere. The agent process only carries traffic.
4. Guest limit reached or guest refused: say it in plain words and show the one-click "sign in with an account" path (same claim link, different button on playit's page).
5. Keep manual address and own-app mode as the last fallback.
6. Tunnel table on the server's Network tab (type, address, local port, on/off), concept from the reference.
Risk: API details come from docs of the Rust client, not from live calls. First live test is on the user's PC. Everything is behind clear errors so one screenshot is enough to fix.

### 10.3 Navigation and layout (items 8, 2, 9)
```
App opens ->  Servers (cards)           [+ New server]  [Panel settings]
                |  open a card
                v
             Server workspace: back arrow | icon + name + status | Start/Stop | address chip
               tabs: Overview  Console  Players  Settings  Files  Plugins/Mods  Backups  Automation  Network
```
- Global (not per server): Servers home, Panel settings, create wizard.
- Selected server lives in the URL hash (`#/s/<id>/players`), so reload and back button work, and nothing is selected by default.

### 10.4 Capability table (item 4)
| Type | Plugins | Mods | Modrinth loader filter |
|------|---------|------|------------------------|
| Vanilla | no | no | - |
| Paper, Spigot, Purpur | yes | no | paper, spigot, purpur, bukkit (+ game version) |
| Fabric | no | yes | fabric (+ game version) |
Hangar and Forge/NeoForge stay in Phase 3.

### 10.5 Settings to keep (item 10), for review
Basics: server name (MOTD), difficulty, game mode, max players, whitelist, online mode (premium check).
World: seed (only for a new world), world type, generate structures, allow nether, hardcore, spawn protection, allow flight, command blocks.
Players: PvP, force game mode, spawn animals, spawn monsters, spawn NPCs, player idle timeout.
Performance: view distance, simulation distance, memory (RAM), tuned Java flags. Expert (collapsed): extra Java arguments.
Network: port (shown read-only on workspace, editable here), nothing else.
Removed from UI: rcon, query, network compression, text filtering, resource pack hash, enforce secure profile, entity broadcast range, rate limits, and similar.

### 10.6 Desktop-software rules (item 13), apply to all new code
- No CDN, no web fonts, no external scripts. Everything the page needs ships in the folder.
- Backend is the only thing that touches disk, processes, Explorer. The page never builds a file path.
- All paths come from one config module (`store.DATA`); no hard-coded drive letters.
- `run.py` is the single entry point; the browser is only the window. Later: wrap the same pages in a native window (pywebview) and build an .exe with PyInstaller, tray icon, auto-update. No code change in pages should be needed.
- Local only: host check and `X-MCPanel` header stay.
- Anything remote (heads, Modrinth, playit) goes through the backend with a cache and a timeout, so the app works offline with graceful fallbacks.

### 10.7 Stages and saves (each stage ends with: files on disk, tests green, log entry here)
- **R0 housekeeping:** version back to 0.1.0, CLAUDE.md rules, refs saved (refs saved already).
- **R1 playit:** claim in the panel, tunnel through API, diagnostics, tests with a fake API. User tests on Windows while R2 goes on.
- **R2 shell:** server cards home, per-server workspace and hash routing, remove the dropdown.
- **R3 create:** modal wizard (6 steps), capability table, icon picker (original pixel set + upload and crop), `server-icon.png` write, card icons.
- **R4 pages:** settings curated, players with heads, backups open folder, automation layout, plugin/mod page by capability.
- **R5 quality:** overlap checker, fix all pages and themes, new tests, demo.js and preview updated, real-backend run, zip delivered.
Order is chosen so the user's blocker (playit) can be tested first.

### 10.8 Decisions I will take unless told otherwise
- Item icons: **original pixel art made for this project** (about 40 blocks and items) instead of Mojang's game textures, to stay clear of copyright. Upload covers anything else.
- Heads come from a public skin service through our backend cache (needs internet only for new names).
- Wizard's plugin step offers a short curated list (permissions, essentials, world tools, map pregeneration), nothing preselected.
- Version stays 0.1.0.

### 10.9 Sources
- playit Rust API client (claim, guest login, tunnels): https://docs.rs/playit-api-client/0.1.2/src/playit_api_client/api.rs.html
- playit agent CLI pairing flow: https://deepwiki.com/playit-cloud/playit-agent/3.1-agent-cli
- playit forum, pairing the CLI: https://discuss.playit.gg/t/how-do-you-actually-pair-playit-cli-to-my-account/1356
- 2026-11-12 round 2 plan written (section 10), refs saved in docs/refs, CLAUDE.md rules added. Waiting for user go-ahead before R0.

**2026-11-12 R0 + R1 done (saved).** R0: version back to 0.1.0 (app.py, demo.js, user agents). R1 playit: the panel now does the claim itself
(`/claim/setup` poll -> `/claim/exchange`), opens the link, stores the key; then makes a Minecraft Java tunnel for the server port through the API
(3 request variants, every answer logged); the old v1 agent only carries traffic. Own key only (the installed playit app's key is never reused).
Account type shown (guest/ready), plain messages for reject, timeout, limit, banned. New: Copy report (diagnostics, key hidden), Unlink, tunnel note.
Tests: test_playit.py 14 (fake API), test_manager 13, test_backend2 19, all green. UNVERIFIED on a real PC: API field names come from the Rust client docs.
If the tunnel step fails the Network page says what to click on playit.gg, and Copy report gives exact error text. Next: R2 (server cards + workspace).
- R2 step 1/5 core.js + index.html topbar done (saved)
- R2 step 2/5 main.js rewritten: hash routing #/ #/panel #/s/<id>/<page>, no default selection, back button, other-server chip (saved)
- R2 step 3-4/5: home cards (pages-servers.js) + CSS written (saved); next: browser check

**2026-11-12 R2 done (saved).** App opens on server cards. No server is selected by default. Card: icon, name, type+version, status dot, players, address chip, Start/Stop (one server at a time),
Open, Delete, installing progress bar, "New server" card. Opening a card enters the workspace: back arrow, icon+name, status pill, "X is running" chip when another server runs,
address chip, restart, Start/Stop. Sidebar switches between (Servers, Panel settings) and (All servers + the 9 server pages). Routes: `#/`, `#/panel`, `#/s/<id>/<page>`;
reload, back button, deep links and unknown ids all handled. Checked in preview and on the real backend (card Start -> Online, Open, deep link, Stop). No JS errors.
Next: R3 (create wizard modal, logo picker, plugin/mod capability).
- R3a backend done (saved): servericon.py (64x64 PNG check), /api/servers/{sid}/icon GET/PUT/DELETE, create accepts icon + starter plugins (installed after the server, failures only logged), status servers carry icon version, system types carry extends (plugins/mods/none) + speed. tests/test_servericon.py 9 ok. Next R3b icons.js + picker, R3c wizard.
- R3b done (saved): icons.js = Modal helper + 25 original pixel blocks/items (code-drawn) + IconPicker (items+background, or upload with drag/zoom crop and Smooth/Blocky/Chunky style) -> 64x64 PNG; serverIcon() shows real icon on cards, topbar, overview hero. Checked in browser. Next R3c wizard modal.
- R3c wizard.js written (6 steps, modal), pages-servers.js slimmed to cards, demo types updated (saved); next: browser check + create e2e
- R3 done: wizard (6 steps), icon picker, Settings "Server icon" card (PUT/DELETE icon), demo mocks. Next: R4 (Settings curation, Players heads, Backups open folder, Automation layout, Plugins by capability), then R5 overlap checks.
- R4a done: POST /api/open-folder (keys backups/server/data only, path built in backend/openfolder.py); buttons on Backups, Files, Panel. Next: Players heads, Settings curation, Automation layout, Plugins by capability.
- R4b done: backend/heads.py + GET /api/head/{name} (name regex, disk cache 7d, miss cache 1d, tests/test_heads.py), avatar() uses real face with pixel-face fallback.
- R4c done: Settings curated to 4 groups / 22 fields (+ port, memory, name in Server options, Expert box for Java args); remote/pack/security/advanced fields removed from UI, unknown keys untouched; advanced toggle and key names removed.
- R4d done: Automation job row now flex-wrap (no fixed columns, no overlap).
- R4e done: nav hides Plugins for vanilla, labels it Plugins or Mods by capability (extOf); page title follows; Modrinth search already filters by loader and game version. R4 complete. Next R5: overlap checker, all pages, 5 widths, 3 themes.
- R5a done: overlap checker (scratchpad overlap.js: 9 pages + servers + panel, 5 widths, 3 themes) reports 0 issues after fixing Panel summary overflow. Mobile is NOT a goal (desktop software), only desktop widths matter.
- R5b done: real-backend smoke (open-folder allow-list, head 404 offline/invalid, bad icon rejected at create). All 5 test suites pass.
- R6 playit fix (from user's real report): agent links fine but account was email-not-verified so tunnel creation failed. Panel messages now kept apart from helper chatter (notes deque, filtered noise) and shown first in "Copy report"; tunnel retried about once a minute; clear note to verify email; claim step text says sign-in is needed (guest not offered). Still unverified live: that tunnel creation works once the email is verified.

## 11. Round 3 (user feedback after real test)

Done in code:
- Start error "port in use" now names the program holding the port and suggests a free port (tests updated).
- Fabric mods: when no mod is made for the server's Minecraft version (new versions have few), Find new now says so and names the versions most mods support. Needs live check on user's PC (Modrinth cannot be reached from the sandbox).
- playit: one tunnel per server (name "MC Panel <server id>"), helper restarts when another server starts, address is picked by tunnel name, never borrowed from another server. Old tunnel "MC Panel 25565" is ignored; user can delete it on playit.gg.
- Panel messages kept apart from helper chatter in "Copy report", retry once a minute, email-not-verified note.

Remember for later (user asked, do NOT do now):
- [ ] Rename the application and make a new logo. Plan: one constants file `backend/brand.py` (NAME, SHORT, DATA_DIR_NAME, USER_AGENT, TUNNEL_PREFIX, CLAIM_NAME) plus frontend `brand.js`; today the name "MC Panel" appears in: page titles, topbar/side logo, playit claim name and tunnel prefix, User-Agent strings, zip/folder name, start.bat window title, notices text, Discord messages, diagnostics header. Changing TUNNEL_PREFIX later orphans old tunnels (keep reading the old prefix too).

## 12. Running it as a product (decisions only, no code yet)

### 12.1 Shipping
- Build: PyInstaller one-folder app (Python + backend + frontend inside) -> Windows installer (Inno Setup) per-user, no admin rights needed. App files in `%LOCALAPPDATA%\Programs\<Name>`, user data in `%APPDATA%\<Name>` (already one data root `store.DATA`), so updates never touch worlds.
- Window: later wrap the UI in a native window (pywebview/WebView2) with the same local server inside; browser mode stays as fallback.
- Hosting: GitHub Releases (free, versioned, checksums). Landing page on GitHub Pages / Cloudflare Pages.
- Windows SmartScreen warns on unsigned installers. Plan: code-signing (SignPath Foundation is free for open source, or Azure Trusted Signing about USD 10/month, or a normal certificate). Until then say honestly on the download page.

### 12.2 How many downloaded / how many use it / bugs
| Question | Answer | Needs consent |
|---|---|---|
| Downloads | GitHub release asset download counts (free, no tracking of people) | no |
| Active users | the daily update check (version + OS only, no id, server only counts requests, IP not stored) is the honest count; an extra anonymous usage ping with a random install id is a second, separate opt-in | update check: disclosed; usage ping: opt-in |
| Bugs | "Send report" button that shows the exact text first (like Copy report, secrets and file paths removed) and posts to a private form / GitHub issue; optional crash reporting (Sentry free tier, scrubbed) only if the user ticks it | opt-in, preview |
| Owner dashboard | a small Cloudflare Worker + D1 table (free tier): counts per version/OS per day, report inbox. Later a proper admin page. | - |

### 12.3 Updates and fixes
- `latest.json` next to releases: version, release date, notes, installer url, sha256, minimum version, channel, optional notice text.
- App checks at start and every 24 h (can be switched off), shows "Update available: what's new", user presses Update. Download -> verify sha256 AND an ed25519 signature (public key built into the app) -> run installer -> restart. Keep previous installer for rollback.
- Channels: stable and beta. A bad release is withdrawn by editing latest.json (the app then offers the previous version and shows a notice).
- New logo/branding ships as a normal app update (never changed remotely).
- Data format versions: `store` keeps a schema number so an update can migrate settings and server records safely, with an automatic backup before migration.
- Support: a Help page with version, "Copy report", link to issues, Discord/email.

## 13. Privacy, consent, legal (plan only; not legal advice, get a lawyer to review before launch)

### 13.1 What data exists and where it goes
| Data | Stays on PC? | Leaves PC to | Why | Consent plan |
|---|---|---|---|---|
| Worlds, server files, backups, settings | yes | nobody | the product | none needed |
| Player names/UUIDs/IPs (logs, whitelist, ops) | yes | nobody | shown in panel | none |
| Player heads | request leaves | minotar.net / mc-heads.net get the player NAME | pictures | switch in Privacy page, asked at first run (default on after notice; off = pixel faces) |
| playit secret key | yes (settings.json, plain text today) | used only against playit.gg | tunnel | encrypt with Windows DPAPI / Credential Manager (todo) |
| playit.gg traffic and account | no | playit.gg (their policy applies) | public address | shown before linking: "playit.gg is a separate service, you sign in there" |
| Discord webhook link and messages | link on PC | Discord: server events, player names | notices | user types the link; off by default |
| Downloads (server jar, Java, mods, playit) | no | Mojang, PaperMC, Purpur, Fabric, Adoptium, Modrinth, GitHub see the PC's IP | needed to work | one line in first-run text |
| Update check | no | our release host: version and OS | updates | switch, on by default, disclosed |
| Usage ping, crash/bug reports | no | our collector | improve app | opt-in, default OFF, preview of exact data |

### 13.2 Consent and controls in the app
1. First-run screen: what the app does, what leaves the PC (the table above in plain words), switches (update check, heads, usage ping, crash reports), links to Privacy Policy and Terms. Nothing optional is sent before the person answers.
2. Privacy page in the app: live list of "what this app sends", every switch, "Export my data" (zip of settings) and "Delete everything" (data folder and tunnel unlink).
3. Minecraft EULA: already asked per server (checkbox). Add: app is not made by or affiliated with Mojang or Microsoft; Minecraft is their trademark; no Mojang assets inside (icons are drawn in code).
4. Children: Minecraft is played by minors. No accounts, no ads, usage ping off by default, no data about players ever sent to us.

### 13.3 Documents to prepare
Privacy Policy, Terms of Use / licence of the software, Third-party notices (starlette, uvicorn, psutil, requests, playit agent, Java runtime licences; check each licence text), Minecraft/Mojang disclaimer, contact and grievance email. Law to check: India DPDP Act 2023 (consent notice, purpose, withdraw consent, grievance contact), GDPR for EU users, children's rules (COPPA/UK code) if telemetry exists.

### 13.4 Security review (done on current code, items to do)
Checked OK: server listens on 127.0.0.1 only; Host check against DNS rebinding; writes need custom header (other websites cannot send it); folder paths built in backend only; file API stays inside the server folder; zip restore and Java zip checked for unsafe paths; mod/jar downloads only from the Modrinth CDN with checksum; secrets and webhook are never sent back to the page; reports redact keys.
To do before release: per-install random API token instead of the fixed header value (stops other programs on a shared PC); encrypt playit secret at rest; sign installer and updates; pin and audit dependencies (pip-audit) in CI; warn when a public server has online-mode off or no whitelist; log nothing with secrets; add a security.txt / contact for reports.
- R7 bug: settings saved while the server runs (online-mode, white-list) flipped back. Fix: panel remembers props saved while running (meta.pending_props), puts them back after the server process exits and before the next start; install no longer overwrites props or server edits made during install. Test added in test_manager.py.
- R8: Automation Discord card has a real "Remove link" button (confirm, no Save needed); old checkbox removed. Backend clear path verified with the real API.
- R9: Servers page showed the word null when no server existed (replaceChildren got null). Fixed.
- R9b: Servers page empty state card ('No servers yet' + Create your first server).
- R9c: static files sent with Cache-Control: no-cache so updates never show stale screens (user still saw 'null' after the fix: old files or stale cache).
- R9d: Servers page: top New server button hidden while no servers (empty card has the only button).

## 14. Windows software plan (v0.1.0, plan only, waits for the user's "Go")

Facts: name Zighost (placeholder, will change), version 0.1.0, publisher shubverser, publisher name Shubham Keshri. Windows only.

### 14.1 Decisions
- One brand file `backend/brand.py` (+ `frontend/brand.js`, `assets/brand/`) holds NAME, VERSION, PUBLISHER "shubverser", PUBLISHER_NAME "Shubham Keshri", URLs, contact. Everything (window title, tray, installer, exe properties, policy text, About, user agent, Discord messages) reads from it. Renaming later = edit this file + replace the icon + rebuild.
- Rename-proof keys that never change: installer AppId (a fixed GUID, so upgrades and uninstall keep working), data folder key `zighost` inside `%APPDATA%` (display name may change, data never moves), old tunnel prefix still read.
- Packaging: PyInstaller one-folder build (not one-file: starts faster, fewer antivirus false alarms). Python and all libraries inside, nothing for the user to install. Frontend inside the package.
- Window: native window (pywebview on Edge WebView2, which is part of Windows 11 and updated Windows 10; installer checks and installs it if missing). If it cannot start, fall back to the default browser. Panel picks a free local port itself (no fixed 8765 clash) and allows only one running copy.
- Installer: Inno Setup, per-user (no admin rights), `%LOCALAPPDATA%\Programs\<Name>`; Start menu shortcut, optional desktop shortcut, optional "start with Windows"; shows Terms and links Privacy Policy; upgrade over old version keeps data; closes the running app first; uninstaller asks "also delete my servers and data?" (default: keep). Output `<Name>-Setup-0.1.0.exe`, plus SHA-256 file.
- Build: cannot be built in the Linux sandbox. `tools/build_windows.py` (runs on the user's PC) and a GitHub Actions workflow (windows-latest runner builds on a version tag) produce the installer. The user tests the real .exe and sends reports.

### 14.2 Optimised for Windows
- No console windows (launcher is a windowed exe, child processes hidden - already done for Java).
- Tray icon: Open, server status, Stop all and quit. Closing the window keeps servers running; Quit stops Minecraft safely (world saved) first.
- Keep servers fast: switch off Windows power throttling (EcoQoS) for panel and Java, optional "keep PC awake while a server runs", Java flags tuned from RAM (already), Java and playit downloaded per user into the data folder.
- Windows toast notices (server online, crashed, player joined) in addition to Discord.
- Optional start with Windows (HKCU Run key, never admin). Follows system dark/light theme. Short data paths (long-path safe). Firewall: no automatic rules (needs admin); show one clear help line if Windows asks for Java access.
- Secrets (playit key, Discord link) encrypted with Windows DPAPI (current user only).

### 14.3 Privacy and consent inside the app
- First run, before anything else: Welcome, "Your privacy" (plain list of what leaves the PC, with switches: update check, player heads, anonymous usage count, crash reports), Terms + Minecraft EULA / not-affiliated notice, Accept. Choice stored with policy version and time; asked again only when the policy changes. Defaults: update check on (disclosed, no id), heads on after notice, usage count off, crash reports off.
- Panel settings > Privacy page: live list of what is sent, all switches, Export my data, Delete all my data and unlink playit, links to documents.
- Documents shipped inside the app (work offline) and hosted on a page: Privacy Policy, Terms of Use, Third-party licences, Minecraft/Mojang disclaimer. Data controller: Shubham Keshri (shubverser). Written to DPDP Act 2023 (India) and GDPR style; lawyer review before public launch. Children: no accounts, no ads, nothing about players ever sent.

### 14.4 Owner side: downloads, users, updates, bugs
- Downloads: GitHub Releases counts.
- Active users: the daily update check goes to a small Cloudflare Worker that only counts (day, version, Windows version); no IP and no id stored. Opt-in usage ping with random install id for unique users and retention.
- Private owner dashboard (password protected Worker page): downloads, daily active, version split, bug reports.
- Updates: signed `latest.json` (version, notes, installer url, sha256, minimum version, notice). App checks at start and every 24 h, shows "Update available", asks before closing running servers, downloads, verifies sha256 and the manifest signature (public key built in), runs the installer silently, relaunches. Bad release can be withdrawn from the manifest.
- Bugs: "Send report" shows the exact text first (secrets and user name removed), goes to the Worker inbox; crash log is kept locally and offered next start. Fallback: Copy report + issue link.

### 14.5 Stages (each: code, tests, saved, log line, then next)
- W0 Foundation: brand files, placeholder icon, data folder, frozen-app paths, free port, single instance, log file, graceful shutdown.
- W1 Windows runtime: launcher, WebView2 window + fallback, tray, safe quit, autostart, keep-awake, EcoQoS, toasts, DPAPI.
- W2 Privacy and consent: first-run flow, consent store, Privacy page, documents, export and delete data, About and licences.
- W3 Updates, stats, reports: manifest, update client, signing keys, Worker + dashboard, report sender.
- W4 Build and installer: PyInstaller spec, Inno Setup script, build script, GitHub Actions, checksum and manifest generator.
- W5 Release checks: test on clean Windows (Windows Sandbox), upgrade 0.1.0 to 0.1.1, uninstall, antivirus scan, SmartScreen and code signing decision.

### 14.6 Limits to be honest about
Windows code (tray, WebView2, DPAPI, installer) can only be run on Windows; it is written carefully and logic-tested here, then verified on the user's PC. Unsigned installers show a SmartScreen warning ("Unknown publisher") until signed or reputation builds.

### 14.7 Needed from the user
Contact email for privacy and support; GitHub account and repo choice (source private, releases public); OK to use a free Cloudflare account for stats and reports; sign the installer now or later; window mode OK (native window); English only for 0.1.0.

### 14.8 Answers from the user (2026-11-12)
Work step by step, one stage at a time (W0 first, wait for "Go"). Stats: free options only (Cloudflare free). English only. Signing: ask the user again at the very end (W5). GitHub account: https://github.com/Shubhamkeshri433 (no repo yet; create when W4 starts). Contact email: not decided yet, recommended a new dedicated email (needed at W2).
- Logo chosen direction: dark tile + green pixel ghost (placeholder for Zighost). Saved in assets/brand/ (svg + PNG 16 to 1024, transparent corners). W0 turns it into .ico. Wordmark lockups stay in the design canvas (font needs Google Fonts).
- W0 done (2026-11-13): backend/brand.py (name Zighost, 0.1.0, shubverser, Shubham Keshri, DATA_KEY, APP_ID) + /brand.js; backend/paths.py (packaged vs source paths, data dir: env, %APPDATA%\zighost when packaged, ./data in source checkout); backend/logsetup.py (rotating log, safe without a console, excepthooks); backend/instance.py (one running copy via instance file + /api/ping + Windows mutex, free port search); run.py rewritten (second start opens the running copy, busy port moves to next, safe shutdown on Ctrl+Break/close/logoff); ghost logo in sidebar, favicon, assets/brand/zighost.ico (tools/make_icons.py); tunnel names use the app name and still recognise "MC Panel "; stale frontend/app.js removed. Tests: tests/test_brand_runtime.py (9) + all 7 suites pass; real run checked (second copy, busy port, clean stop). Not verifiable here: the Windows mutex and console-close handler (written for Windows, need the user's PC).

- 2026-11-13 W1 (Windows runtime) done in code: pywebview window + pystray tray (hide to tray, safe quit), keep-awake, EcoQoS off for Java, Start with Windows (HKCU Run), DPAPI-sealed secrets, tray notices, Windows card on Panel settings, requirements (win32 markers), start-window.bat, tests/test_windows.py (12). Windows-only parts (mutex, tray, WebView2, DPAPI, autostart, keep-awake) still need a test on the user's PC.

- 2026-11-13 Round 3 (user list): splash window + native window starts maximized (Shell._boot, SPLASH); Support button in the top bar (right) with email zighost.support@gmail.com, scrubbed support report (copy only), logs folder; privacy policy (frontend/policy.js, POLICY_VERSION in brand.py) with first-run consent screen (accept required, player heads optional and off), then "Get ready" step that pre-downloads Java 21 and the playit helper (both already auto-download on demand); Privacy card in Panel settings; heads proxy returns 404 until consented; backend/consent.py, backend/support.py, tests/test_privacy.py. WebView2 runtime and other installs are for the installer (W4). Not yet tested on Windows: splash, maximized start.

- 2026-11-13 W4 files written (untested on Windows): zighost.spec (reads brand, exe version info), installer/zighost.iss (per-user, WebView2 check and download, uninstall asks about data), tools/build_windows.py (PyInstaller, Inno, portable zip, SHA256SUMS), .github/workflows/build.yml (tag v* builds a draft Release), .gitignore, README.md. Repo: github.com/Shubhamkeshri433/Zighost (Claude has no push access; user uploads). Open: private repo releases are not public, so choose a public repo or a separate public releases repo before W3 updates.
