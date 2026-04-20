"""
Fix: remove or adjust nodeProperties for the output node to use a mode
compatible with Hyper file output (create/replace, not truncate-table).
"""
import json
import zipfile
import shutil
from pathlib import Path

FLOW_PATH = Path(r"C:\Users\quinson\Documents\Mon dossier Tableau Prep\Flux\Perimetre Migration.tfl")
WORK_DIR = Path(r"C:\Users\quinson\Desktop\Claude\Tableau DWH\tfl_work2")

OUTPUT_NODE_ID = "c449e97c-80e0-46c0-b489-9e08b7429ec9"

if WORK_DIR.exists():
    shutil.rmtree(WORK_DIR)
WORK_DIR.mkdir(parents=True)
with zipfile.ZipFile(FLOW_PATH, 'r') as z:
    z.extractall(WORK_DIR)

flow_file = WORK_DIR / "flow"
with open(flow_file, 'r', encoding='utf-8') as f:
    flow = json.load(f)

# Show current nodeProperties for the output node
props = flow.get("nodeProperties", {}).get(OUTPUT_NODE_ID, {})
print(f"Current nodeProperties for output node:")
print(json.dumps(props, indent=2))

# The Superstore sample (which works with WriteToHyper) has NO nodeProperties
# for the Hyper output node. Let's just remove ours.
if OUTPUT_NODE_ID in flow.get("nodeProperties", {}):
    del flow["nodeProperties"][OUTPUT_NODE_ID]
    print(f"Removed nodeProperties for {OUTPUT_NODE_ID}")

with open(flow_file, 'w', encoding='utf-8') as f:
    json.dump(flow, f, indent=2, ensure_ascii=False)
print("Flow rewritten")

# Repackage
temp_tfl = WORK_DIR.parent / "Perimetre Migration.tfl.new2"
if temp_tfl.exists():
    temp_tfl.unlink()
with zipfile.ZipFile(temp_tfl, 'w', zipfile.ZIP_DEFLATED) as z:
    for f in WORK_DIR.iterdir():
        z.write(f, arcname=f.name)
shutil.copy2(temp_tfl, FLOW_PATH)
temp_tfl.unlink()
shutil.rmtree(WORK_DIR)
print(f"Written: {FLOW_PATH}")
