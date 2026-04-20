"""Unify the fonts inside Glossaire customized-tooltips to the Tableau font family."""
import zipfile, shutil, re
from pathlib import Path

TWBX_PATH = Path(r"C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse New.twbx")
WORK_DIR = Path(r"C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_fonts")

if WORK_DIR.exists():
    shutil.rmtree(WORK_DIR)
WORK_DIR.mkdir()
with zipfile.ZipFile(TWBX_PATH, 'r') as z:
    z.extractall(WORK_DIR)
twb_file = next(WORK_DIR.glob("*.twb"))
content = twb_file.read_text(encoding='utf-8')
orig_len = len(content)

# Update fontname inside Glossaire customized-tooltips only
def update_tooltip_block(m):
    block = m.group(0)
    # Body text (Benton Sans Book / Google Sans Text) -> Tableau Book
    block = block.replace("fontname='Benton Sans Book'", "fontname='Tableau Book'")
    block = block.replace("fontname='Google Sans Text'", "fontname='Tableau Book'")
    # Bold headers (Google Sans, usually with bold='true') -> Tableau Bold
    block = block.replace("fontname='Google Sans'", "fontname='Tableau Bold'")
    return block

# Process each Glossaire customized-tooltip
ws_pattern = r"(<worksheet name='Glossaire[^']*'>.*?</worksheet>)"
n_ws = 0
def process_worksheet(m):
    nonlocal_n = m.group(0)
    return re.sub(
        r"<customized-tooltip>.*?</customized-tooltip>",
        update_tooltip_block,
        nonlocal_n,
        flags=re.DOTALL
    )

# Use a simpler approach: find each tooltip that's preceded by a Glossaire worksheet
# Process the whole content but only inside Glossaire worksheets
def process_glossaire_ws(m):
    return re.sub(
        r"<customized-tooltip>.*?</customized-tooltip>",
        update_tooltip_block,
        m.group(0),
        flags=re.DOTALL
    )

content_new = re.sub(ws_pattern, process_glossaire_ws, content, flags=re.DOTALL)
n_changed = (
    content.count("Benton Sans Book") - content_new.count("Benton Sans Book") +
    content.count("Google Sans Text") - content_new.count("Google Sans Text") +
    content.count("'Google Sans'") - content_new.count("'Google Sans'")
)
print(f"Total font references changed: {n_changed}")

twb_file.write_text(content_new, encoding='utf-8')
print(f"Length: {orig_len} -> {len(content_new)}")

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
