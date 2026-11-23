import json, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend import store, recover


def main():
    tmp = Path(tempfile.mkdtemp())
    store.DATA = tmp; store.SERVERS_DIR = tmp / "servers"; recover.store = store
    store.SERVERS_DIR.mkdir(parents=True)
    import backend.store as st
    st.DATA = tmp
    d = store.SERVERS_DIR / "84fa2a62"; d.mkdir()
    (d / "server.jar").write_bytes(b"x"); (d / ".paper").mkdir()
    (d / "server.properties").write_text("motd=Hello\nserver-port=25570\n")
    (d / "eula.txt").write_text("eula=true\n")
    (d / "version_history.json").write_text('{"currentVersion":"1.21.4-1-abc (MC: 1.21.4)"}')
    (store.SERVERS_DIR / "notanid").mkdir()
    (store.SERVERS_DIR / "deadbeef").mkdir()          # empty -> ignored
    saved = []
    store.save_server = lambda m: saved.append(m)
    store.list_servers = lambda: []
    out = recover.recover()
    assert len(out) == 1, out
    m = out[0]
    assert (m["id"], m["type"], m["version"], m["port"], m["eula"], m["installed"]) == ("84fa2a62", "paper", "1.21.4", 25570, True, True), m
    assert (d / "server.jar").exists() and saved == out
    store.list_servers = lambda: [{"id": "84fa2a62"}]
    assert recover.recover() == []
    print("recover ok")

main()
