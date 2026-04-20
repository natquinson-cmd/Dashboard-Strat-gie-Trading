"""
STEP 3 v2: Replace input 'Perimetre_Migration 2' using the exact format
Prep generated in the test flow for reading a .hyper file.
"""
import json
import zipfile
import shutil
import copy
from pathlib import Path

FLOW_PATH = Path(r"C:\Users\quinson\Documents\Mon dossier Tableau Prep\Flux\Perimetre Migration.tfl")
TEST_PATH = Path(r"C:\Users\quinson\Documents\Mon dossier Tableau Prep\Flux\Perimetre Migration Test.tfl")
WORK_DIR = Path(r"C:\Users\quinson\Desktop\Claude\Tableau DWH\tfl_work3v2")

INPUT_NODE_ID = "0e3e735c-b429-4b0f-b617-2628718e686c"
OLD_CONN_ID = "3192c8b4-41bb-4d6d-b7e5-7e6ddc116c14"
TEST_HYPER_NODE_ID = "d904895e-46d3-4539-9ba6-fe16a068dbb1"
TEST_HYPER_CONN_ID = "7d32e3d1-72db-409a-9268-67b01228e246"

# 1. Read test flow to get the exact LoadSql node + connection
with zipfile.ZipFile(TEST_PATH, 'r') as z:
    with z.open('flow') as f:
        test_flow = json.load(f)
test_node = copy.deepcopy(test_flow['nodes'][TEST_HYPER_NODE_ID])
test_conn = copy.deepcopy(test_flow['connections'][TEST_HYPER_CONN_ID])
print(f"Grabbed test LoadSql node + connection")
print(f"  Node fields: {len(test_node['fields'])}")

# 2. Extract the real flow
if WORK_DIR.exists():
    shutil.rmtree(WORK_DIR)
WORK_DIR.mkdir(parents=True)
with zipfile.ZipFile(FLOW_PATH, 'r') as z:
    z.extractall(WORK_DIR)
flow_file = WORK_DIR / "flow"
with open(flow_file, 'r', encoding='utf-8') as f:
    flow = json.load(f)

# 3. Preserve nextNodes and name from original input node
old_node = flow['nodes'][INPUT_NODE_ID]
preserved_next_nodes = old_node.get('nextNodes', [])
print(f"Preserving {len(preserved_next_nodes)} nextNodes from old input")

# 4. Build the new input node: copy test format, but keep the old ID and nextNodes
new_node = copy.deepcopy(test_node)
new_node['id'] = INPUT_NODE_ID  # keep same ID so references in other parts stay valid
new_node['name'] = 'Perimetre_Migration 2'
new_node['nextNodes'] = preserved_next_nodes
new_node['connectionId'] = OLD_CONN_ID  # reuse the original connection ID

# 5. Replace the connection: keep the OLD connection ID but switch to hyper format
new_conn = copy.deepcopy(test_conn)
new_conn['id'] = OLD_CONN_ID  # keep old connection ID
# connectionAttributes from test has the correct format: dbname + class=hyper
print(f"New connection attributes: {new_conn['connectionAttributes']}")

# Apply
flow['nodes'][INPUT_NODE_ID] = new_node
flow['connections'][OLD_CONN_ID] = new_conn

# 6. Write back and repackage
with open(flow_file, 'w', encoding='utf-8') as f:
    json.dump(flow, f, indent=2, ensure_ascii=False)

temp_tfl = WORK_DIR.parent / "Perimetre Migration.tfl.new3v2"
if temp_tfl.exists():
    temp_tfl.unlink()
with zipfile.ZipFile(temp_tfl, 'w', zipfile.ZIP_DEFLATED) as z:
    for ff in WORK_DIR.iterdir():
        z.write(ff, arcname=ff.name)
shutil.copy2(temp_tfl, FLOW_PATH)
temp_tfl.unlink()
shutil.rmtree(WORK_DIR)
print(f"\nWritten: {FLOW_PATH}")
print(f"Size: {FLOW_PATH.stat().st_size} bytes")
