"""More detailed inspection of twbx XML connections and federated datasources."""
import zipfile, re
from pathlib import Path

TWBX = Path(r"C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse.twbx")
with zipfile.ZipFile(TWBX, 'r') as z:
    twb_name = [n for n in z.namelist() if n.endswith('.twb')][0]
    with z.open(twb_name) as f:
        content = f.read().decode('utf-8')

# Connection tags including multiline (greedy until > but allow newlines)
print("=== <connection ...>  blocks (multiline-aware) ===")
for m in re.finditer(r"<connection [^>]*>", content, re.DOTALL):
    line = content[:m.start()].count('\n') + 1
    snip = m.group(0).replace('\n', ' ')[:300]
    print(f"Line {line}: {snip}")

print()
print("=== <named-connection> tags ===")
for m in re.finditer(r"<named-connection [^>]*>", content, re.DOTALL):
    line = content[:m.start()].count('\n') + 1
    snip = m.group(0).replace('\n', ' ')[:300]
    print(f"Line {line}: {snip}")

print()
print("=== Lines containing 'sqlproxy' or 'tableau.epfl' ===")
lines = content.split('\n')
for i, ln in enumerate(lines):
    if 'sqlproxy' in ln or 'tableau.epfl.ch' in ln or 'Perimetre_MigrationExcel' in ln:
        print(f"Line {i+1}: {ln.strip()[:200]}")
        if i > 100: break  # avoid spam
