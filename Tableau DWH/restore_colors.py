"""Restore the original color palettes that Tableau reset during Replace Data Source."""
import zipfile, shutil, re
from pathlib import Path

TWBX_PATH = Path(r"C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse New.twbx")
WORK_DIR = Path(r"C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_colors")

if WORK_DIR.exists():
    shutil.rmtree(WORK_DIR)
WORK_DIR.mkdir()
with zipfile.ZipFile(TWBX_PATH, 'r') as z:
    z.extractall(WORK_DIR)
twb_file = next(WORK_DIR.glob("*.twb"))
content = twb_file.read_text(encoding='utf-8')
orig_len = len(content)

# ===== 1. Workload color encoding =====
# Find encoding blocks for [none:Valeurs du champ de tableau crois\u00e9 dynamique:nk]
# Replace ALL color maps inside with original values + add palette='blue_teal_10_0'

workload_orig_maps = """<map to='#2c5985'>
              <bucket>&quot;NQU&quot;</bucket>
            </map>
            <map to='#306c94'>
              <bucket>&quot;LSO&quot;</bucket>
            </map>
            <map to='#3482a4'>
              <bucket>&quot;JDF&quot;</bucket>
            </map>
            <map to='#3c97b2'>
              <bucket>&quot;FLU&quot;</bucket>
            </map>
            <map to='#57abbe'>
              <bucket>&quot;EMINEO&quot;</bucket>
            </map>
            <map to='#79bec8'>
              <bucket>&quot;EFR&quot;</bucket>
            </map>
            <map to='#99d0d0'>
              <bucket>&quot;ASA&quot;</bucket>
            </map>
            <map to='#9c755f'>
              <bucket>&quot;LRI&quot;</bucket>
            </map>
            <map to='#bce4d8'>
              <bucket>%null%</bucket>
            </map>"""

# Pattern: <encoding attr='color' field='[none:Valeurs du champ ...:nk]' type='palette'>...</encoding>
def replace_workload(m):
    header = m.group(1)
    # add palette attribute if missing
    if "palette=" not in header:
        new_header = header.replace("type='palette'", "palette='blue_teal_10_0' type='palette'")
    else:
        new_header = header
    indent = "          "
    return new_header + "\n" + indent + "  " + workload_orig_maps + "\n" + indent + "</encoding>"

workload_pattern = (
    r"(<encoding attr='color' field='\[none:Valeurs du champ de tableau crois\u00e9 dynamique:nk\][^>]*>)"
    r".*?</encoding>"
)
n_w = len(re.findall(workload_pattern, content, re.DOTALL))
print(f"Workload encoding blocks found: {n_w}")
content = re.sub(workload_pattern, replace_workload, content, flags=re.DOTALL)

# ===== 2. Statut Global (Avancement BI) =====
statut_orig_maps = """<map to='#59a14f'>
              <bucket>&quot;Termin\u00e9&quot;</bucket>
            </map>
            <map to='#989ca3'>
              <bucket>&quot;A faire&quot;</bucket>
            </map>
            <map to='#f28e2b'>
              <bucket>&quot;En cours&quot;</bucket>
            </map>"""

def replace_statut(m):
    header = m.group(1)
    indent = "          "
    return header + "\n" + indent + "  " + statut_orig_maps + "\n" + indent + "</encoding>"

statut_pattern = (
    r"(<encoding attr='color' field='\[none:Calculation_1009650768493371395:nk\][^>]*>)"
    r".*?</encoding>"
)
n_s = len(re.findall(statut_pattern, content, re.DOTALL))
print(f"Statut Global encoding blocks found: {n_s}")
content = re.sub(statut_pattern, replace_statut, content, flags=re.DOTALL)

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
