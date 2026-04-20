"""
STEP 1: Modify the Prep flow to change ONLY the output node from WriteToExcel to WriteToHyper.
Keep input 'Perimetre_Migration 2' as Excel for this first run.
"""
import json
import zipfile
import shutil
from pathlib import Path

FLOW_PATH = Path(r"C:\Users\quinson\Documents\Mon dossier Tableau Prep\Flux\Perimetre Migration.tfl")
BACKUP_PATH = Path(r"C:\Users\quinson\Desktop\Claude\Tableau DWH\Perimetre Migration - BEFORE hyper.tfl")
WORK_DIR = Path(r"C:\Users\quinson\Desktop\Claude\Tableau DWH\tfl_work")

HYPER_OUT = r"\\scxdata\CommunOS_BI$\C Courant\Datasources\ISCS-BI\SuiviProjetDWH\flatfiles\Perimetre_Migration.hyper"
TDS_OUT = r"\\scxdata\CommunOS_BI$\C Courant\Datasources\ISCS-BI\SuiviProjetDWH\flatfiles\Perimetre_Migration.tds"

# ID of the Sortie output node
OUTPUT_NODE_ID = "c449e97c-80e0-46c0-b489-9e08b7429ec9"

# 1. Backup
if not BACKUP_PATH.exists():
    shutil.copy2(FLOW_PATH, BACKUP_PATH)
    print(f"Backup: {BACKUP_PATH}")

# 2. Extract .tfl (zip)
if WORK_DIR.exists():
    shutil.rmtree(WORK_DIR)
WORK_DIR.mkdir(parents=True)
with zipfile.ZipFile(FLOW_PATH, 'r') as z:
    z.extractall(WORK_DIR)
print(f"Extracted to {WORK_DIR}")

# 3. Read the flow JSON
flow_file = WORK_DIR / "flow"
with open(flow_file, 'r', encoding='utf-8') as f:
    flow = json.load(f)

# 4. Find and modify the output node
node = flow["nodes"][OUTPUT_NODE_ID]
print(f"Current output node: {node['nodeType']}")
print(f"  Excel file: {node.get('excelOutputFile', '')}")

# Replace with WriteToHyper
new_node = {
    "nodeType": ".v1.WriteToHyper",
    "name": node["name"],
    "id": node["id"],
    "baseType": "output",
    "nextNodes": node.get("nextNodes", []),
    "serialize": node.get("serialize", False),
    "description": node.get("description", None),
    "hyperOutputFile": HYPER_OUT,
    "tdsOutput": TDS_OUT,
}
flow["nodes"][OUTPUT_NODE_ID] = new_node
print(f"New output node: {new_node['nodeType']}")
print(f"  Hyper file: {new_node['hyperOutputFile']}")

# The nodeProperties references the old node ID for OutputRefreshOptions.
# We keep this because ID is the same. But OutputRefreshOptions may not apply
# the same way for Hyper output; let's keep it for safety (truncate mode).
print(f"nodeProperties for this node still present: {OUTPUT_NODE_ID in flow.get('nodeProperties', {})}")

# 5. Write back the flow file
with open(flow_file, 'w', encoding='utf-8') as f:
    json.dump(flow, f, indent=2, ensure_ascii=False)
print("Flow JSON rewritten")

# 6. Repackage .tfl (zip)
temp_tfl = WORK_DIR.parent / "Perimetre Migration.tfl.new"
if temp_tfl.exists():
    temp_tfl.unlink()
with zipfile.ZipFile(temp_tfl, 'w', zipfile.ZIP_DEFLATED) as z:
    for f in WORK_DIR.iterdir():
        z.write(f, arcname=f.name)

# Replace the original
shutil.copy2(temp_tfl, FLOW_PATH)
temp_tfl.unlink()
shutil.rmtree(WORK_DIR)
print(f"Written new .tfl: {FLOW_PATH}")
print(f"Size: {FLOW_PATH.stat().st_size} bytes")
