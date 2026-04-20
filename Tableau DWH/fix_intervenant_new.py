"""
Fix Intervenant 1/2 formulas in the New twbx: replace
[Valeurs du champ de tableau croisé dynamique 1] (orphan alias from Replace Data Source)
with [Valeurs du champ de tableau croisé dynamique] (the real column).
"""
import zipfile, shutil
from pathlib import Path

TWBX_PATH = Path(r"C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse New.twbx")
WORK_DIR = Path(r"C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_fix_int")

if WORK_DIR.exists():
    shutil.rmtree(WORK_DIR)
WORK_DIR.mkdir()
with zipfile.ZipFile(TWBX_PATH, 'r') as z:
    z.extractall(WORK_DIR)
twb_file = next(WORK_DIR.glob("*.twb"))
content = twb_file.read_text(encoding='utf-8')
orig_len = len(content)

# Fix the formulas: use the column without " 1" suffix
old_ref = "[Valeurs du champ de tableau crois\u00e9 dynamique 1]"
new_ref = "[Valeurs du champ de tableau crois\u00e9 dynamique]"

# Count BEFORE
n_old = content.count(old_ref)
print(f"Found {n_old} references to {old_ref!r}")

# Replace - but ONLY in formulas, not in column declarations
# A safe way: replace only inside formula='...' attributes
import re
def fix_formula(m):
    return m.group(0).replace(old_ref, new_ref)

content = re.sub(r"formula='[^']*'", fix_formula, content)

n_after = content.count(old_ref)
print(f"After fix in formulas: {n_after} references to '{old_ref}' remain (in column declarations)")

# Save
twb_file.write_text(content, encoding='utf-8')
print(f"Length: {orig_len} -> {len(content)}")

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
