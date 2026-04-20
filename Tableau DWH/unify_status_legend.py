"""Force all status values in the color encoding for all 4 phases (Cadrage, Conception, Flux, Reporting),
so the legend always shows the complete domain even if some values are absent from current data."""
import zipfile, shutil, re
from pathlib import Path

TWBX_PATH = Path(r"C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse New.twbx")
WORK_DIR = Path(r"C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_legend")

if WORK_DIR.exists():
    shutil.rmtree(WORK_DIR)
WORK_DIR.mkdir()
with zipfile.ZipFile(TWBX_PATH, 'r') as z:
    z.extractall(WORK_DIR)
twb_file = next(WORK_DIR.glob("*.twb"))
content = twb_file.read_text(encoding='utf-8')
orig_len = len(content)

# Full mapping list (preserved order = legend order)
full_maps = """<map to='#59a14f'>
              <bucket>&quot;Termin\u00e9&quot;</bucket>
            </map>
            <map to='#f6a55c'>
              <bucket>&quot;En cours&quot;</bucket>
            </map>
            <map to='#f28e2b'>
              <bucket>&quot;Tests en cours&quot;</bucket>
            </map>
            <map to='#f1ce63'>
              <bucket>&quot;Analyse en cours&quot;</bucket>
            </map>
            <map to='#fcb46d'>
              <bucket>&quot;R\u00e9alisation en cours&quot;</bucket>
            </map>
            <map to='#ffbe7d'>
              <bucket>&quot;Pr\u00eat pour r\u00e9alisation&quot;</bucket>
            </map>
            <map to='#595959'>
              <bucket>&quot;A faire&quot;</bucket>
            </map>
            <map to='#d5d5d5'>
              <bucket>%null%</bucket>
            </map>"""

# Fields to update (the 4 statut encodings + their attr: variants)
fields = [
    "[none:Statut Cadrage conception:nk]",
    "[none:Statut Conception:nk]",
    "[none:Statut flux:nk]",
    "[none:Statut reporting:nk]",
    "[attr:Statut Cadrage conception:nk]",
    "[attr:Statut Conception:nk]",
    "[attr:Statut flux:nk]",
    "[attr:Statut reporting:nk]",
]

n_total = 0
for field in fields:
    pattern = (
        r"(<encoding attr='color' field='" + re.escape(field) + r"'[^>]*>)"
        r".*?</encoding>"
    )
    def repl(m):
        header = m.group(1)
        indent = "          "
        return header + "\n" + indent + "  " + full_maps + "\n" + indent + "</encoding>"
    new_content, n = re.subn(pattern, repl, content, flags=re.DOTALL)
    if n > 0:
        print(f"  Updated {n} encoding(s) for {field}")
        n_total += n
        content = new_content

print(f"Total encodings updated: {n_total}")
print(f"Length: {orig_len} -> {len(content)}")

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
