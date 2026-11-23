"""The update helper must run hidden: DETACHED_PROCESS cancels CREATE_NO_WINDOW and every command in apply.cmd opened a console."""
import re, sys
from pathlib import Path
src = (Path(__file__).resolve().parent.parent / "backend" / "updates.py").read_text(encoding="utf-8")
assert "DETACHED" not in src, "do not use DETACHED_PROCESS for the update helper"
m = re.search(r"Popen\(\[\"cmd\.exe\".*?creationflags=([^,]+),", src, re.S)
assert m and "NOWINDOW" in m.group(1), m and m.group(1)
assert "NEWGROUP = 0x00000200" in src
print("update flags ok")
