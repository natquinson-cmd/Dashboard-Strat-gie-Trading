"""
Insert a new node between LoadExcel 'Périmètre migration' (ce00679c) and its next nodes
to override DateDujour with TODAY(), so the cached value in the Excel formula doesn't matter.
"""
import json, zipfile, shutil, uuid
from pathlib import Path

FLOW_PATH = Path(r"C:\Users\quinson\Documents\Mon dossier Tableau Prep\Flux\Perimetre Migration.tfl")
WORK_DIR = Path(r"C:\Users\quinson\Desktop\Claude\Tableau DWH\tfl_date")

LOAD_EXCEL_ID = "ce00679c-f7ee-40c2-bbb1-9814930c7897"  # LoadExcel "Périmètre migration"
NEW_NODE_ID = str(uuid.uuid4())

if WORK_DIR.exists():
    shutil.rmtree(WORK_DIR)
WORK_DIR.mkdir()
with zipfile.ZipFile(FLOW_PATH, 'r') as z:
    z.extractall(WORK_DIR)
flow_file = WORK_DIR / "flow"
with open(flow_file, 'r', encoding='utf-8') as f:
    flow = json.load(f)

# Get current nextNodes of LoadExcel ce00679c
load_excel = flow['nodes'][LOAD_EXCEL_ID]
current_next = load_excel['nextNodes']
print(f"LoadExcel current nextNodes: {[n['nextNodeId'][:8] for n in current_next]}")

# Build the new ChangeColumnType node that overrides DateDujour to TODAY()
new_node = {
    "nodeType": ".v1.ChangeColumnType",
    "fields": {
        "DateDujour": {
            "type": "date",
            "calc": "TODAY()"
        }
    },
    "name": "Override DateDujour = TODAY()",
    "id": NEW_NODE_ID,
    "baseType": "transform",
    "nextNodes": current_next,  # take over the original nextNodes
    "serialize": False,
    "description": None
}
flow['nodes'][NEW_NODE_ID] = new_node
print(f"Added override node: {NEW_NODE_ID[:8]}")

# Re-route LoadExcel to point ONLY to the new node
load_excel['nextNodes'] = [
    {
        "namespace": "Default",
        "nextNodeId": NEW_NODE_ID,
        "nextNamespace": "Default"
    }
]
print(f"Re-routed LoadExcel -> new node")

# Save and repackage
with open(flow_file, 'w', encoding='utf-8') as f:
    json.dump(flow, f, indent=2, ensure_ascii=False)

tmp_tfl = WORK_DIR.parent / "Perimetre Migration.tfl.date"
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
