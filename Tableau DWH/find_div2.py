"""Find all /2 divisions in formulas of the original twbx."""
import zipfile, re

ORIG = r"C:\Users\quinson\Desktop\Claude\Tableau DWH\Dasboard suivi projet DataWarehouse - BEFORE hyper.twbx"
with zipfile.ZipFile(ORIG) as z:
    twb = [n for n in z.namelist() if n.endswith('.twb')][0]
    content = z.open(twb).read().decode('utf-8')

print("=== Calculation formulas with /2 ===")
seen = set()
for m in re.finditer(r"<calculation column='\[([^]]+)\]' formula='([^']*)'", content):
    col, formula = m.group(1), m.group(2)
    # Match standalone /2 (not part of /20 or /22 etc)
    if re.search(r"/\s*2\b", formula):
        key = (col, formula[:200])
        if key in seen:
            continue
        seen.add(key)
        print(f"COL: {col}")
        print(f"  {formula[:300]}")
        print()

# Also search for column captions for these IDs
print()
print("=== Column captions for /2 calculations ===")
calc_ids = set(c.split("(copie)")[0] for c, _ in seen)
for col, _ in seen:
    pat = re.compile(r"<column [^>]*caption='([^']+)'[^>]*name='\[" + re.escape(col) + r"\]'")
    matches = pat.findall(content)
    cap = matches[0] if matches else "(no caption)"
    print(f"  [{col}]  ->  caption: '{cap}'")
