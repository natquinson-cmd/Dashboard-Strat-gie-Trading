"""
MINIMAL twbx modification: only swap the connection from published sqlproxy
datasource to a local Hyper file. Keep ALL formulas, columns, calculations as-is.
"""
import zipfile, shutil, re
from pathlib import Path

TWBX_PATH = Path(r"C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse.twbx")
WORK_DIR = Path(r"C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_minswap")

HYPER_PATH_FWD = "//scxdata/CommunOS_BI$/C Courant/Datasources/ISCS-BI/SuiviProjetDWH/flatfiles/Perimetre_Migration.hyper"
HYPER_CONN_NAME = "hyper.epfl_perimetre_migration"

if WORK_DIR.exists():
    shutil.rmtree(WORK_DIR)
WORK_DIR.mkdir()
with zipfile.ZipFile(TWBX_PATH, 'r') as z:
    z.extractall(WORK_DIR)
twb_file = next(WORK_DIR.glob("*.twb"))
content = twb_file.read_text(encoding='utf-8')
orig_len = len(content)
print(f"Original length: {orig_len}")

# 1. Remove <repository-location> for the published datasource (NOT the workbook one)
repo_pattern = r"\s*<repository-location derived-from='https://tableau\.epfl\.ch/datasources/Perimetre_MigrationExcel[^>]*/>\r?\n"
n_repo = len(re.findall(repo_pattern, content))
content = re.sub(repo_pattern, "\n", content)
print(f"Removed {n_repo} datasource <repository-location> lines")

# 2. Replace the <connection class='sqlproxy' ...> opening tag with the federated wrapper
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
print(f"Replacing connection openings: variant1={n1}, variant2={n2}")
content = content.replace(old_conn_open_1, new_conn_open)
content = content.replace(old_conn_open_2, new_conn_open)

# 3. Update <relation> tags: keep alias 'sqlproxy' so all [sqlproxy].[col] refs stay valid,
#    but reference the new hyper connection and the new table [Extract].[Extract]
old_relation = "<relation name='sqlproxy' table='[sqlproxy]' type='table' />"
new_relation = f"<relation connection='{HYPER_CONN_NAME}' name='sqlproxy' table='[Extract].[Extract]' type='table' />"
n_rel = content.count(old_relation)
print(f"Updating {n_rel} <relation> tags")
content = content.replace(old_relation, new_relation)

# Save
twb_file.write_text(content, encoding='utf-8')
print(f"\nNew length: {len(content)} (delta: {len(content)-orig_len})")

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
