"""Find what 'Action (Statut Global)', 'Inclusions (...)', 'Tooltip (Projet)' are
in the original twb, and find the Burn-up filter on the pivot col."""
import zipfile

ORIG = r"C:\Users\quinson\Desktop\Claude\Tableau DWH\Dasboard suivi projet DataWarehouse - BEFORE hyper.twbx"
with zipfile.ZipFile(ORIG) as z:
    twb = [n for n in z.namelist() if n.endswith('.twb')][0]
    content = z.open(twb).read().decode('utf-8')
lines = content.split('\n')

print("=== 'Action (Statut Global)' references ===")
for i, ln in enumerate(lines):
    if 'Action (Statut Global)' in ln:
        print(f"L{i+1}: {ln.strip()[:300]}")

print()
print("=== 'Inclusions (Date' references ===")
for i, ln in enumerate(lines):
    if 'Inclusions (Date' in ln:
        print(f"L{i+1}: {ln.strip()[:300]}")

print()
print("=== 'Tooltip (Projet)' references ===")
for i, ln in enumerate(lines):
    if 'Tooltip (Projet)' in ln:
        print(f"L{i+1}: {ln.strip()[:300]}")
