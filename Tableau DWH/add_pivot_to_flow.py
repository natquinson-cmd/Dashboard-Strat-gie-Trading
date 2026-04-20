"""
Insert a Pivot (Unpivot) node between 'Ajout Num Semaine' and 'Sortie' that
unpivots REF BI01 and REF BI02 into the columns expected by the dashboard:
  - 'Noms des champs de tableau croisé dynamique' = "Ref Bi01" / "Ref Bi02"
  - 'Valeurs du champ de tableau croisé dynamique' = REF BI01 / REF BI02 value

This reproduces the pivot the published datasource was doing on the server,
so the .hyper output has the long-format data the dashboard's calculations expect
(including the /2 divisions that compensate for row doubling).
"""
import json, zipfile, shutil, uuid
from pathlib import Path

FLOW_PATH = Path(r"C:\Users\quinson\Documents\Mon dossier Tableau Prep\Flux\Perimetre Migration.tfl")
WORK_DIR  = Path(r"C:\Users\quinson\Desktop\Claude\Tableau DWH\tfl_pivot_work")

# IDs
PREVIOUS_NODE_ID = "360de93e-64ac-4056-9d6d-16719743c4ae"  # Ajout Num Semaine container
OUTPUT_NODE_ID   = "c449e97c-80e0-46c0-b489-9e08b7429ec9"  # Sortie

# New node IDs (random UUIDs to avoid collision)
NEW_PIVOT_ID  = str(uuid.uuid4())
NEW_ACTION_ID = str(uuid.uuid4())

PIVOT_NAME_COL  = "Noms des champs de tableau crois\u00e9 dynamique"
PIVOT_VALUE_COL = "Valeurs du champ de tableau crois\u00e9 dynamique"

# --- extract ---
if WORK_DIR.exists():
    shutil.rmtree(WORK_DIR)
WORK_DIR.mkdir()
with zipfile.ZipFile(FLOW_PATH, 'r') as z:
    z.extractall(WORK_DIR)
flow_file = WORK_DIR / "flow"
with open(flow_file, 'r', encoding='utf-8') as f:
    flow = json.load(f)

# --- build the SuperUnpivot node ---
# Each "expression" defines one column to unpivot. With 2 expressions, each input row becomes 2 rows.
new_pivot_node = {
    "nodeType": ".v2018_2_3.SuperUnpivot",
    "name": "Pivot REF BI01/BI02",
    "id": NEW_PIVOT_ID,
    "baseType": "superNode",
    "nextNodes": [
        {
            "namespace": "Default",
            "nextNodeId": OUTPUT_NODE_ID,
            "nextNamespace": "Default"
        }
    ],
    "serialize": False,
    "description": None,
    "beforeActionAnnotations": [],
    "afterActionAnnotations": [],
    "actionNode": {
        "nodeType": ".v1.Unpivot",
        "name": "Permuter REF BI",
        "id": NEW_ACTION_ID,
        "baseType": "transform",
        "nextNodes": [],
        "serialize": False,
        "description": None,
        "usesSmartDefaults": True,
        "unpivotGroups": [
            {
                "expressions": [
                    {
                        "bindings": [
                            {
                                "bindingType": "literal",
                                "newColumnName": PIVOT_NAME_COL,
                                "groupName": "Ref Bi01"
                            },
                            {
                                "bindingType": "column",
                                "newColumnName": PIVOT_VALUE_COL,
                                "columnName": "REF BI01"
                            }
                        ]
                    },
                    {
                        "bindings": [
                            {
                                "bindingType": "literal",
                                "newColumnName": PIVOT_NAME_COL,
                                "groupName": "Ref Bi02"
                            },
                            {
                                "bindingType": "column",
                                "newColumnName": PIVOT_VALUE_COL,
                                "columnName": "REF BI02"
                            }
                        ]
                    }
                ]
            }
        ]
    }
}

# --- insert into flow ---
# 1. Add the new pivot node to the nodes dict
flow["nodes"][NEW_PIVOT_ID] = new_pivot_node
print(f"Added pivot node {NEW_PIVOT_ID[:8]}")

# 2. Update the previous node (Ajout Num Semaine) so its nextNodes points to the pivot instead of the output
prev_node = flow["nodes"][PREVIOUS_NODE_ID]
print(f"Old nextNodes of {PREVIOUS_NODE_ID[:8]}: {[n['nextNodeId'][:8] for n in prev_node['nextNodes']]}")
prev_node["nextNodes"] = [
    {
        "namespace": "Default",
        "nextNodeId": NEW_PIVOT_ID,
        "nextNamespace": "Default"
    }
]
print(f"New nextNodes of {PREVIOUS_NODE_ID[:8]}: {[n['nextNodeId'][:8] for n in prev_node['nextNodes']]}")

# --- write back and repackage ---
with open(flow_file, 'w', encoding='utf-8') as f:
    json.dump(flow, f, indent=2, ensure_ascii=False)

tmp_tfl = WORK_DIR.parent / "Perimetre Migration.tfl.pivot_new"
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
