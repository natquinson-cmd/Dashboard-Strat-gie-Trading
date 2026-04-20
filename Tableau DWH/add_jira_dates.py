"""Add 5 ChangeColumnType nodes to convert Jira string dates into real dates."""
import json, zipfile, shutil, uuid
from pathlib import Path

FLOW_PATH = Path(r"C:\Users\quinson\Documents\Mon dossier Tableau Prep\Flux\Traitement Jira.tfl")
WORK_DIR = Path(r"C:\Users\quinson\Desktop\Claude\Tableau DWH\jira_dates_work")

CONTAINER_ID = "d4702b31-3029-4d7f-82fd-850b57a035cd"

# Columns to convert
DATE_COLS = [
    "Date d'\u00e9ch\u00e9ance",  # Date d'échéance
    "R\u00e9solu",                   # Résolu
    "Cr\u00e9ation",                 # Création
    "Mise \u00e0 jour",              # Mise à jour
    "Champs personnalis\u00e9s (Start date)",  # Start date
]

if WORK_DIR.exists(): shutil.rmtree(WORK_DIR)
WORK_DIR.mkdir()
with zipfile.ZipFile(FLOW_PATH, 'r') as z:
    z.extractall(WORK_DIR)
flow_file = WORK_DIR / "flow"
with open(flow_file, 'r', encoding='utf-8') as f:
    flow = json.load(f)

# Generate new node IDs
parse_ids = [str(uuid.uuid4()) for _ in DATE_COLS]

# Build ChangeColumnType nodes
# Use DATE(STR([col])) which is lenient and tries to parse common formats
new_nodes = {}
for i, col in enumerate(DATE_COLS):
    nid = parse_ids[i]
    # Escape: Prep uses [col name] style. If col has apostrophe, no escaping needed inside brackets.
    calc_expr = f"IF NOT ISNULL(DATE(STR([{col}]))) THEN DATE(STR([{col}])) ELSE NULL END"
    next_nodes = []
    if i + 1 < len(parse_ids):
        next_nodes = [{"namespace":"Default","nextNodeId":parse_ids[i+1],"nextNamespace":"Default"}]
    new_nodes[nid] = {
        "nodeType": ".v1.ChangeColumnType",
        "fields": { col: {"type":"date","calc":calc_expr} },
        "name": f"Parse date {col[:25]}",
        "id": nid,
        "baseType": "transform",
        "nextNodes": next_nodes,
        "serialize": False,
        "description": None
    }

# Inject into container
container = flow["nodes"][CONTAINER_ID]
loom = container["loomContainer"]

# Find the current last node (namespacesToOutput -> nodeId)
current_output_nodeid = container["namespacesToOutput"]["Default"]["nodeId"]
print(f"Current container output node: {current_output_nodeid[:8]}")

# The current last node's nextNodes should be updated to point to the first parse node
last_node = loom["nodes"][current_output_nodeid]
last_node["nextNodes"] = [{"namespace":"Default","nextNodeId":parse_ids[0],"nextNamespace":"Default"}]

# Add all new nodes
for nid, node in new_nodes.items():
    loom["nodes"][nid] = node

# Update namespacesToOutput to the new last node (last parse node)
container["namespacesToOutput"] = {"Default":{"nodeId":parse_ids[-1],"namespace":"Default"}}

print(f"Added {len(parse_ids)} date parsers, new container output: {parse_ids[-1][:8]}")
print(f"New chain: {current_output_nodeid[:8]} -> {' -> '.join(p[:8] for p in parse_ids)}")

# Save + repackage
with open(flow_file, 'w', encoding='utf-8') as f:
    json.dump(flow, f, indent=2, ensure_ascii=False)

tmp_tfl = WORK_DIR.parent / "Traitement Jira.tfl.new"
if tmp_tfl.exists(): tmp_tfl.unlink()
with zipfile.ZipFile(tmp_tfl, 'w', zipfile.ZIP_DEFLATED) as z:
    for ff in WORK_DIR.iterdir():
        z.write(ff, arcname=ff.name)
shutil.copy2(tmp_tfl, FLOW_PATH)
tmp_tfl.unlink(); shutil.rmtree(WORK_DIR)
print(f"\nWritten: {FLOW_PATH}")
