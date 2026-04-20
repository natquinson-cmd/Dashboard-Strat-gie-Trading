"""Compare the groups before and after migration."""
import zipfile

OLD = r"C:\Users\quinson\Desktop\Claude\Tableau DWH\Dasboard suivi projet DataWarehouse - BEFORE hyper.twbx"
NEW = r"C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse.twbx"

def load(p):
    with zipfile.ZipFile(p) as z:
        twb = [n for n in z.namelist() if n.endswith('.twb')][0]
        return z.open(twb).read().decode('utf-8')

old = load(OLD)
new = load(NEW)

for label, c in [("OLD", old), ("NEW", new)]:
    print(f"=== {label} ===")
    print(f"  '<group ' count: {c.count('<group ')}")
    print(f"  'Action (Statut Global)': {c.count('Action (Statut Global)')}")
    print(f"  'Inclusions (Date': {c.count('Inclusions (Date')}")
    print(f"  'Tooltip (Projet)': {c.count('Tooltip (Projet)')}")
    print()

# Look for the lines around line 2875 (Action group) in NEW
new_lines = new.split('\n')
print("=== NEW: lines mentioning 'Action (Statut Global)' (first 5) ===")
n = 0
for i, ln in enumerate(new_lines):
    if 'Action (Statut Global)' in ln:
        print(f"L{i+1}: {ln.strip()[:200]}")
        n += 1
        if n >= 5: break
