"""
STEP 3: Modify the Prep flow input 'Perimetre_Migration 2' from Excel to Hyper.

Strategy:
- Keep the same node ID and connectionId (so all nextNodes references stay valid).
- Change the connection class from 'excel-direct' to 'hyper'.
- Change the node type to .v1.LoadRelational (generic SQL-based load for Hyper).
- Update the relation to point to the [Extract].[Extract] table from the generated Hyper.
- Update the fields array to match the new Hyper schema.
- Clear the 'actions' array (the RemoveColumns transforms referenced columns that
  no longer exist in the Hyper — they were already removed by the flow on previous run).
"""
import json
import zipfile
import shutil
from pathlib import Path
from tableauhyperapi import HyperProcess, Telemetry, Connection, TypeTag

FLOW_PATH = Path(r"C:\Users\quinson\Documents\Mon dossier Tableau Prep\Flux\Perimetre Migration.tfl")
HYPER_PATH = r"\\scxdata\CommunOS_BI$\C Courant\Datasources\ISCS-BI\SuiviProjetDWH\flatfiles\Perimetre_Migration.hyper"
HYPER_LOCAL = r"C:\Users\quinson\Desktop\Claude\Tableau DWH\Perimetre_Migration.hyper"
WORK_DIR = Path(r"C:\Users\quinson\Desktop\Claude\Tableau DWH\tfl_work3")

INPUT_NODE_ID = "0e3e735c-b429-4b0f-b617-2628718e686c"
CONN_ID = "3192c8b4-41bb-4d6d-b7e5-7e6ddc116c14"

# ---------- 1. Read the Hyper schema to build the fields array ----------
def hyper_type_to_prep(tt):
    # Mapping Hyper TypeTag to Prep field type string
    t = str(tt)
    if "DATE" in t and "TIME" not in t: return "date"
    if "TIMESTAMP" in t or "DATETIME" in t: return "datetime"
    if "BIG_INT" in t or "INTEGER" in t or "SMALL_INT" in t: return "integer"
    if "DOUBLE" in t or "NUMERIC" in t or "FLOAT" in t: return "real"
    if "BOOL" in t: return "bool"
    return "string"

print("Reading Hyper schema...")
with HyperProcess(telemetry=Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as hyper:
    with Connection(endpoint=hyper.endpoint, database=HYPER_LOCAL) as conn:
        table_defs = []
        for schema in conn.catalog.get_schema_names():
            for t in conn.catalog.get_table_names(schema):
                td = conn.catalog.get_table_definition(t)
                table_defs.append((t, td))
        tname, tdef = table_defs[0]  # should be "Extract"."Extract"
        print(f"  Using table: {tname}")

        fields = []
        for i, col in enumerate(tdef.columns):
            # col.name is a Name object; get the unquoted string
            cname = col.name.unescaped
            ftype = hyper_type_to_prep(col.type.tag)
            fields.append({
                "name": cname,
                "type": ftype,
                "collation": None,
                "caption": "",
                "ordinal": i,
                "isGenerated": False
            })
        print(f"  Built {len(fields)} field definitions")

# ---------- 2. Extract the .tfl ----------
if WORK_DIR.exists():
    shutil.rmtree(WORK_DIR)
WORK_DIR.mkdir(parents=True)
with zipfile.ZipFile(FLOW_PATH, 'r') as z:
    z.extractall(WORK_DIR)

# ---------- 3. Load flow JSON and modify ----------
flow_file = WORK_DIR / "flow"
with open(flow_file, 'r', encoding='utf-8') as f:
    flow = json.load(f)

# Preserve next nodes from old node
old_node = flow["nodes"][INPUT_NODE_ID]
next_nodes = old_node.get("nextNodes", [])
print(f"Preserving {len(next_nodes)} nextNodes link(s)")

# Update the connection
conn = flow["connections"][CONN_ID]
print(f"Old connection class: {conn['connectionAttributes'].get('class')}")
conn["name"] = "Perimetre_Migration.hyper"
conn["connectionAttributes"] = {
    "filename": HYPER_PATH,
    "class": "hyper",
    "directory": r"\\scxdata\CommunOS_BI$\C Courant\Datasources\ISCS-BI\SuiviProjetDWH\flatfiles"
}
print(f"New connection class: {conn['connectionAttributes']['class']}")

# Replace the input node entirely (keeping id, name, nextNodes, connectionId)
new_node = {
    "nodeType": ".v1.LoadRelational",
    "name": "Perimetre_Migration 2",
    "id": INPUT_NODE_ID,
    "baseType": "input",
    "nextNodes": next_nodes,
    "serialize": False,
    "description": None,
    "connectionId": CONN_ID,
    "connectionAttributes": {},
    "fields": fields,
    "actions": [],
    "debugModeRowLimit": old_node.get("debugModeRowLimit", -1),
    "originalDataTypes": {},
    "randomSampling": old_node.get("randomSampling", None),
    "updateTimestamp": old_node.get("updateTimestamp", None),
    "restrictedFields": [],
    "userRenamedFields": {},
    "selectedFields": None,
    "samplingType": None,
    "groupByFields": None,
    "filters": [],
    "relation": {
        "type": "table",
        "table": "[Extract].[Extract]"
    }
}
flow["nodes"][INPUT_NODE_ID] = new_node
print(f"New node type: {new_node['nodeType']}")
print(f"New relation: {new_node['relation']}")

# ---------- 4. Write back ----------
with open(flow_file, 'w', encoding='utf-8') as f:
    json.dump(flow, f, indent=2, ensure_ascii=False)

# ---------- 5. Repackage ----------
temp_tfl = WORK_DIR.parent / "Perimetre Migration.tfl.new3"
if temp_tfl.exists():
    temp_tfl.unlink()
with zipfile.ZipFile(temp_tfl, 'w', zipfile.ZIP_DEFLATED) as z:
    for f in WORK_DIR.iterdir():
        z.write(f, arcname=f.name)
shutil.copy2(temp_tfl, FLOW_PATH)
temp_tfl.unlink()
shutil.rmtree(WORK_DIR)
print(f"\nWritten: {FLOW_PATH}")
print(f"Size: {FLOW_PATH.stat().st_size} bytes")
