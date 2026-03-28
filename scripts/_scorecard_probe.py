"""Quick probe: match KC IPEDS unitids against College Scorecard."""
import sqlite3
import zipfile
import pandas as pd

conn = sqlite3.connect("db/haystack.db")
rows = conn.execute(
    "SELECT unitid, name FROM organization WHERE unitid IS NOT NULL AND org_type='training'"
).fetchall()
conn.close()

our_unitids = {str(r[0]): r[1] for r in rows}
print(f"KC providers with unitids in DB: {len(our_unitids)}")

z = zipfile.ZipFile(r"data/raw/scorecard/College_Scorecard_Raw_Data_03232026.zip")
with z.open("Most-Recent-Cohorts-Institution.csv") as f:
    inst = pd.read_csv(f, dtype=str)

matched = inst[inst["UNITID"].isin(our_unitids.keys())].copy()
print(f"Matched in scorecard: {len(matched)} of {len(our_unitids)}")
print()

key_fields = [
    "UNITID", "INSTNM",
    "MD_EARN_WNE_P6", "MD_EARN_WNE_P10",
    "C150_4", "C150_L4",
    "PCTPELL", "PCTFLOAN",
    "GRAD_DEBT_MDN", "WDRAW_DEBT_MDN",
    "RPY_3YR_RT", "COMPL_RPY_3YR_RT",
]
existing = [c for c in key_fields if c in matched.columns]
print(matched[existing].to_string())

print("\n\n=== Field-of-Study sample for KC providers ===")
with z.open("Most-Recent-Cohorts-Field-of-Study.csv") as f:
    fos = pd.read_csv(f, dtype=str)

fos_kc = fos[fos["UNITID"].isin(our_unitids.keys())].copy()
print(f"FoS rows for KC providers: {len(fos_kc)}")
fos_key = ["UNITID","INSTNM","CIPCODE","CIPDESC","CREDLEV","CREDDESC",
           "EARN_MDN_HI_1YR","EARN_MDN_HI_2YR","EARN_COUNT_WNE_HI_2YR"]
fos_existing = [c for c in fos_key if c in fos_kc.columns]
print(fos_kc[fos_existing].head(20).to_string())
