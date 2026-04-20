"""
Option 3: Restructure the Prep flow as follows:
1. Revert input "Perimetre_Migration 2" from LoadSql (Hyper) back to LoadExcel (original Excel)
2. Restore the Excel connection (with class='excel-direct' and filename pointing to the .xlsx)
3. Add a SECOND output node WriteToExcel (writes back to the same Excel file, un-pivoted history)
4. Keep the existing Pivot → WriteToHyper output (for the dashboard)

The flow becomes:
  Excel.xlsx ──┐
               ├─► [union/joins/cleanup] ──► Ajout Num Semaine ─┬─► WriteToExcel (history Excel, un-pivoted)
  New Excel ───┘                                                └─► Pivot ──► WriteToHyper (dashboard, pivoted)
"""
import json, zipfile, shutil, uuid
from pathlib import Path

FLOW_PATH = Path(r"C:\Users\quinson\Documents\Mon dossier Tableau Prep\Flux\Perimetre Migration.tfl")
ORIGINAL_BACKUP = Path(r"C:\Users\quinson\Desktop\Claude\Tableau DWH\Perimetre Migration - BEFORE hyper.tfl")
WORK_DIR = Path(r"C:\Users\quinson\Desktop\Claude\Tableau DWH\tfl_opt3")

# Node IDs
INPUT_NODE_ID = "0e3e735c-b429-4b0f-b617-2628718e686c"  # Perimetre_Migration 2
PIVOT_NODE_ID = "29776b16-bb88-4004-904b-80e25eed370d"  # SuperUnpivot we added
OUTPUT_HYPER_ID = "c449e97c-80e0-46c0-b489-9e08b7429ec9"  # Existing output (currently WriteToHyper)
PREVIOUS_NODE_ID = "360de93e-64ac-4056-9d6d-16719743c4ae"  # Ajout Num Semaine container
EXCEL_CONN_ID = "3192c8b4-41bb-4d6d-b7e5-7e6ddc116c14"  # The connection ID

# Generate a NEW ID for the second output (WriteToExcel)
NEW_EXCEL_OUT_ID = str(uuid.uuid4())

# Excel file path
EXCEL_PATH = r"\\scxdata\CommunOS_BI$\C Courant\Datasources\ISCS-BI\SuiviProjetDWH\flatfiles\Perimetre_Migration - Stockage Finale DataPrep.xlsx"

# 1. Read the ORIGINAL backup to get the LoadExcel node + Excel connection
with zipfile.ZipFile(ORIGINAL_BACKUP) as z:
    with z.open('flow') as f:
        orig_flow = json.load(f)

orig_load_excel_node = orig_flow['nodes'][INPUT_NODE_ID]
orig_excel_conn = orig_flow['connections'][EXCEL_CONN_ID]
print(f"Got original LoadExcel node ({len(orig_load_excel_node['fields'])} fields)")
print(f"Got original Excel connection")

# 2. Extract current flow
if WORK_DIR.exists():
    shutil.rmtree(WORK_DIR)
WORK_DIR.mkdir()
with zipfile.ZipFile(FLOW_PATH, 'r') as z:
    z.extractall(WORK_DIR)
flow_file = WORK_DIR / "flow"
with open(flow_file, 'r', encoding='utf-8') as f:
    flow = json.load(f)

# 3. Replace the input node with the LoadExcel
# Preserve current nextNodes
current_input = flow['nodes'][INPUT_NODE_ID]
current_next = current_input.get('nextNodes', [])
print(f"Current input nextNodes: {[n['nextNodeId'][:8] for n in current_next]}")

new_input = dict(orig_load_excel_node)
new_input['nextNodes'] = current_next
flow['nodes'][INPUT_NODE_ID] = new_input
print(f"Replaced input with LoadExcel")

# 4. Replace the Excel connection
flow['connections'][EXCEL_CONN_ID] = orig_excel_conn
print(f"Replaced connection with Excel definition")

# 5. Connect Ajout Num Semaine to BOTH the existing pivot AND a new WriteToExcel node
# Currently: 360de93e → 29776b16 (pivot)
# New: 360de93e → 29776b16 (pivot) AND 360de93e → NEW_EXCEL_OUT
prev_node = flow['nodes'][PREVIOUS_NODE_ID]
print(f"Ajout Num Semaine current nextNodes: {[n['nextNodeId'][:8] for n in prev_node['nextNodes']]}")
prev_node['nextNodes'].append({
    "namespace": "Default",
    "nextNodeId": NEW_EXCEL_OUT_ID,
    "nextNamespace": "Default"
})
print(f"Ajout Num Semaine new nextNodes: {[n['nextNodeId'][:8] for n in prev_node['nextNodes']]}")

# 6. Create the new WriteToExcel node
new_excel_output = {
    "nodeType": ".v2021_1_1.WriteToExcel",
    "name": "Sortie Excel (history)",
    "id": NEW_EXCEL_OUT_ID,
    "baseType": "output",
    "nextNodes": [],
    "serialize": False,
    "description": None,
    "excelOutputFile": EXCEL_PATH,
    "excelOutputSheetName": "[Perimetre_Migration$]"
}
flow['nodes'][NEW_EXCEL_OUT_ID] = new_excel_output
print(f"Added WriteToExcel output: {NEW_EXCEL_OUT_ID[:8]}")

# 7. Add nodeProperties for the new Excel output (truncate mode like original)
flow.setdefault('nodeProperties', {})[NEW_EXCEL_OUT_ID] = {
    "com.tableau.loom.doc.fileformat.v2020_2_1.OutputRefreshOptions": {
        "nodePropertyType": ".v2020_2_1.OutputRefreshOptions",
        "outputOperationType": "outputOperationTypeTruncate",
        "incrementalOutputOperationType": "outputOperationTypeAppend",
        "isIncrementalDefault": False
    }
}

# 8. Save flow JSON
with open(flow_file, 'w', encoding='utf-8') as f:
    json.dump(flow, f, indent=2, ensure_ascii=False)

# 9. Repackage
tmp_tfl = WORK_DIR.parent / "Perimetre Migration.tfl.opt3"
if tmp_tfl.exists():
    tmp_tfl.unlink()
with zipfile.ZipFile(tmp_tfl, 'w', zipfile.ZIP_DEFLATED) as z:
    for ff in WORK_DIR.iterdir():
        z.write(ff, arcname=ff.name)
shutil.copy2(tmp_tfl, FLOW_PATH)
tmp_tfl.unlink()
shutil.rmtree(WORK_DIR)
print(f"\nWritten: {FLOW_PATH}")
print(f"Size: {FLOW_PATH.stat().st_size} bytes")
