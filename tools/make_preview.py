"""Build frontend/preview.html: one file with CSS + JS inlined and demo mode forced on.
Open it by double-click to see the dashboard without the backend. Do not edit preview.html by hand."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend import brand

FE = Path(__file__).resolve().parent.parent / "frontend"
html = (FE / "index.html").read_text(encoding="utf-8").replace("__NAME__", brand.NAME)
html = html.replace('<script src="/brand.js"></script>', f"<script>\n{brand.js()}</script>")
css = (FE / "style.css").read_text(encoding="utf-8")
html = html.replace('<link rel="stylesheet" href="/static/style.css">', f"<style>\n{css}\n</style>")
order = [m for m in __import__("re").findall(r'src="/static/([^"]+)"', html)]
import re
for m in re.findall(r'<script src="/static/([^"]+)"></script>', html):
    js = (FE / m).read_text(encoding="utf-8")
    pre = "window.MCP_FORCE_DEMO = true;\n" if m == "demo.js" else ""
    html = html.replace(f'<script src="/static/{m}"></script>', f"<script>\n{pre}{js}\n</script>")
(FE / "preview.html").write_text(html, encoding="utf-8")
print("wrote", FE / "preview.html")
