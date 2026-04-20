"""Add 6 calculated fields to the Jira_Projet datasource."""
import zipfile, shutil
from pathlib import Path

TWBX = Path(r"C:\Users\quinson\Desktop\Claude\Tableau DWH\Dasboard suivi projet DataWarehouse.twbx")
WORK = Path(r"C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_calcs_work")

if WORK.exists(): shutil.rmtree(WORK)
WORK.mkdir()
with zipfile.ZipFile(TWBX) as z: z.extractall(WORK)
twb = next(WORK.glob("*.twb"))
content = twb.read_text(encoding='utf-8')

# Calculated fields for Jira_Projet datasource
# NB: [Parameters].[Param X] references params from the Parameters datasource
# Also: HTML-escape the formulas for XML safety (&quot; instead of ")
calcs = """      <column caption='Deadline Domaine' datatype='date' name='[Deadline Domaine]' role='dimension' type='ordinal'>
        <calculation class='tableau' formula='CASE [Domaine] WHEN &quot;Nexus&quot; THEN [Parameters].[Param Deadline Nexus] WHEN &quot;Plexus&quot; THEN [Parameters].[Param Deadline Plexus] ELSE [Parameters].[Param Deadline Autres] END' />
      </column>
      <column caption='Charge Realisee' datatype='real' name='[Charge Realisee]' role='measure' type='quantitative'>
        <calculation class='tableau' formula='IF [\u00c9tat] = &quot;Termin\u00e9&quot; THEN [Charge_Jours] ELSE 0 END' />
      </column>
      <column caption='Charge Restante' datatype='real' name='[Charge Restante]' role='measure' type='quantitative'>
        <calculation class='tableau' formula='IF [\u00c9tat] &lt;&gt; &quot;Termin\u00e9&quot; THEN [Charge_Jours] ELSE 0 END' />
      </column>
      <column caption='Mois Realisation' datatype='date' name='[Mois Realisation]' role='dimension' type='ordinal'>
        <calculation class='tableau' formula='DATETRUNC(&quot;month&quot;, [R\u00e9solu])' />
      </column>
      <column caption='Mois Planifie' datatype='date' name='[Mois Planifie]' role='dimension' type='ordinal'>
        <calculation class='tableau' formula='DATETRUNC(&quot;month&quot;, [Date d&apos;\u00e9ch\u00e9ance])' />
      </column>
      <column caption='Statut Livraison' datatype='string' name='[Statut Livraison]' role='dimension' type='nominal'>
        <calculation class='tableau' formula='IF { FIXED [Domaine] : SUM([Charge Restante])} = 0 THEN &quot;Livr\u00e9&quot; ELSEIF TODAY() &gt; [Deadline Domaine] THEN &quot;Retard&quot; ELSE &quot;Dans d\u00e9lai&quot; END' />
      </column>
"""

# Locate insertion point: right before <layout ...> in the Jira_Projet block
jstart = content.find("<datasource caption='Jira_Projet'")
jend   = content.find('</datasource>', jstart)
jira_block = content[jstart:jend]

layout_pos = jira_block.find('<layout ')
if layout_pos < 0:
    print("ERROR : <layout ...> not found in Jira block")
    exit(1)
absolute_insert_pos = jstart + layout_pos

new_content = content[:absolute_insert_pos] + calcs + "      " + content[absolute_insert_pos:]

twb.write_text(new_content, encoding='utf-8')

import xml.etree.ElementTree as ET
try:
    ET.parse(twb)
    print("XML: VALID")
except ET.ParseError as e:
    print(f"XML ERROR: {e}"); exit(1)

tmp = WORK.parent / "twbx_tmp.twbx"
if tmp.exists(): tmp.unlink()
with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as z:
    for f in WORK.rglob('*'):
        if f.is_file():
            z.write(f, arcname=f.relative_to(WORK))
shutil.copy2(tmp, TWBX); tmp.unlink(); shutil.rmtree(WORK)
print(f"Written: {TWBX}")
print("6 champs calcules ajoutes:")
print("  - Deadline Domaine")
print("  - Charge Realisee")
print("  - Charge Restante")
print("  - Mois Realisation")
print("  - Mois Planifie")
print("  - Statut Livraison")
