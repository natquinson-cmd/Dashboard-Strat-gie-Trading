"""
Migrate the twbx from a published sqlproxy datasource to a local Hyper file.

Strategy (minimal-change approach):
- Keep the datasource 'name' attribute (sqlproxy.<id>) so worksheet references stay valid.
- Keep the relation 'name' as 'sqlproxy' so all [sqlproxy].[col] cols-map references stay valid.
- Replace the inner <connection class='sqlproxy' ...> tag with a federated wrapper containing
  a named-connection that points to the .hyper file.
- Update the <relation> to: connection='hyper.<id>' name='sqlproxy' table='[Extract].[Extract]'.
- Remove <repository-location> (no longer a published datasource).
- Remove cols-map entries for the pivot columns (Noms des champs / Valeurs du champ).
- Add cols-map entries for REF BI01 and REF BI02 (which were hidden by the published pivot).
- Remove <column> definitions for the pivot column fields.
- Add <column> definitions for REF BI01 and REF BI02.
- Rewrite the Intervenant 1/2 formulas to use [REF BI01] and [REF BI02] directly.
- Apply the same changes to the embedded CDATA datasource definition (line 2424).
- Update the 4 <relation name='sqlproxy' ...> lines (in object-graphs).
"""
import zipfile
import shutil
import re
from pathlib import Path

TWBX_PATH = Path(r"C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse.twbx")
WORK_DIR = Path(r"C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_migrate")

HYPER_PATH_FWD = "//scxdata/CommunOS_BI$/C Courant/Datasources/ISCS-BI/SuiviProjetDWH/flatfiles/Perimetre_Migration.hyper"
HYPER_CONN_NAME = "hyper.epfl_perimetre_migration"  # internal connection ID, can be any unique string

# --- Extract ---
if WORK_DIR.exists():
    shutil.rmtree(WORK_DIR)
WORK_DIR.mkdir()
with zipfile.ZipFile(TWBX_PATH, 'r') as z:
    z.extractall(WORK_DIR)
twb_file = next(WORK_DIR.glob("*.twb"))
print(f"Extracted: {twb_file.name}")

# --- Read content ---
content = twb_file.read_text(encoding='utf-8')
orig_len = len(content)
print(f"Original length: {orig_len}")

# =====================================================================
# 1. Remove <repository-location> lines (2 occurrences in main + CDATA)
# =====================================================================
repo_pattern = r"\s*<repository-location derived-from='https://tableau\.epfl\.ch/datasources/Perimetre_MigrationExcel[^>]*/>\r?\n"
n_repo = len(re.findall(repo_pattern, content))
content = re.sub(repo_pattern, "\n", content)
print(f"Removed {n_repo} <repository-location> lines")

# =====================================================================
# 2. Replace <connection class='sqlproxy' ...> opening tags with federated wrapper
# =====================================================================
# The two occurrences:
#  L51: <connection channel='https' class='sqlproxy' dbname='Perimetre_MigrationExcel' directory='/dataserver' port='443' server='tableau.epfl.ch' server-oauth='' username='' workgroup-auth-mode='prompt'>
#  L2431: <connection channel='https' class='sqlproxy' dbname='Perimetre_MigrationExcel' directory='/dataserver' port='443' server='tableau.epfl.ch'>

# Build the new opening (federated wrapper + named-connection inside)
new_conn_open = (
    "<connection class='federated'>\n"
    "      <named-connections>\n"
    f"        <named-connection caption='Perimetre_Migration' name='{HYPER_CONN_NAME}'>\n"
    f"          <connection authentication='auth-none' class='hyper' dbname='{HYPER_PATH_FWD}' default-settings='yes' server='' sslmode='' username='tableau_internal_user' />\n"
    "        </named-connection>\n"
    "      </named-connections>"
)

old_conn_open_1 = "<connection channel='https' class='sqlproxy' dbname='Perimetre_MigrationExcel' directory='/dataserver' port='443' server='tableau.epfl.ch' server-oauth='' username='' workgroup-auth-mode='prompt'>"
old_conn_open_2 = "<connection channel='https' class='sqlproxy' dbname='Perimetre_MigrationExcel' directory='/dataserver' port='443' server='tableau.epfl.ch'>"

n1 = content.count(old_conn_open_1)
n2 = content.count(old_conn_open_2)
print(f"Replacing connection opening tags: variant1={n1}, variant2={n2}")
content = content.replace(old_conn_open_1, new_conn_open)
content = content.replace(old_conn_open_2, new_conn_open)

# =====================================================================
# 3. Update <relation> tags (4 occurrences) to use new connection + table
# =====================================================================
old_relation = "<relation name='sqlproxy' table='[sqlproxy]' type='table' />"
new_relation = f"<relation connection='{HYPER_CONN_NAME}' name='sqlproxy' table='[Extract].[Extract]' type='table' />"
n_rel = content.count(old_relation)
print(f"Updating {n_rel} <relation> tags")
content = content.replace(old_relation, new_relation)

# =====================================================================
# 4. Rewrite Intervenant 1 and Intervenant 2 formulas
# =====================================================================
# Old formulas (in XML attribute, with HTML entities)
old_intv1 = "{ FIXED [Nom source] : MAX(IF [Noms des champs de tableau crois\u00e9 dynamique] = &quot;Ref Bi01&quot; THEN [Valeurs du champ de tableau crois\u00e9 dynamique] END) }"
new_intv1 = "{ FIXED [Nom source] : MAX([REF BI01]) }"

old_intv2 = "{ FIXED [Nom source] : MAX(IF [Noms des champs de tableau crois\u00e9 dynamique] = &quot;Ref Bi02&quot; THEN [Valeurs du champ de tableau crois\u00e9 dynamique] END) }"
new_intv2 = "{ FIXED [Nom source] : MAX([REF BI02]) }"

n_intv1 = content.count(old_intv1)
n_intv2 = content.count(old_intv2)
print(f"Rewriting {n_intv1} Intervenant 1 formulas, {n_intv2} Intervenant 2 formulas")
content = content.replace(old_intv1, new_intv1)
content = content.replace(old_intv2, new_intv2)

# Also handle the escaped variant (in CDATA-embedded blocks, formula is escaped with \&quot;)
old_intv1_esc = "{ FIXED [Nom source] : MAX(IF [Noms des champs de tableau crois\u00e9 dynamique] = \\&quot;Ref Bi01\\&quot; THEN [Valeurs du champ de tableau crois\u00e9 dynamique] END) }"
new_intv1_esc = "{ FIXED [Nom source] : MAX([REF BI01]) }"
old_intv2_esc = "{ FIXED [Nom source] : MAX(IF [Noms des champs de tableau crois\u00e9 dynamique] = \\&quot;Ref Bi02\\&quot; THEN [Valeurs du champ de tableau crois\u00e9 dynamique] END) }"
new_intv2_esc = "{ FIXED [Nom source] : MAX([REF BI02]) }"
n_intv1e = content.count(old_intv1_esc)
n_intv2e = content.count(old_intv2_esc)
print(f"Rewriting {n_intv1e} escaped Intervenant 1 formulas, {n_intv2e} escaped Intervenant 2 formulas")
content = content.replace(old_intv1_esc, new_intv1_esc)
content = content.replace(old_intv2_esc, new_intv2_esc)

# =====================================================================
# 5. Remove pivot column entries from <cols> map
# =====================================================================
pivot_map_1 = "<map key='[Noms des champs de tableau crois\u00e9 dynamique]' value='[sqlproxy].[Noms des champs de tableau crois\u00e9 dynamique]' />"
pivot_map_2 = "<map key='[Valeurs du champ de tableau crois\u00e9 dynamique]' value='[sqlproxy].[Valeurs du champ de tableau crois\u00e9 dynamique]' />"
print(f"Removing pivot map entries: noms={content.count(pivot_map_1)}, valeurs={content.count(pivot_map_2)}")
content = re.sub(r"\s*" + re.escape(pivot_map_1) + r"\r?\n", "\n", content)
content = re.sub(r"\s*" + re.escape(pivot_map_2) + r"\r?\n", "\n", content)

# =====================================================================
# 6. Add REF BI01 and REF BI02 to <cols> map (in both datasource blocks)
# =====================================================================
ref_bi01_map = "      <map key='[REF BI01]' value='[sqlproxy].[REF BI01]' />\n"
ref_bi02_map = "      <map key='[REF BI02]' value='[sqlproxy].[REF BI02]' />\n"
# Insert them right before the closing </cols> tag — for each occurrence
content = content.replace("    </cols>", ref_bi01_map + ref_bi02_map + "    </cols>")
print("Added [REF BI01] and [REF BI02] map entries")

# =====================================================================
# 7. Remove <column> entries for the pivot columns
# =====================================================================
# These are <column ... name='[Noms des champs de tableau croisé dynamique]' ... />
# and similar for Valeurs. They're typically simple <column ... /> tags.
pivot_col_pattern_noms = r"\s*<column [^>]*name='\[Noms des champs de tableau crois\u00e9 dynamique\]'[^/]*/>\r?\n"
pivot_col_pattern_val = r"\s*<column [^>]*name='\[Valeurs du champ de tableau crois\u00e9 dynamique\]'[^/]*/>\r?\n"
n_col_noms = len(re.findall(pivot_col_pattern_noms, content))
n_col_val = len(re.findall(pivot_col_pattern_val, content))
content = re.sub(pivot_col_pattern_noms, "\n", content)
content = re.sub(pivot_col_pattern_val, "\n", content)
print(f"Removed pivot <column> entries: noms={n_col_noms}, valeurs={n_col_val}")

# =====================================================================
# 8. Add <column> entries for REF BI01 and REF BI02
# =====================================================================
# Insert them right after the </aliases> tag (a stable anchor) in each datasource block
ref_bi01_col = "  <column datatype='string' name='[REF BI01]' role='dimension' type='nominal' />\n  "
ref_bi02_col = "  <column datatype='string' name='[REF BI02]' role='dimension' type='nominal' />\n  "
# Look for the <aliases enabled='yes' /> tag and insert after
aliases_tag = "<aliases enabled='yes' />"
n_aliases = content.count(aliases_tag)
print(f"Found {n_aliases} <aliases> tags")
content = content.replace(aliases_tag, aliases_tag + "\n  " + ref_bi01_col.rstrip() + "\n  " + ref_bi02_col.rstrip())

# =====================================================================
# 9. Save and repackage
# =====================================================================
twb_file.write_text(content, encoding='utf-8')
print(f"\nNew length: {len(content)} (delta: {len(content)-orig_len})")

# Validate XML (will raise if broken)
import xml.etree.ElementTree as ET
try:
    ET.parse(twb_file)
    print("XML: VALID")
except ET.ParseError as e:
    print(f"XML PARSE ERROR: {e}")
    raise SystemExit(1)

# Repackage
out_twbx = TWBX_PATH
tmp_twbx = TWBX_PATH.parent / "twbx_tmp.twbx"
if tmp_twbx.exists():
    tmp_twbx.unlink()
with zipfile.ZipFile(tmp_twbx, 'w', zipfile.ZIP_DEFLATED) as z:
    for f in WORK_DIR.rglob('*'):
        if f.is_file():
            z.write(f, arcname=f.relative_to(WORK_DIR))
shutil.copy2(tmp_twbx, out_twbx)
tmp_twbx.unlink()
shutil.rmtree(WORK_DIR)
print(f"Repackaged: {out_twbx}")
