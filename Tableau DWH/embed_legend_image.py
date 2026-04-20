"""Embed Legende_Statut.png into the twbx and replace the Statut (Reporting) - Autres color legend zone."""
import zipfile, shutil, re
from pathlib import Path

TWBX_PATH = Path(r"C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse New.twbx")
PNG_SRC = Path(r"C:\Users\quinson\Desktop\Claude\Tableau DWH\Legende_Statut.png")
WORK_DIR = Path(r"C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_legend_img")

if WORK_DIR.exists():
    shutil.rmtree(WORK_DIR)
WORK_DIR.mkdir()
with zipfile.ZipFile(TWBX_PATH, 'r') as z:
    z.extractall(WORK_DIR)

# Copy the PNG into the package's Image folder
img_dir = WORK_DIR / "Image"
img_dir.mkdir(exist_ok=True)
target_png = img_dir / "Legende_Statut.png"
shutil.copy2(PNG_SRC, target_png)
print(f"Copied PNG to {target_png}")

# Read the .twb
twb_file = next(WORK_DIR.glob("*.twb"))
content = twb_file.read_text(encoding='utf-8')
orig_len = len(content)

# Original color legend zone (we want to replace its first occurrence on Suivi Global dashboard)
old_zone = "<zone h='14182' id='1625' leg-item-layout='vert' name='Statut (Reporting) - Autres' pane-specification-id='0' param='[sqlproxy.15pbedn0q6uqg31a9u9hr1vudrnj].[none:Statut reporting:nk]' show-title='false' type-v2='color' w='12111' x='86222' y='50455' />"
# Replace with a bitmap zone using the same coordinates
new_zone = "<zone h='14182' id='1625' is-centered='0' is-scaled='1' param='Image/Legende_Statut.png' type-v2='bitmap' w='12111' x='86222' y='50455' />"

n = content.count(old_zone)
print(f"Found {n} matching zone declarations")
content = content.replace(old_zone, new_zone, 1)  # only the first (top-level dashboard zone)

print(f"Length: {orig_len} -> {len(content)}")

twb_file.write_text(content, encoding='utf-8')

import xml.etree.ElementTree as ET
try:
    ET.parse(twb_file)
    print("XML: VALID")
except ET.ParseError as e:
    print(f"XML PARSE ERROR: {e}")
    raise SystemExit(1)

tmp_twbx = TWBX_PATH.parent / "twbx_tmp.twbx"
if tmp_twbx.exists():
    tmp_twbx.unlink()
with zipfile.ZipFile(tmp_twbx, 'w', zipfile.ZIP_DEFLATED) as z:
    for f in WORK_DIR.rglob('*'):
        if f.is_file():
            z.write(f, arcname=f.relative_to(WORK_DIR))
shutil.copy2(tmp_twbx, TWBX_PATH)
tmp_twbx.unlink()
shutil.rmtree(WORK_DIR)
print(f"Repackaged: {TWBX_PATH}")
