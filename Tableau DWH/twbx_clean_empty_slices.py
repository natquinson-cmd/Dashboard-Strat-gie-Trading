"""Remove now-empty <slices> blocks left over after removing all their <column> children."""
import zipfile, shutil, re
from pathlib import Path

TWBX_PATH = Path(r"C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse.twbx")
WORK_DIR = Path(r"C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_empty_slices")

if WORK_DIR.exists():
    shutil.rmtree(WORK_DIR)
WORK_DIR.mkdir()
with zipfile.ZipFile(TWBX_PATH, 'r') as z:
    z.extractall(WORK_DIR)
twb_file = next(WORK_DIR.glob("*.twb"))
content = twb_file.read_text(encoding='utf-8')
orig_len = len(content)

# Match <slices> ... </slices> blocks where the content is only whitespace
empty_slices = r"\s*<slices>\s*</slices>\r?\n"
n = len(re.findall(empty_slices, content))
content = re.sub(empty_slices, "\n", content)
print(f"Removed {n} empty <slices> blocks")

print(f"Length: {orig_len} -> {len(content)} (delta: {len(content)-orig_len})")
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
