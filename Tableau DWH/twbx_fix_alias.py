"""
Fix: change relation name from 'sqlproxy' to 'Extract' and rename all
[sqlproxy].[col] references to [Extract].[col].

Tableau doesn't honor relation aliases for hyper connections — the cols-map
prefix must match the relation 'name' attribute exactly.
"""
import zipfile, shutil, re
from pathlib import Path

TWBX_PATH = Path(r"C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse.twbx")
WORK_DIR = Path(r"C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_fix_alias")

if WORK_DIR.exists():
    shutil.rmtree(WORK_DIR)
WORK_DIR.mkdir()
with zipfile.ZipFile(TWBX_PATH, 'r') as z:
    z.extractall(WORK_DIR)
twb_file = next(WORK_DIR.glob("*.twb"))
content = twb_file.read_text(encoding='utf-8')
orig_len = len(content)

# 1. Change relation name from 'sqlproxy' to 'Extract'
old_rel = "<relation connection='hyper.epfl_perimetre_migration' name='sqlproxy' table='[Extract].[Extract]' type='table' />"
new_rel = "<relation connection='hyper.epfl_perimetre_migration' name='Extract' table='[Extract].[Extract]' type='table' />"
n_rel = content.count(old_rel)
print(f"Updating {n_rel} <relation> tags (sqlproxy alias -> Extract)")
content = content.replace(old_rel, new_rel)

# 2. Rename all [sqlproxy].[col] -> [Extract].[col] in cols map
old_prefix = "[sqlproxy]."
new_prefix = "[Extract]."
n_map = content.count(old_prefix)
print(f"Renaming {n_map} [sqlproxy].[...] references to [Extract].[...]")
content = content.replace(old_prefix, new_prefix)

# Save and validate
twb_file.write_text(content, encoding='utf-8')
print(f"\nNew length: {len(content)} (delta: {len(content)-orig_len})")

import xml.etree.ElementTree as ET
try:
    ET.parse(twb_file)
    print("XML: VALID")
except ET.ParseError as e:
    print(f"XML PARSE ERROR: {e}")
    raise SystemExit(1)

# Repackage
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
