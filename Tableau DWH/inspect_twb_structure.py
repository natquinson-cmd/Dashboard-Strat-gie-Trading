"""
Inspect the twbx structure: locate the sqlproxy connection block,
the cols mapping, the Intervenant 1/2 formulas, and the published-datasource references.
This is read-only — does NOT modify anything.
"""
import zipfile, re
from pathlib import Path

TWBX = Path(r"C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse.twbx")

# Extract twb XML
with zipfile.ZipFile(TWBX, 'r') as z:
    twb_name = [n for n in z.namelist() if n.endswith('.twb')][0]
    print(f"TWB file in twbx: {twb_name}")
    with z.open(twb_name) as f:
        content = f.read().decode('utf-8')

print(f"Total length: {len(content)}")
print()

# Locate connection blocks
print("=== <connection ...> tags ===")
for m in re.finditer(r"<connection [^/>]*?>", content):
    line = content[:m.start()].count('\n') + 1
    print(f"Line {line}: {m.group(0)[:200]}")

print()
print("=== <repository-location ...> tags (published datasources) ===")
for m in re.finditer(r"<repository-location [^/>]*?/>", content):
    line = content[:m.start()].count('\n') + 1
    print(f"Line {line}: {m.group(0)[:200]}")

print()
print("=== Intervenant 1 / 2 formulas (column captions) ===")
# Find columns where caption is Intervenant 1 or 2
for m in re.finditer(r"<column [^>]*caption='Intervenant [12]'[^>]*>", content):
    line = content[:m.start()].count('\n') + 1
    print(f"Line {line}: {m.group(0)[:300]}")
    # Read next few lines for the formula
    end = content.find('</column>', m.end())
    if end > 0:
        block = content[m.end():end]
        for fm in re.finditer(r"formula='([^']*)'", block):
            print(f"  Formula: {fm.group(1)[:300]}")

print()
print("=== References to 'tableau crois' (pivot field names) ===")
cnt = content.count('tableau crois')
print(f"Total occurrences: {cnt}")

print()
print("=== <relation ...> tags ===")
for m in re.finditer(r"<relation [^/>]*?/?>", content):
    line = content[:m.start()].count('\n') + 1
    print(f"Line {line}: {m.group(0)[:200]}")
