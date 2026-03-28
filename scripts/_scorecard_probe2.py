"""
Probe: get all column names from both Scorecard CSVs and determine
which KC institutions are in the dataset. Outputs column lists for migration.
"""
import sqlite3
import zipfile
import re
import pandas as pd

# Get KC unitids
conn = sqlite3.connect("db/haystack.db")
rows = conn.execute(
    "SELECT unitid, name FROM organization WHERE unitid IS NOT NULL AND org_type='training'"
).fetchall()
conn.close()
our_unitids = {str(r[0]).strip(): r[1] for r in rows}

z = zipfile.ZipFile("data/raw/scorecard/College_Scorecard_Raw_Data_03232026.zip")

# ----- Institution file -----
with z.open("Most-Recent-Cohorts-Institution.csv") as f:
    inst_full = pd.read_csv(f, dtype=str, low_memory=False)

kc_inst = inst_full[inst_full["UNITID"].isin(our_unitids.keys())].copy()
print(f"Institution file: {len(inst_full)} total rows, {len(inst_full.columns)} columns")
print(f"KC subset: {len(kc_inst)} rows")
print()

# Column type analysis
def sqlite_type(col_data):
    """Infer SQLite type from non-null, non-PS values."""
    vals = col_data[~col_data.isin(["PrivacySuppressed", "PS", "NULL", ""])]
    vals = vals.dropna()
    if vals.empty:
        return "TEXT"
    try:
        vals.astype(float)
        # Check if all are integers
        if all(v == str(int(float(v))) for v in vals.iloc[:5] if v == v):
            return "INTEGER"
        return "REAL"
    except (ValueError, TypeError):
        return "TEXT"

print("=== Column types for scorecard_institution table ===")
col_defs = []
for col in inst_full.columns:
    t = sqlite_type(kc_inst[col] if col in kc_inst.columns else inst_full[col].iloc[:100])
    safe_col = col.lower().replace("-", "_")
    col_defs.append((safe_col, t, col))

for safe_col, t, orig in col_defs[:30]:
    print(f"  {safe_col:50s} {t:10s} (orig: {orig})")
print(f"  ... {len(col_defs)} total columns")

print()
print("=== Non-suppressed data rate for key columns in KC subset ===")
key_checks = ["UNITID", "INSTNM", "MD_EARN_WNE_P6", "MD_EARN_WNE_P10",
              "C150_4", "C150_L4", "PCTPELL", "GRAD_DEBT_MDN",
              "RPY_3YR_RT", "COSTT4_A", "PCTFLOAN"]
for col in key_checks:
    if col in kc_inst.columns:
        total = len(kc_inst)
        null_ps = kc_inst[col].isin(["PrivacySuppressed", "PS", ""]) | kc_inst[col].isna()
        available = total - null_ps.sum()
        print(f"  {col:35s}: {available}/{total} ({available/total*100:.0f}%) available")

# ----- FoS file -----
print()
with z.open("Most-Recent-Cohorts-Field-of-Study.csv") as f:
    fos_full = pd.read_csv(f, dtype=str, low_memory=False)

kc_fos = fos_full[fos_full["UNITID"].isin(our_unitids.keys())].copy()
print(f"FoS file: {len(fos_full)} total rows, {len(fos_full.columns)} columns")
print(f"KC subset: {len(kc_fos)} rows")
print()
print("FoS columns:")
for col in fos_full.columns[:50]:
    print(f"  {col}")

print()
print("FoS CIPCODE sample (first 20 KC rows):")
print(kc_fos[["UNITID","INSTNM","CIPCODE","CIPDESC","CREDLEV","CREDDESC"]].head(20).to_string())
