"""
Aggressive cleanup of all orphaned pivot column references in the migrated twbx.

We remove ALL XML elements that reference [Valeurs du champ de tableau croisé dynamique]
or [Noms des champs de tableau croisé dynamique], including:
- <column-instance column='[Valeurs/Noms ...]' .../>
- <column ... name='[Valeurs/Noms ...]' /> (worksheet aliases)
- <filter ... column='[...].[none:Valeurs/Noms ...:nk]'>...</filter>
- <column>[...].[none:Valeurs/Noms ...:nk]</column> (in slices)
- <_.fcp...format ... field='[...].[none:Valeurs/Noms ...:nk]' .../> (font formatting)

The Intervenant filter on the Burn-up worksheet will be lost. User can re-add manually
in Tableau Desktop after migration if needed.
"""
import zipfile, shutil, re
from pathlib import Path

TWBX_PATH = Path(r"C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse.twbx")
WORK_DIR = Path(r"C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_cleanup")

if WORK_DIR.exists():
    shutil.rmtree(WORK_DIR)
WORK_DIR.mkdir()
with zipfile.ZipFile(TWBX_PATH, 'r') as z:
    z.extractall(WORK_DIR)
twb_file = next(WORK_DIR.glob("*.twb"))

content = twb_file.read_text(encoding='utf-8')
orig_len = len(content)

# Helper: count occurrences of a substring
def show(label, sub):
    print(f"  {label}: {content.count(sub)}")

print("=== BEFORE cleanup ===")
show("'Valeurs du champ'", "Valeurs du champ de tableau")
show("'Noms des champs'", "Noms des champs de tableau")

# 1. Remove <column-instance ... [Valeurs/Noms ...] .../> lines
ci_pattern = r"\s*<column-instance column='\[(?:Valeurs du champ|Noms des champs) de tableau crois\u00e9 dynamique\]'[^/]*/>\r?\n"
n_ci = len(re.findall(ci_pattern, content))
content = re.sub(ci_pattern, "\n", content)
print(f"Removed {n_ci} <column-instance> entries")

# 2. Remove worksheet-level <column ... name='[Valeurs/Noms ...]' .../> aliases
col_alias_pattern = r"\s*<column [^>]*name='\[(?:Valeurs du champ|Noms des champs) de tableau crois\u00e9 dynamique\]'[^/]*/>\r?\n"
n_ca = len(re.findall(col_alias_pattern, content))
content = re.sub(col_alias_pattern, "\n", content)
print(f"Removed {n_ca} worksheet <column> aliases")

# 3. Remove <filter ...>...</filter> blocks referencing the pivot col
# Pattern: <filter ... column='[sqlproxy...].[none:Valeurs/Noms ...:nk]'>(content)</filter>
filter_pattern = r"\s*<filter [^>]*column='\[sqlproxy[^]]*\]\.\[none:(?:Valeurs du champ|Noms des champs) de tableau crois\u00e9 dynamique:nk\]'>.*?</filter>\r?\n"
n_f = len(re.findall(filter_pattern, content, re.DOTALL))
content = re.sub(filter_pattern, "\n", content, flags=re.DOTALL)
print(f"Removed {n_f} <filter> blocks")

# 4. Remove <column>[...].[none:Valeurs/Noms ...:nk]</column> entries (in slices)
slice_pattern = r"\s*<column>\[sqlproxy[^]]*\]\.\[none:(?:Valeurs du champ|Noms des champs) de tableau crois\u00e9 dynamique:nk\]</column>\r?\n"
n_s = len(re.findall(slice_pattern, content))
content = re.sub(slice_pattern, "\n", content)
print(f"Removed {n_s} <column> slice entries")

# 5. Remove individual format references (font sizes, etc.)
fmt_pattern = r"\s*<format [^/]*field='\[sqlproxy[^]]*\]\.\[none:(?:Valeurs du champ|Noms des champs) de tableau crois\u00e9 dynamique:nk\]'[^/]*/>\r?\n"
n_fmt = len(re.findall(fmt_pattern, content))
content = re.sub(fmt_pattern, "\n", content)
print(f"Removed {n_fmt} <format> field-specific entries")

# 6. Remove fcp wrapper blocks (IndividualControlFormatting that wrap a format)
# These are like: <_.fcp.IndividualControlFormatting.true...><format ... /></_.fcp.IndividualControlFormatting.true...>
fcp_pattern = r"\s*<_\.fcp\.[^>]*>\s*<format [^/]*field='\[sqlproxy[^]]*\]\.\[none:(?:Valeurs du champ|Noms des champs) de tableau crois\u00e9 dynamique:nk\]'[^/]*/>\s*</_\.fcp\.[^>]*>\r?\n"
n_fcp = len(re.findall(fcp_pattern, content, re.DOTALL))
content = re.sub(fcp_pattern, "\n", content, flags=re.DOTALL)
print(f"Removed {n_fcp} fcp wrapper blocks")

print()
print("=== AFTER cleanup ===")
show("'Valeurs du champ'", "Valeurs du champ de tableau")
show("'Noms des champs'", "Noms des champs de tableau")
print(f"Length: {orig_len} -> {len(content)} (delta: {len(content)-orig_len})")

twb_file.write_text(content, encoding='utf-8')

# Validate XML
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
