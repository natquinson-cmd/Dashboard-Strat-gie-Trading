"""
Fix: change the output path of the WriteToHyper node so it writes to a
different file from the input (Prep refuses input == output for safety).
"""
import json, zipfile, shutil
from pathlib import Path

FLOW_PATH = Path(r"C:\Users\quinson\Documents\Mon dossier Tableau Prep\Flux\Perimetre Migration.tfl")
WORK_DIR = Path(r"C:\Users\quinson\Desktop\Claude\Tableau DWH\tfl_work_outpath")

OUTPUT_NODE_ID = "c449e97c-80e0-46c0-b489-9e08b7429ec9"

NEW_HYPER_OUT = r"\\scxdata\CommunOS_BI$\C Courant\Datasources\ISCS-BI\SuiviProjetDWH\flatfiles\Perimetre_Migration_Updated.hyper"
NEW_TDS_OUT  = r"\\scxdata\CommunOS_BI$\C Courant\Datasources\ISCS-BI\SuiviProjetDWH\flatfiles\Perimetre_Migration_Updated.tds"

if WORK_DIR.exists():
    shutil.rmtree(WORK_DIR)
WORK_DIR.mkdir(parents=True)
with zipfile.ZipFile(FLOW_PATH, 'r') as z:
    z.extractall(WORK_DIR)

flow_file = WORK_DIR / "flow"
with open(flow_file, 'r', encoding='utf-8') as f:
    flow = json.load(f)

node = flow["nodes"][OUTPUT_NODE_ID]
print(f"Old hyperOutputFile: {node.get('hyperOutputFile')}")
node["hyperOutputFile"] = NEW_HYPER_OUT
node["tdsOutput"] = NEW_TDS_OUT
print(f"New hyperOutputFile: {node['hyperOutputFile']}")

with open(flow_file, 'w', encoding='utf-8') as f:
    json.dump(flow, f, indent=2, ensure_ascii=False)

temp_tfl = WORK_DIR.parent / "Perimetre Migration.tfl.outpath"
if temp_tfl.exists():
    temp_tfl.unlink()
with zipfile.ZipFile(temp_tfl, 'w', zipfile.ZIP_DEFLATED) as z:
    for ff in WORK_DIR.iterdir():
        z.write(ff, arcname=ff.name)
shutil.copy2(temp_tfl, FLOW_PATH)
temp_tfl.unlink()
shutil.rmtree(WORK_DIR)
print(f"Written: {FLOW_PATH}")
