"""Inspect the user's test .twb to extract the exact format Tableau uses for a Hyper file connection."""
from pathlib import Path
import re

p = Path(r"C:\Users\quinson\Desktop\Claude\Test Hyper.twb")
content = p.read_text(encoding='utf-8')
lines = content.split('\n')

# 1. Find the datasource block
print("=== <datasource ...> tags ===")
for i, ln in enumerate(lines):
    if '<datasource ' in ln and 'inline' in ln:
        print(f"L{i+1}: {ln.strip()[:200]}")

# 2. Find connection-related elements
print("\n=== Connection-related XML (lines around connection) ===")
for i, ln in enumerate(lines):
    if any(k in ln for k in ['<connection ', '<named-connection', '<named-connections', '<relation ', '<cols>', 'class=\'hyper\'', 'class="hyper"']):
        print(f"L{i+1}: {ln.strip()[:300]}")

# 3. Print the first 60 lines to see overall structure
print("\n=== First 60 lines of the .twb ===")
for i, ln in enumerate(lines[:60]):
    print(f"L{i+1}: {ln.rstrip()[:300]}")
