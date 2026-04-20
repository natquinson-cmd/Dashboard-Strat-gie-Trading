"""
Rename the datasource from 'sqlproxy.<id>' to 'federated.<id>' so Tableau
treats it as a local datasource (not a published one).

This also renames all references in worksheets, parameters, etc.
"""
import zipfile, shutil
from pathlib import Path

TWBX_PATH = Path(r"C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse.twbx")
WORK_DIR = Path(r"C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_rename")

OLD_NAME = "sqlproxy.1yiv2z00jebo4919a1ffq12saj0f"
NEW_NAME = "federated.1yiv2z00jebo4919a1ffq12saj0f"

if WORK_DIR.exists():
    shutil.rmtree(WORK_DIR)
WORK_DIR.mkdir()
with zipfile.ZipFile(TWBX_PATH, 'r') as z:
    z.extractall(WORK_DIR)
twb_file = next(WORK_DIR.glob("*.twb"))
content = twb_file.read_text(encoding='utf-8')
orig_len = len(content)

n = content.count(OLD_NAME)
print(f"Renaming {n} occurrences of '{OLD_NAME}' to '{NEW_NAME}'")
content = content.replace(OLD_NAME, NEW_NAME)

twb_file.write_text(content, encoding='utf-8')
print(f"New length: {len(content)} (delta: {len(content)-orig_len})")

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
