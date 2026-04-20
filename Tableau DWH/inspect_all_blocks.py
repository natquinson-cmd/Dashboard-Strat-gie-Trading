"""Map all the locations in the twbx where sqlproxy/Perimetre_Migration is referenced."""
import zipfile
from pathlib import Path

TWBX = Path(r"C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse.twbx")
with zipfile.ZipFile(TWBX) as z:
    twb_name = [n for n in z.namelist() if n.endswith('.twb')][0]
    content = z.open(twb_name).read().decode('utf-8')

lines = content.split('\n')

print("Total lines:", len(lines))
print()

# Find all <connection class='sqlproxy'> blocks
print("=== <connection class='sqlproxy'> ===")
for i, ln in enumerate(lines):
    if "class='sqlproxy'" in ln:
        print(f"L{i+1}: {ln.strip()[:200]}")

print()
print("=== <relation name='sqlproxy'> ===")
for i, ln in enumerate(lines):
    if "<relation name='sqlproxy'" in ln:
        print(f"L{i+1}: {ln.strip()[:200]}")

print()
print("=== Datasources containing the published Perimetre_MigrationExcel ===")
for i, ln in enumerate(lines):
    if "Perimetre_MigrationExcel" in ln:
        print(f"L{i+1}: {ln.strip()[:200]}")

# Count metadata-records mentioning the pivot columns
print()
print("=== Pivot column references ===")
print(f"  Lines with 'Noms des champs de tableau': {sum(1 for l in lines if 'Noms des champs de tableau' in l)}")
print(f"  Lines with 'Valeurs du champ de tableau': {sum(1 for l in lines if 'Valeurs du champ de tableau' in l)}")

# Look for parent-name='[sqlproxy]'
print()
print("=== parent-name references ===")
target1 = "parent-name='[sqlproxy]'"
target2 = "parent-name='[Perimetre_Migration]'"
print(f"  {target1}: {sum(1 for l in lines if target1 in l)}")
print(f"  {target2}: {sum(1 for l in lines if target2 in l)}")

# Check the cols map count
print()
print("=== Column maps (in <cols> blocks) ===")
print(f"  '<map key=' lines: {sum(1 for l in lines if '<map key=' in l)}")
print(f"  Lines with [sqlproxy].[: {sum(1 for l in lines if '[sqlproxy].[' in l)}")

# REF BI01 / REF BI02 column references
print()
print("=== REF BI01 / REF BI02 references ===")
print(f"  'REF BI01': {sum(1 for l in lines if 'REF BI01' in l)}")
print(f"  'REF BI02': {sum(1 for l in lines if 'REF BI02' in l)}")
print(f"  '[REF BI01]': {sum(1 for l in lines if '[REF BI01]' in l)}")

# Find datasource blocks (start tags)
print()
print("=== <datasource ... inline='true'> blocks ===")
for i, ln in enumerate(lines):
    if "<datasource " in ln and "inline" in ln:
        print(f"L{i+1}: {ln.strip()[:200]}")
