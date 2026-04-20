"""Remove the PublishExtract node from the Prep flow. The responsable's
consolidation_migration_dwh.tfl flow handles server publication downstream."""
import json, zipfile, shutil
from pathlib import Path

FLOW_PATH = Path(r"C:\Users\quinson\Documents\Mon dossier Tableau Prep\Flux\Perimetre Migration.tfl")
WORK_DIR = Path(r"C:\Users\quinson\Desktop\Claude\Tableau DWH\tfl_rm_publish")

PIVOT_NODE_ID = "29776b16-bb88-4004-904b-80e25eed370d"

if WORK_DIR.exists():
    shutil.rmtree(WORK_DIR)
WORK_DIR.mkdir()
with zipfile.ZipFile(FLOW_PATH, 'r') as z:
    z.extractall(WORK_DIR)
flow_file = WORK_DIR / "flow"
with open(flow_file, 'r', encoding='utf-8') as f:
    flow = json.load(f)

# Find all PublishExtract nodes and remove them
publish_ids = [nid for nid, n in flow['nodes'].items() if n.get('nodeType') == '.v1.PublishExtract']
print(f"PublishExtract nodes found: {publish_ids}")

for pid in publish_ids:
    del flow['nodes'][pid]
    print(f"  Removed {pid[:8]}")

# Clean up any nextNodes references pointing to removed publish nodes
for nid, n in flow['nodes'].items():
    nn = n.get('nextNodes', [])
    filtered = [x for x in nn if x['nextNodeId'] not in publish_ids]
    if len(filtered) != len(nn):
        print(f"  Cleaned {nid[:8]} nextNodes: {len(nn)} -> {len(filtered)}")
    n['nextNodes'] = filtered

# Save and repackage
with open(flow_file, 'w', encoding='utf-8') as f:
    json.dump(flow, f, indent=2, ensure_ascii=False)

tmp_tfl = WORK_DIR.parent / "Perimetre Migration.tfl.rmpub"
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
