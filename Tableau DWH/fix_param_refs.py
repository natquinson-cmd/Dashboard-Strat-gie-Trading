"""Fix parameter references in calculated fields: [Parameters].[X] -> [X]."""
import zipfile, shutil
from pathlib import Path

TWBX = Path(r"C:\Users\quinson\Desktop\Claude\Tableau DWH\Dasboard suivi projet DataWarehouse.twbx")
WORK = Path(r"C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_fix_work")

if WORK.exists(): shutil.rmtree(WORK)
WORK.mkdir()
with zipfile.ZipFile(TWBX) as z: z.extractall(WORK)
twb = next(WORK.glob("*.twb"))
content = twb.read_text(encoding='utf-8')

# Remove [Parameters]. prefix (parameters are global)
before_count = content.count('[Parameters].')
content = content.replace('[Parameters].[Param', '[Param')
after_count = content.count('[Parameters].')
print(f"Replaced {before_count - after_count} [Parameters].[Param references -> [Param")

twb.write_text(content, encoding='utf-8')

import xml.etree.ElementTree as ET
try:
    ET.parse(twb)
    print("XML: VALID")
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
