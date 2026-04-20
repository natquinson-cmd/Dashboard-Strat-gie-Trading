"""Revert: restore the native color legend zone for Statut (Reporting) - Autres
and remove the embedded Legende_Statut.png from the package."""
import zipfile, shutil
from pathlib import Path

TWBX_PATH = Path(r"C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse New.twbx")
WORK_DIR = Path(r"C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_revert_legend")

if WORK_DIR.exists():
    shutil.rmtree(WORK_DIR)
WORK_DIR.mkdir()
with zipfile.ZipFile(TWBX_PATH, 'r') as z:
    z.extractall(WORK_DIR)

# Remove the embedded PNG
img = WORK_DIR / "Image" / "Legende_Statut.png"
if img.exists():
    img.unlink()
    print(f"Removed: {img}")

twb_file = next(WORK_DIR.glob("*.twb"))
content = twb_file.read_text(encoding='utf-8')

old_bitmap = "<zone h='14182' id='1625' is-centered='0' is-scaled='1' param='Image/Legende_Statut.png' type-v2='bitmap' w='12111' x='86222' y='50455' />"
new_zone = "<zone h='14182' id='1625' leg-item-layout='vert' name='Statut (Reporting) - Autres' pane-specification-id='0' param='[sqlproxy.15pbedn0q6uqg31a9u9hr1vudrnj].[none:Statut reporting:nk]' show-title='false' type-v2='color' w='12111' x='86222' y='50455' />"
n = content.count(old_bitmap)
content = content.replace(old_bitmap, new_zone)
print(f"Restored {n} legend zone(s)")

twb_file.write_text(content, encoding='utf-8')

import xml.etree.ElementTree as ET
ET.parse(twb_file)
print("XML: VALID")

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
