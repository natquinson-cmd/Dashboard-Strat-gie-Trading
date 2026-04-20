"""Add Domaine + Charge_Jours columns inside the 'Nettoyer 1' container of the Jira flow."""
import json, zipfile, shutil, uuid
from pathlib import Path

FLOW_PATH = Path(r"C:\Users\quinson\Documents\Mon dossier Tableau Prep\Flux\Traitement Jira.tfl")
WORK_DIR  = Path(r"C:\Users\quinson\Desktop\Claude\Tableau DWH\jira_work_add")

CONTAINER_ID = "d4702b31-3029-4d7f-82fd-850b57a035cd"  # Nettoyer 1 container

# Generate IDs for the new nodes
DOMAINE_ID = str(uuid.uuid4())
CHARGE_ID  = str(uuid.uuid4())

if WORK_DIR.exists():
    shutil.rmtree(WORK_DIR)
WORK_DIR.mkdir()
with zipfile.ZipFile(FLOW_PATH, 'r') as z:
    z.extractall(WORK_DIR)
flow_file = WORK_DIR / "flow"
with open(flow_file, 'r', encoding='utf-8') as f:
    flow = json.load(f)

# The 2 AddColumn nodes to put inside the container
domaine_node = {
    "nodeType": ".v1.AddColumn",
    "columnName": "Domaine",
    "expression": "IF STARTSWITH([Parent summary], 'NEX') THEN 'Nexus' ELSEIF STARTSWITH([Parent summary], 'PLX') THEN 'Plexus' ELSE 'Autres' END",
    "name": "Add Domaine",
    "id": DOMAINE_ID,
    "baseType": "transform",
    "nextNodes": [
        {"namespace": "Default", "nextNodeId": CHARGE_ID, "nextNamespace": "Default"}
    ],
    "serialize": False,
    "description": None
}

charge_node = {
    "nodeType": ".v1.AddColumn",
    "columnName": "Charge_Jours",
    "expression": "[Champs personnalisés (Story point estimate)] / 50.0",
    "name": "Add Charge_Jours",
    "id": CHARGE_ID,
    "baseType": "transform",
    "nextNodes": [],
    "serialize": False,
    "description": None
}

# Inject them into the container's loomContainer
container = flow["nodes"][CONTAINER_ID]
loom = container["loomContainer"]
loom["nodes"][DOMAINE_ID] = domaine_node
loom["nodes"][CHARGE_ID]  = charge_node
loom["initialNodes"] = [DOMAINE_ID]  # data enters here

# Tell the container how inputs and outputs map to the inner nodes
container["namespacesToInput"] = {
    "Default": {"nodeId": DOMAINE_ID, "namespace": "Default"}
}
container["namespacesToOutput"] = {
    "Default": {"nodeId": CHARGE_ID, "namespace": "Default"}
}

print(f"Added 2 AddColumn nodes inside container '{container['name']}':")
print(f"  - Domaine ({DOMAINE_ID[:8]})")
print(f"  - Charge_Jours ({CHARGE_ID[:8]})")
print(f"  Chain: input -> Domaine -> Charge_Jours -> container output")

# Save and repackage
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
