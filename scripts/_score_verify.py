"""Quick DB verification after scorecard load."""
import sqlite3

conn = sqlite3.connect("db/haystack.db")

tables = ["scorecard_institution", "scorecard_field_of_study", "dataset_source"]
for t in tables:
    try:
        n = conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        print(f"  {t}: {n} rows")
    except Exception as e:
        print(f"  {t}: ERROR - {e}")

print()
print("Sample institution data (key cols):")
rows = conn.execute(
    "SELECT UNITID, INSTNM, MD_EARN_WNE_P6, MD_EARN_WNE_P10, GRAD_DEBT_MDN, RPY_3YR_RT, C150_4, C150_L4 "
    "FROM scorecard_institution LIMIT 8"
).fetchall()
for r in rows:
    print(f"  {r[0]}  {str(r[1])[:30]:30s}  earn6={r[2]}  debt={r[4]}  c150_4={r[6]}  c150_l4={r[7]}")

print()
print("FoS sample (non-suppressed earnings):")
fos = conn.execute(
    "SELECT UNITID, CIPCODE_NORM, CIPDESC, CREDDESC, EARN_MDN_HI_2YR, EARN_MDN_4YR_NAT "
    'FROM scorecard_field_of_study WHERE EARN_MDN_HI_2YR != "" AND EARN_MDN_HI_2YR IS NOT NULL LIMIT 8'
).fetchall()
for r in fos:
    print(f"  {r[0]}  {str(r[1]):8s}  {str(r[2])[:25]:25s}  earn2={r[4]}  nat={r[5]}")

print()
print("dataset_source (scorecard):")
src = conn.execute(
    "SELECT source_id, name, version, loaded_at, record_count FROM dataset_source WHERE source_id LIKE '%scorecard%'"
).fetchall()
for r in src:
    print(f"  {r}")

# Count columns in scorecard_institution
col_count = conn.execute("SELECT COUNT(*) FROM pragma_table_info('scorecard_institution')").fetchone()[0]
print(f"\nscorecard_institution column count: {col_count}")

conn.close()
