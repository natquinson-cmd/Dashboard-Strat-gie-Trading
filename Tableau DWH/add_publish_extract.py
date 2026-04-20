"""
Add a PublishExtract node after the Pivot in the Prep flow, so each run publishes
the pivoted data directly to the Tableau Server datasource 'Perimetre_Migration_Hyper'.

Flow structure after changes:
  Ajout Num Semaine ──┬─► Pivot ──┬─► WriteToHyper (local file, optional)
                      │           └─► PublishExtract (Tableau Server) ← NEW
                      └─► WriteToExcel (history)
"""
import json, zipfile, shutil, uuid
from pathlib import Path

FLOW_PATH = Path(r"C:\Users\quinson\Documents\Mon dossier Tableau Prep\Flux\Perimetre Migration.tfl")
WORK_DIR = Path(r"C:\Users\quinson\Desktop\Claude\Tableau DWH\tfl_publish")

PIVOT_NODE_ID = "29776b16-bb88-4004-904b-80e25eed370d"  # SuperUnpivot
NEW_PUBLISH_ID = str(uuid.uuid4())

# Tableau Server publish settings
PROJECT_NAME = "Published"  # adjust if the datasource lives in another project
PROJECT_LUID = "028b1ddb-7103-42ee-b91c-115c55df29c0"  # same LUID as the other flow on this server
DATASOURCE_NAME = "Perimetre_Migration_Hyper"
SERVER_URL = "https://tableau.epfl.ch"

if WORK_DIR.exists():
    shutil.rmtree(WORK_DIR)
WORK_DIR.mkdir()
with zipfile.ZipFile(FLOW_PATH, 'r') as z:
    z.extractall(WORK_DIR)
flow_file = WORK_DIR / "flow"
with open(flow_file, 'r', encoding='utf-8') as f:
    flow = json.load(f)

# Create new PublishExtract node
new_publish = {
    "nodeType": ".v1.PublishExtract",
    "name": "Publier Hyper sur Tableau Server",
    "id": NEW_PUBLISH_ID,
    "baseType": "output",
    "nextNodes": [],
    "serialize": False,
    "description": None,
    "projectName": PROJECT_NAME,
    "projectLuid": PROJECT_LUID,
    "datasourceName": DATASOURCE_NAME,
    "datasourceDescription": "Auto-published by Perimetre Migration flow",
    "serverUrl": SERVER_URL
}
flow['nodes'][NEW_PUBLISH_ID] = new_publish
print(f"Added PublishExtract node: {NEW_PUBLISH_ID[:8]}")

# Connect the Pivot node to the new PublishExtract (in addition to its existing nextNode)
pivot = flow['nodes'][PIVOT_NODE_ID]
print(f"Pivot current nextNodes: {[n['nextNodeId'][:8] for n in pivot['nextNodes']]}")
pivot['nextNodes'].append({
    "namespace": "Default",
    "nextNodeId": NEW_PUBLISH_ID,
    "nextNamespace": "Default"
})
print(f"Pivot new nextNodes: {[n['nextNodeId'][:8] for n in pivot['nextNodes']]}")

# Save and repackage
with open(flow_file, 'w', encoding='utf-8') as f:
    json.dump(flow, f, indent=2, ensure_ascii=False)

tmp_tfl = WORK_DIR.parent / "Perimetre Migration.tfl.publish"
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
