"""Build assets/brand/zighost.ico (16 to 256 px) from the PNG sizes. Used by the installer build and the exe."""
from pathlib import Path
from PIL import Image

B = Path(__file__).resolve().parent.parent / "assets" / "brand"
sizes = [16, 24, 32, 48, 64, 128, 256]
src = Image.open(B / "zighost-icon-1024.png").convert("RGBA")
# Resize with nearest-neighbour friendly filter for the pixel art look at tiny sizes
imgs = [src.resize((n, n), Image.LANCZOS if n >= 64 else Image.BOX) for n in sizes]
imgs[-1].save(B / "zighost.ico", sizes=[(n, n) for n in sizes], append_images=imgs[:-1])
print("wrote", B / "zighost.ico")
