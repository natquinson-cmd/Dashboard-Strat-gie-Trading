"""Add missing status values to the Statut reporting filter on Statut (Reporting) - Autres worksheet."""
import zipfile, shutil, re
from pathlib import Path

TWBX_PATH = Path(r"C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse New.twbx")
WORK_DIR = Path(r"C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_filter")

if WORK_DIR.exists():
    shutil.rmtree(WORK_DIR)
WORK_DIR.mkdir()
with zipfile.ZipFile(TWBX_PATH, 'r') as z:
    z.extractall(WORK_DIR)
twb_file = next(WORK_DIR.glob("*.twb"))
content = twb_file.read_text(encoding='utf-8')
orig_len = len(content)

# Inside the Statut (Reporting) - Autres worksheet, find the Statut reporting filter
# and add the missing members.
def update_filter(m):
    block = m.group(0)
    # Add missing members right before </groupfilter> (the inner one)
    missing = (
        '              <groupfilter function=\'member\' level=\'[none:Statut reporting:nk]\' member=\'&quot;En cours&quot;\' />\n'
        '              <groupfilter function=\'member\' level=\'[none:Statut reporting:nk]\' member=\'&quot;Analyse en cours&quot;\' />\n'
        '              <groupfilter function=\'member\' level=\'[none:Statut reporting:nk]\' member=\'&quot;Pr\u00eat pour r\u00e9alisation&quot;\' />\n'
    )
    # Insert before the closing </groupfilter>
    closing = '            </groupfilter>'
    return block.replace(closing, missing + closing, 1)

# Find the Statut (Reporting) - Autres worksheet and update only its filter
ws_pat = r"(<worksheet name='Statut \(Reporting\) - Autres'>.*?</worksheet>)"
def update_worksheet(m):
    ws = m.group(0)
    return re.sub(
        r"<filter class='categorical' column='\[[^]]+\]\.\[none:Statut reporting:nk\]'>.*?</filter>",
        update_filter,
        ws,
        flags=re.DOTALL
    )

content_new = re.sub(ws_pat, update_worksheet, content, flags=re.DOTALL)

if content_new == content:
    print("WARNING: No changes made")
else:
    print(f"Length: {orig_len} -> {len(content_new)} (delta: {len(content_new)-orig_len})")
    content = content_new

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
