"""Remove orphan column declarations referencing [Valeurs du champ de tableau croisé dynamique 1]."""
import zipfile, shutil, re
from pathlib import Path

TWBX_PATH = Path(r"C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse New.twbx")
WORK_DIR = Path(r"C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_rm_orphan")

if WORK_DIR.exists():
    shutil.rmtree(WORK_DIR)
WORK_DIR.mkdir()
with zipfile.ZipFile(TWBX_PATH, 'r') as z:
    z.extractall(WORK_DIR)
twb_file = next(WORK_DIR.glob("*.twb"))
content = twb_file.read_text(encoding='utf-8')
orig_len = len(content)

# Pattern: <column ... name='[Valeurs du champ de tableau croisé dynamique 1]' ... />
pat = r"\s*<column [^>]*name='\[Valeurs du champ de tableau crois\u00e9 dynamique 1\]'[^/]*/>\r?\n"
n = len(re.findall(pat, content))
content = re.sub(pat, "\n", content)
print(f"Removed {n} orphan <column> declarations")

# Also remove any <column-instance ... [Valeurs ... 1]>
pat2 = r"\s*<column-instance [^>]*column='\[Valeurs du champ de tableau crois\u00e9 dynamique 1\]'[^/]*/>\r?\n"
n2 = len(re.findall(pat2, content))
content = re.sub(pat2, "\n", content)
print(f"Removed {n2} orphan <column-instance> entries")

# Show any remaining references for sanity
remaining = content.count("Valeurs du champ de tableau crois\u00e9 dynamique 1")
print(f"Remaining 'Valeurs ... 1' references: {remaining}")

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
