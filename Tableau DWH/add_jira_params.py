"""Add 5 parameters (Capacite, Ratio SP, 3 deadlines) to the twbx."""
import zipfile, shutil
from pathlib import Path

TWBX = Path(r"C:\Users\quinson\Desktop\Claude\Tableau DWH\Dasboard suivi projet DataWarehouse.twbx")
WORK = Path(r"C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_params_work")

if WORK.exists(): shutil.rmtree(WORK)
WORK.mkdir()
with zipfile.ZipFile(TWBX) as z: z.extractall(WORK)
twb = next(WORK.glob("*.twb"))
content = twb.read_text(encoding='utf-8')

# New params XML block to insert just before </datasource> of Parameters block
new_params = """      <column caption='Capacite Dispo (j)' datatype='integer' name='[Param Capacite Dispo]' param-domain-type='any' role='measure' type='quantitative' value='1440'>
        <calculation class='tableau' formula='1440' />
      </column>
      <column caption='Ratio SP vers Jours' datatype='integer' name='[Param Ratio SP]' param-domain-type='any' role='measure' type='quantitative' value='50'>
        <calculation class='tableau' formula='50' />
      </column>
      <column caption='Deadline Autres' datatype='date' name='[Param Deadline Autres]' param-domain-type='any' role='measure' type='quantitative' value='#2026-01-31#'>
        <calculation class='tableau' formula='#2026-01-31#' />
      </column>
      <column caption='Deadline Nexus' datatype='date' name='[Param Deadline Nexus]' param-domain-type='any' role='measure' type='quantitative' value='#2026-12-31#'>
        <calculation class='tableau' formula='#2026-12-31#' />
      </column>
      <column caption='Deadline Plexus' datatype='date' name='[Param Deadline Plexus]' param-domain-type='any' role='measure' type='quantitative' value='#2027-12-31#'>
        <calculation class='tableau' formula='#2027-12-31#' />
      </column>
"""

# Find the Parameters datasource closing tag
pstart = content.find("<datasource hasconnection='false' inline='true' name='Parameters'")
if pstart < 0:
    print("Parameters block NOT found!"); exit(1)
pend = content.find('</datasource>', pstart)
# Insert new_params just before </datasource>
new_content = content[:pend] + new_params + "    " + content[pend:]

# Write back
twb.write_text(new_content, encoding='utf-8')

# Validate XML
import xml.etree.ElementTree as ET
try:
    ET.parse(twb)
    print("XML: VALID")
except ET.ParseError as e:
    print(f"XML ERROR: {e}"); exit(1)

# Repackage
tmp = WORK.parent / "twbx_tmp.twbx"
if tmp.exists(): tmp.unlink()
with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as z:
    for f in WORK.rglob('*'):
        if f.is_file():
            z.write(f, arcname=f.relative_to(WORK))
shutil.copy2(tmp, TWBX); tmp.unlink(); shutil.rmtree(WORK)
print(f"Written: {TWBX}")
print(f"Ajoute 5 parametres : Capacite Dispo, Ratio SP, Deadline (Autres/Nexus/Plexus)")
