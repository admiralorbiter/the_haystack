"""
Probe: identify the most valuable columns across the institution file categories.
Groups by prefix to understand what's available.
"""
import sqlite3
import zipfile
import pandas as pd
from collections import Counter

conn = sqlite3.connect("db/haystack.db")
rows = conn.execute(
    "SELECT unitid, name FROM organization WHERE unitid IS NOT NULL AND org_type='training'"
).fetchall()
conn.close()
our_unitids = {str(r[0]).strip(): r[1] for r in rows}

z = zipfile.ZipFile("data/raw/scorecard/College_Scorecard_Raw_Data_03232026.zip")

with z.open("Most-Recent-Cohorts-Institution.csv") as f:
    # Read only the KC rows
    inst_full = pd.read_csv(f, dtype=str, low_memory=False)

kc_inst = inst_full[inst_full["UNITID"].isin(our_unitids.keys())].copy()
print(f"KC: {len(kc_inst)} rows x {len(kc_inst.columns)} cols")
print()

# Check SQLite column limit
print(f"SQLite column limit: 2000")
print(f"Our columns: {len(kc_inst.columns)} — need to split!")
print()

# Group by prefix
prefixes = Counter()
for col in kc_inst.columns:
    prefix = col.split("_")[0] if "_" in col else col
    prefixes[prefix] += 1

print("Column groups by prefix (top 30):")
for p, n in prefixes.most_common(30):
    print(f"  {p:20s}: {n:4d} cols")

print()

# Identify columns with >50% non-suppressed data in KC subset
print("=== Columns with >50% non-suppressed data in KC subset ===")
good_cols = []
for col in kc_inst.columns:
    null_ps = kc_inst[col].isin(["PrivacySuppressed", "PS", "NULL", ""]) | kc_inst[col].isna()
    available_pct = (len(kc_inst) - null_ps.sum()) / len(kc_inst)
    if available_pct > 0.5:
        good_cols.append((col, available_pct))

print(f"Found {len(good_cols)} columns with >50% data in KC")
print()
print("High-value subset (>80% available):")
for col, pct in sorted(good_cols, key=lambda x: -x[1])[:60]:
    print(f"  {col:50s} {pct:.0%}")

print()
print(f"\nTotal actionable columns (>50%): {len(good_cols)}")

# Also check: can we store KC data as a single parquet?
kc_inst.to_parquet("data/raw/scorecard/kc_scorecard_institution.parquet", index=False)
print(f"\nWritten KC institution parquet: data/raw/scorecard/kc_scorecard_institution.parquet")
