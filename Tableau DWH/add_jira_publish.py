"""Add PublishExtract node to Jira flow to publish Jira_Projet datasource on Tableau Server."""
import json, zipfile, shutil, uuid
from pathlib import Path

FLOW_PATH = Path(r"C:\Users\quinson\Documents\Mon dossier Tableau Prep\Flux\Traitement Jira.tfl")
WORK_DIR  = Path(r"C:\Users\quinson\Desktop\Claude\Tableau DWH\jira_work_pub")

CONTAINER_ID = "d4702b31-3029-4d7f-82fd-850b57a035cd"  # Nettoyer 1 container

# Server publish config
PROJECT_NAME = "Published"
PROJECT_LUID = "028b1ddb-7103-42ee-b91c-115c55df29c0"
DATASOURCE_NAME = "Jira_Projet"
SERVER_URL = "https://tableau.epfl.ch"

NEW_PUBLISH_ID = str(uuid.uuid4())

if WORK_DIR.exists():
    shutil.rmtree(WORK_DIR)
WORK_DIR.mkdir()
with zipfile.ZipFile(FLOW_PATH, 'r') as z:
    z.extractall(WORK_DIR)
flow_file = WORK_DIR / "flow"
with open(flow_file, 'r', encoding='utf-8') as f:
    flow = json.load(f)

# Create PublishExtract node
publish_node = {
    "nodeType": ".v1.PublishExtract",
    "name": "Publier Jira_Projet sur Tableau Server",
    "id": NEW_PUBLISH_ID,
    "baseType": "output",
    "nextNodes": [],
    "serialize": False,
    "description": None,
    "projectName": PROJECT_NAME,
    "projectLuid": PROJECT_LUID,
    "datasourceName": DATASOURCE_NAME,
    "datasourceDescription": "Planning Jira - genere par Traitement Jira.tfl",
    "serverUrl": SERVER_URL
}
flow['nodes'][NEW_PUBLISH_ID] = publish_node

# Connect container -> Publish (in addition to the existing container -> WriteToHyper)
container = flow['nodes'][CONTAINER_ID]
existing_next = container.get('nextNodes', [])
print(f"Container current nextNodes: {[n['nextNodeId'][:8] for n in existing_next]}")
container['nextNodes'].append({
    "namespace": "Default",
    "nextNodeId": NEW_PUBLISH_ID,
    "nextNamespace": "Default"
})
print(f"Container new nextNodes: {[n['nextNodeId'][:8] for n in container['nextNodes']]}")

# Save + repackage
with open(flow_file, 'w', encoding='utf-8') as f:
    json.dump(flow, f, indent=2, ensure_ascii=False)

tmp_tfl = WORK_DIR.parent / "Traitement Jira.tfl.new"
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
