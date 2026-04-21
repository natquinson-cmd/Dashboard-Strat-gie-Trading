"""Create 'KPI Capacite' worksheet by duplicating 'Dernier refresh' as a template.
This is a proof-of-concept: minimal BAN showing the Capacite Dispo parameter."""
import zipfile, shutil, uuid, re
from pathlib import Path

TWBX = Path(r"C:\Users\quinson\Desktop\Claude\Tableau DWH\Dasboard suivi projet DataWarehouse.twbx")
WORK = Path(r"C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_kpi_work")
if WORK.exists(): shutil.rmtree(WORK)
WORK.mkdir()
with zipfile.ZipFile(TWBX) as z: z.extractall(WORK)
twb = next(WORK.glob("*.twb"))
content = twb.read_text(encoding='utf-8')

# Jira datasource name
JIRA_DS = "sqlproxy.01iac1b080v34315jtrfp12bqdgh"

# New worksheet name + UUID
NEW_NAME = "KPI Capacite"
NEW_UUID = "{" + str(uuid.uuid4()).upper() + "}"

# Build the worksheet XML - minimal BAN using Capacite Dispo parameter
# We reference [Parameters].[Param Capacite Dispo] - actually just [Param Capacite Dispo] (global)
ws_xml = f'''    <worksheet name='{NEW_NAME}'>
      <table>
        <view>
          <datasources>
            <datasource caption='Parameters' name='Parameters' />
            <datasource caption='Jira_Projet' name='{JIRA_DS}' />
          </datasources>
          <datasource-dependencies datasource='Parameters'>
            <column caption='Capacite Dispo (j)' datatype='integer' name='[Param Capacite Dispo]' param-domain-type='any' role='measure' type='quantitative' value='1440'>
              <calculation class='tableau' formula='1440' />
            </column>
            <column caption='Texte Capacite' datatype='string' name='[Calculation_KPI_Capacite_Text]' role='dimension' type='nominal'>
              <calculation class='tableau' formula='STR([Param Capacite Dispo]) + &quot; j&quot;' />
            </column>
            <column-instance column='[Calculation_KPI_Capacite_Text]' derivation='None' name='[none:Calculation_KPI_Capacite_Text:nk]' pivot='key' type='nominal' />
          </datasource-dependencies>
          <aggregation value='true' />
        </view>
        <style>
          <style-rule element='table'>
            <format attr='background-color' value='#0f172a' />
          </style-rule>
        </style>
        <panes>
          <pane selection-relaxation-option='selection-relaxation-allow'>
            <view>
              <breakdown value='auto' />
            </view>
            <mark class='Text' />
            <encodings>
              <text column='[Parameters].[none:Calculation_KPI_Capacite_Text:nk]' />
            </encodings>
            <customized-tooltip>
              <formatted-text />
            </customized-tooltip>
            <customized-label>
              <formatted-text>
                <run fontcolor='#ffffff' fontname='Tableau Bold' fontsize='32'><![CDATA[<[Parameters].[none:Calculation_KPI_Capacite_Text:nk]>]]></run>
              </formatted-text>
            </customized-label>
            <style>
              <style-rule element='mark'>
                <format attr='mark-labels-show' value='true' />
                <format attr='mark-labels-cull' value='true' />
              </style-rule>
            </style>
          </pane>
        </panes>
        <rows />
        <cols />
      </table>
      <simple-id uuid='{NEW_UUID}' />
    </worksheet>
'''

# Insert before </worksheets>
ws_close = content.find("</worksheets>")
if ws_close < 0:
    print("ERROR: </worksheets> not found"); exit(1)
content = content[:ws_close] + ws_xml + content[ws_close:]
print(f"Inserted worksheet '{NEW_NAME}' before </worksheets>")

# Add window for the new worksheet
win_xml = f"    <window class='worksheet' name='{NEW_NAME}'>\n      <cards />\n    </window>\n"
wins_close = content.find("</windows>")
if wins_close < 0:
    print("ERROR: </windows> not found"); exit(1)
content = content[:wins_close] + win_xml + content[wins_close:]
print(f"Inserted window for '{NEW_NAME}' before </windows>")

twb.write_text(content, encoding='utf-8')

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
