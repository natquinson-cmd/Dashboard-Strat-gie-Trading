"""Fix KPI Capacite worksheet to use light theme (white bg, dark text) matching existing dashboard."""
import zipfile, shutil, re
from pathlib import Path

TWBX = Path(r"C:\Users\quinson\Desktop\Claude\Tableau DWH\Dasboard suivi projet DataWarehouse.twbx")
WORK = Path(r"C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_light_work")
if WORK.exists(): shutil.rmtree(WORK)
WORK.mkdir()
with zipfile.ZipFile(TWBX) as z: z.extractall(WORK)
twb = next(WORK.glob("*.twb"))
content = twb.read_text(encoding='utf-8')

# Find the KPI Capacite worksheet block
m = re.search(r"<worksheet name='KPI Capacite'>.*?</worksheet>", content, re.DOTALL)
if not m:
    print("KPI Capacite not found!"); exit(1)

# Replace bg color #0f172a (dark) -> no explicit bg (transparent) or white #ffffff
# Replace fontcolor #ffffff -> dark #1e293b
new_block = m.group(0)
new_block = new_block.replace("<format attr='background-color' value='#0f172a' />", "<format attr='background-color' value='#ffffff' />")
new_block = new_block.replace("fontcolor='#ffffff'", "fontcolor='#1e293b'")

content = content[:m.start()] + new_block + content[m.end():]
twb.write_text(content, encoding='utf-8')

import xml.etree.ElementTree as ET
try:
    ET.parse(twb); print("XML: VALID")
except ET.ParseError as e:
    print(f"XML ERROR: {e}"); exit(1)

tmp = WORK.parent / "twbx_tmp.twbx"
if tmp.exists(): tmp.unlink()
with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as z:
    for f in WORK.rglob('*'):
        if f.is_file():
            z.write(f, arcname=f.relative_to(WORK))
shutil.copy2(tmp, TWBX); tmp.unlink(); shutil.rmtree(WORK)
print(f"Written: {TWBX}")
print("Theme clair applique : fond blanc, texte fonce #1e293b")
