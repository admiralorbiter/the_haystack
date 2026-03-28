"""
Provider routes — Epic 3

Implements:
  GET /providers                          — directory (filterable, paginated)
  GET /providers/mock                     — mock detail (retained for dev reference)
  GET /providers/<org_id>                 — detail page (snapshot + overview tab)
  GET /providers/<org_id>/tab/connections — HTMX: occupation links + similar providers
  GET /providers/<org_id>/tab/geography   — HTMX: location info
  GET /providers/<org_id>/tab/outcomes    — HTMX: completions table
  GET /providers/<org_id>/tab/evidence    — HTMX: data provenance
  GET /providers/<org_id>/tab/methods     — HTMX: static caveat copy
"""

import re
from collections import Counter
from functools import lru_cache

from flask import abort, current_app, render_template, request
from sqlalchemy import func, text

from models import (
    DatasetSource, Occupation, OrgAlias, Organization,
    Program, ProgramOccupation, RegionCounty, db,
)

from . import root_bp

_UUID_RE = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)


def _valid_unitid(unitid: str | None) -> bool:
    """IPEDS UNITID is a 6-digit numeric string. Reject anything else
    before it reaches raw SQL to prevent unexpected query behaviour."""
    if not unitid:
        return False
    s = str(unitid).strip()
    return s.isdigit() and 1 <= len(s) <= 8


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_provider_or_404(org_id: str) -> Organization:
    """Fetch a training provider by org_id. Aborts 404 if missing or wrong type."""
    org = (
        db.session.query(Organization)
        .filter_by(org_id=org_id, org_type="training")
        .first()
    )
    if not org:
        abort(404)
    return org


# Top-level CIP 2-digit family names (NCES official)
_CIP_FAMILY_NAMES = {
    "01": "Agriculture", "03": "Natural Resources", "04": "Architecture",
    "05": "Area & Cultural Studies", "09": "Communication", "10": "Communications Tech",
    "11": "Computer Science", "12": "Personal Services", "13": "Education",
    "14": "Engineering", "15": "Engineering Tech", "16": "Foreign Languages",
    "19": "Family Sciences", "22": "Legal", "23": "English",
    "24": "Liberal Arts", "25": "Library Science", "26": "Biology",
    "27": "Mathematics", "28": "Military", "29": "Military Tech",
    "30": "Interdisciplinary", "31": "Parks & Recreation", "38": "Philosophy",
    "39": "Theology", "40": "Physical Sciences", "41": "Science Tech",
    "42": "Psychology", "43": "Homeland Security", "44": "Public Admin",
    "45": "Social Sciences", "46": "Construction", "47": "Mechanic & Repair",
    "48": "Precision Production", "49": "Transportation", "50": "Visual & Performing Arts",
    "51": "Health Professions", "52": "Business", "54": "History",
    "60": "Residency Programs",
}


def _provider_snapshot(org_id: str) -> dict:
    """
    Compute all snapshot strip metrics for a provider in a single pass.
    Returns a dict safe to pass into templates.
    """
    programs = db.session.query(Program).filter_by(org_id=org_id).all()

    total_programs = len(programs)
    completions_values = [p.completions for p in programs if p.completions is not None]
    total_completions = sum(completions_values) if completions_values else None
    suppressed_count = sum(1 for p in programs if p.completions is None)

    # Top credential type — most common by program count
    cred_counts = Counter(p.credential_type for p in programs)
    top_credential = cred_counts.most_common(1)[0][0] if cred_counts else "—"

    # Top CIP family — most common 2-digit CIP prefix
    cip_families = Counter(
        p.cip.split(".")[0] for p in programs if p.cip and "." in p.cip
    )
    top_cip_family = cip_families.most_common(1)[0][0] if cip_families else "—"
    cip_name = _CIP_FAMILY_NAMES.get(top_cip_family, "")
    top_cip_label = f"{cip_name} ({top_cip_family})" if cip_name else top_cip_family

    # Linked occupations — distinct SOC codes across all programs
    program_ids = [p.program_id for p in programs]
    occ_count = 0
    if program_ids:
        occ_count = (
            db.session.query(func.count(func.distinct(ProgramOccupation.soc)))
            .filter(ProgramOccupation.program_id.in_(program_ids))
            .scalar() or 0
        )

    # Dataset source freshness
    ds = (
        db.session.query(DatasetSource)
        .filter(DatasetSource.source_id.like("ipeds_hd_%"))
        .order_by(DatasetSource.loaded_at.desc())
        .first()
    )

    return {
        "total_programs": total_programs,
        "total_completions": total_completions,
        "suppressed_count": suppressed_count,
        "top_credential": top_credential,
        "top_cip_family": top_cip_family,
        "top_cip_label": top_cip_label,
        "linked_occupations": occ_count,
        "data_source": ds.name if ds else "IPEDS",
        "data_as_of": ds.loaded_at.strftime("%Y-%m-%d") if ds and ds.loaded_at else "Unknown",
    }


# IPEDS lookup codes -> human-readable labels
_CALSYS = {"1": "Semester", "2": "Quarter", "3": "Trimester", "4": "4-1-4", "5": "Other", "6": "Varies", "7": "Continuous"}
_OPENADMP = {"1": "Open Admission", "2": "Selective Admission"}


def _empty_ipeds() -> dict:
    """Return a fully-keyed IPEDS dict with all values None.
    Key names MUST match exactly what _get_ipeds_enrichment() writes —
    this guards Jinja2 templates for providers that have no IPEDS row.
    """
    return {
        # Institutional characteristics
        "calendar":            None,
        "open_admissions":     None,
        "ft_undergrad":        None,
        "pt_undergrad":        None,
        # Tuition / cost
        "instate_tuition":     None,
        "outstate_tuition":    None,
        "room_board":          None,
        "tuition_varies":      None,
        "net_price":           None,
        "commuter_sticker":    None,
        # Admissions
        "acceptance_rate":     None,
        "sat_reading_75":      None,
        "sat_math_75":         None,
        "act_composite_75":    None,
        # Graduation rates (4yr / standard)
        "grad_rate_150":       None,
        "grad_rate_150_cohort":None,
        "grad_rate_pell":      None,
        "grad_rate_200":       None,
        "grad_rate_200_cohort":None,
        # Graduation rates (2yr / less-than-4yr institutions)
        "grad_rate_150_l2":    None,
        "grad_rate_l2_cohort": None,
        "grad_rate_pell_l2":   None,
        # Enrollment
        "enrollment_total":    None,
        "enrollment_male":     None,
        "enrollment_female":   None,
        "distance_ed_pct":     None,
        "distance_ed_n":       None,
        # Retention
        "retention_ft":        None,
        "retention_pt":        None,
        "student_faculty_ratio":None,
        # Financial aid
        "aid_any_grant_pct":   None,
        "aid_any_grant_avg":   None,
        "aid_pell_pct":        None,
        "aid_pell_avg":        None,
        "aid_loan_pct":        None,
        "aid_loan_avg":        None,
        # Veterans / GI Bill
        "vet_gi_bill_n":       None,
        "vet_gi_bill_avg":     None,
        # Faculty
        "faculty_count":       None,
        "faculty_avg_salary":  None,
        # Expenditures
        "exp_instruction":     None,
        "exp_academic_support":None,
        "exp_student_services":None,
        "exp_total":           None,
        "exp_finance_type":    None,  # 'public' | 'private_nonprofit' | 'forprofit'
    }


# Memoize per-unitid to avoid re-running the 15-table JOIN on every tab load
@lru_cache(maxsize=256)
def _get_ipeds_enrichment(unitid: str) -> dict:
    """Fetch IC, cost, admissions, enrollment, retention, graduation, financial aid,
    200% graduation rate, faculty/staff counts, and expenditure data from IPEDS tables."""
    if not unitid:
        return _empty_ipeds()
    
    query = '''
    SELECT
        ic.CALSYS, ic.OPENADMP, ic.FT_UG, ic.PT_UG,
        cost.CHG1AT0, cost.CHG2AT0, cost.CHG4AY0, cost.CHG5AY0, cost.CHG5AY1, cost.CHG7AY0, cost.TUITVARY,
        adm.APPLCN, adm.ADMSSN, adm.SATVR75, adm.SATMT75, adm.ACTCM75,
        grn.GRTOTLT as gr_150, grd.GRTOTLT as gr_150_cohort,
        grp.PGCMTOT as gr_pell_comp, grp.PGADJCT as gr_pell_adj,
        gr200.BAREVCT as gr200_cohort, gr200.BAGR200 as gr200_comp,
        grl2.LINE_10 as grl2_cohort, grl2.LINE_50 as grl2_comp,
        grl2.PGLIN10 as grl2_pell_cohort, grl2.PGLIN50 as grl2_pell_comp,
        effy.EFYTOTLT, effy.EFYTOTLM, effy.EFYTOTLW,
        dist.EFYDEEXC,
        ef4d.RET_PCF, ef4d.RET_NMP, ef4d.STUFACR,
        sfa.NPIST2,
        sfa24.UAGRNTP as sfa24_any_grant_pct, sfa24.UAGRNTA as sfa24_any_grant_avg,
        sfa24.UPGRNTP as sfa24_pell_pct,    sfa24.UPGRNTA as sfa24_pell_avg,
        sfa24.UFLOANP as sfa24_loan_pct,    sfa24.UFLOANA as sfa24_loan_avg,
        sfav.UGPO9_N as vet_gi_n, sfav.UGPO9_A as vet_gi_avg,
        eap.EAPTOT as faculty_total,
        sal.SA09MAT as faculty_avg_salary,
        fin.exp_i as exp_instruction,
        fin.exp_a as exp_academic_support,
        fin.exp_s as exp_student_services,
        fin.finance_type as exp_finance_type
    FROM ipeds_ic2024 ic
    LEFT JOIN ipeds_cost1_2024 cost ON ic.UNITID = cost.UNITID
    LEFT JOIN ipeds_adm2024 adm ON ic.UNITID = adm.UNITID
    LEFT JOIN ipeds_gr2024 grd ON ic.UNITID = grd.UNITID AND grd.GRTYPE IN (2, 29) AND grd.GRTOTLT != '-1'
    LEFT JOIN ipeds_gr2024 grn ON ic.UNITID = grn.UNITID AND grn.GRTYPE IN (3, 30) AND grn.GRTOTLT != '-1'
    LEFT JOIN ipeds_gr2024_pell_ssl grp ON ic.UNITID = grp.UNITID AND grp.PSGRTYPE IN ('2','4') AND grp.PGCMTOT != '-1'
    LEFT JOIN ipeds_gr200_24 gr200 ON ic.UNITID = gr200.UNITID
    LEFT JOIN ipeds_gr2024_l2 grl2 ON ic.UNITID = grl2.UNITID
    LEFT JOIN ipeds_effy2024 effy ON ic.UNITID = effy.UNITID AND effy.EFFYLEV = '1'
    LEFT JOIN ipeds_effy2024_dist dist ON ic.UNITID = dist.UNITID AND dist.EFFYDLEV = '1'
    LEFT JOIN ipeds_ef2024d ef4d ON ic.UNITID = ef4d.UNITID
    LEFT JOIN ipeds_sfa2223 sfa ON ic.UNITID = sfa.UNITID
    LEFT JOIN ipeds_sfa2324 sfa24 ON ic.UNITID = sfa24.UNITID
    LEFT JOIN ipeds_sfav2223 sfav ON ic.UNITID = sfav.UNITID
    LEFT JOIN (
        SELECT UNITID, SUM(EAPTOT) as EAPTOT
        FROM ipeds_eap2024
        WHERE EAPCAT = '1' AND OCCUPCAT IN ('2100', '2200')
        GROUP BY UNITID
    ) eap ON ic.UNITID = eap.UNITID
    LEFT JOIN (
        SELECT UNITID, SA09MAT
        FROM ipeds_sal2023_is
        WHERE ARANK = '7'
    ) sal ON ic.UNITID = sal.UNITID
    LEFT JOIN (
        -- COALESCE across public (F1A), private non-profit (F2), for-profit (F3)
        -- Only one table should match per UNITID. Finance type label for display.
        SELECT UNITID,
               F1B01 as exp_i, F1B04 as exp_a, F1B05 as exp_s,
               'public' as finance_type
        FROM ipeds_f2223_f1a
        UNION ALL
        SELECT UNITID,
               F2B01, F2B04, F2B05,
               'private_nonprofit'
        FROM ipeds_f2223_f2
        UNION ALL
        SELECT UNITID,
               F3B01, F3B04, F3B05,
               'forprofit'
        FROM ipeds_f2223_f3
    ) fin ON ic.UNITID = fin.UNITID
    WHERE ic.UNITID = :unitid
    '''
    
    try:
        with db.engine.connect() as conn:
            _row = conn.execute(text(query), {"unitid": str(unitid)}).mappings().first()
        row = dict(_row) if _row else None
        if not row:
            return _empty_ipeds()
    except Exception as e:
        import sys
        print(f"IPEDS DB Error for {unitid}: {e}", file=sys.stderr)
        return _empty_ipeds()

    def _int(r, key):
        try: return int(r[key]) if r and r.get(key) and str(r[key]) not in ('-1', '-2', 'None', '') else None
        except (ValueError, TypeError): return None

    def _float(r, key):
        try: return float(r[key]) if r and r.get(key) and str(r[key]) not in ('-1', '-2', 'None', '') else None
        except (ValueError, TypeError): return None

    result = _empty_ipeds()

    result["calendar"]        = _CALSYS.get(str(row.get("CALSYS", "")), None)
    result["open_admissions"] = _OPENADMP.get(str(row.get("OPENADMP", "")), None)
    result["ft_undergrad"]    = str(row.get("FT_UG", "0")) == "1"
    result["pt_undergrad"]    = str(row.get("PT_UG", "0")) == "1"

    in_tuit = _int(row, "CHG1AT0")
    result["instate_tuition"]  = in_tuit
    result["outstate_tuition"] = _int(row, "CHG2AT0")
    result["room_board"]       = _int(row, "CHG5AY0") or _int(row, "CHG5AY1")
    result["tuition_varies"]   = str(row.get("TUITVARY", "0")) == "1"
    result["net_price"]        = _int(row, "NPIST2")

    books = _int(row, "CHG4AY0")
    if in_tuit is not None and books is not None:
        result["commuter_sticker"] = in_tuit + books

    apps   = _int(row, "APPLCN")
    admits = _int(row, "ADMSSN")
    if apps and admits and apps > 0:
        result["acceptance_rate"] = round(admits / apps * 100, 1)
    result["sat_reading_75"]   = _int(row, "SATVR75")
    result["sat_math_75"]      = _int(row, "SATMT75")
    result["act_composite_75"] = _int(row, "ACTCM75")

    result["enrollment_total"]  = _int(row, "EFYTOTLT")
    result["enrollment_male"]   = _int(row, "EFYTOTLM")
    result["enrollment_female"] = _int(row, "EFYTOTLW")

    de_total = _int(row, "EFYDEEXC")
    en_total = _int(row, "EFYTOTLT")
    if de_total is not None and en_total and en_total > 0:
        result["distance_ed_pct"] = round(de_total / en_total * 100, 1)
        result["distance_ed_n"]   = de_total

    result["retention_ft"]         = _int(row, "RET_PCF")
    result["retention_pt"]         = _int(row, "RET_NMP")
    sf = _float(row, "STUFACR")
    result["student_faculty_ratio"] = round(sf, 1) if sf else None

    gr_150 = _int(row, "gr_150")
    gr_co  = _int(row, "gr_150_cohort")
    if gr_150 is not None and gr_co and gr_co > 0:
        result["grad_rate_150"]        = round(gr_150 / gr_co * 100)
        result["grad_rate_150_cohort"] = gr_co

    pg_comp = _int(row, "gr_pell_comp")
    pg_adj  = _int(row, "gr_pell_adj")
    if pg_comp is not None and pg_adj and pg_adj > 0:
        result["grad_rate_pell"] = round(pg_comp / pg_adj * 100)

    # 200% graduation rate (completion within twice the normal time)
    gr200_co   = _int(row, "gr200_cohort")
    gr200_comp = _int(row, "gr200_comp")
    if gr200_co and gr200_comp is not None and gr200_co > 0:
        result["grad_rate_200"]        = round(gr200_comp / gr200_co * 100)
        result["grad_rate_200_cohort"] = gr200_co

    # 2-year institution graduation rates (gr2024_l2)
    # LINE_10 = cohort, LINE_50 = completers within 150% of time
    grl2_co   = _int(row, "grl2_cohort")
    grl2_comp = _int(row, "grl2_comp")
    if grl2_co and grl2_comp is not None and grl2_co > 0:
        result["grad_rate_150_l2"]  = round(grl2_comp / grl2_co * 100)
        result["grad_rate_l2_cohort"] = grl2_co
    grl2_pell_co   = _int(row, "grl2_pell_cohort")
    grl2_pell_comp = _int(row, "grl2_pell_comp")
    if grl2_pell_co and grl2_pell_comp is not None and grl2_pell_co > 0:
        result["grad_rate_pell_l2"] = round(grl2_pell_comp / grl2_pell_co * 100)

    # Financial aid — 2023-24 (sfa2324)
    result["aid_any_grant_pct"]  = _int(row, "sfa24_any_grant_pct")
    result["aid_any_grant_avg"]  = _int(row, "sfa24_any_grant_avg")
    result["aid_pell_pct"]       = _int(row, "sfa24_pell_pct")
    result["aid_pell_avg"]       = _int(row, "sfa24_pell_avg")
    result["aid_loan_pct"]       = _int(row, "sfa24_loan_pct")
    result["aid_loan_avg"]       = _int(row, "sfa24_loan_avg")

    # Veterans / GI Bill (sfav2223)
    vet_n   = _int(row, "vet_gi_n")
    vet_avg = _int(row, "vet_gi_avg")
    if vet_n and vet_n > 0:
        result["vet_gi_bill_n"]   = vet_n
        result["vet_gi_bill_avg"] = vet_avg

    # Faculty & Staff — instructional head count (eap2024, OCCUPCAT 2100+2200)
    result["faculty_count"]      = _int(row, "faculty_total")

    # Faculty average 9-month salary (sal2023_is, ARANK=7 = all ranks)
    _sal = _int(row, "faculty_avg_salary")
    result["faculty_avg_salary"] = _sal if _sal and _sal > 0 else None

    # Institutional Expenditures — FY2022-23, covers public/private-nonprofit/for-profit
    # All three finance tables use the same Bxx column pattern; values are raw dollars.
    # We guard against negative values (IPEDS suppression artifact in F2/F3).
    def _pos_int(r, key):
        v = _int(r, key)
        return v if v and v > 0 else None

    _exp_instruction      = _pos_int(row, "exp_instruction")
    _exp_academic_support = _pos_int(row, "exp_academic_support")
    _exp_student_services = _pos_int(row, "exp_student_services")
    result["exp_instruction"]      = round(_exp_instruction / 1000)      if _exp_instruction      else None
    result["exp_academic_support"] = round(_exp_academic_support / 1000) if _exp_academic_support else None
    result["exp_student_services"] = round(_exp_student_services / 1000) if _exp_student_services else None
    result["exp_finance_type"]     = str(row.get("exp_finance_type") or "") or None
    # Total for percentage calculations
    _exp_vals = [result["exp_instruction"], result["exp_academic_support"], result["exp_student_services"]]
    result["exp_total"] = sum(v for v in _exp_vals if v) or None

    return result


# ---------------------------------------------------------------------------
# /providers/mock — DEV ONLY (guarded)
# ---------------------------------------------------------------------------

@root_bp.route("/providers/mock")
def provider_detail_mock():
    """Dev shortcut — only active in DEBUG mode."""
    if not current_app.debug:
        abort(404)
    try:
        from mock_data import MOCK_PROVIDER  # noqa: PLC0415
    except ImportError:
        abort(404)
    return render_template(
        "providers/detail.html",
        org=type("O", (), MOCK_PROVIDER)(),
        snapshot={
            "total_programs": 5, "total_completions": 120,
            "suppressed_count": 0, "top_credential": "Bachelor's degree",
            "top_cip_family": "51", "linked_occupations": 12,
            "data_source": "IPEDS Mock", "data_as_of": "2024-01-01",
        },
        top_programs=[],
        cred_mix=[],
        active_tab="overview",
        inst_type="4-year",
    )



@lru_cache(maxsize=256)
def _ipeds_outcome_measures(unitid: str) -> list[dict]:
    """
    Pull Outcome Measures (om2024) for a provider.
    OMCHRT=10 → full-time first-time students; OMCHRT=11 → part-time/transfer.
    Returns [{cohort_type, cohort_n, pct_4yr, pct_6yr, pct_8yr}, ...].
    """
    if not _valid_unitid(unitid):
        return []
    _OMCHRT = {"10": "Full-time, first-time", "11": "Part-time / transfer"}
    try:
        with db.engine.connect() as conn:
            rows = conn.execute(
                text("""SELECT OMCHRT, OMACHRT, OMAWDP4, OMAWDP6, OMAWDP8
                       FROM ipeds_om2024 WHERE UNITID=:uid AND OMCHRT IN ('10','11')"""),
                {"uid": str(unitid)},
            ).fetchall()

        def _iv(v):
            try: return int(v) if v and v not in ('-1','-2','') else None
            except: return None

        result = []
        for r in rows:
            cohort_n = _iv(r[1])
            if not cohort_n:
                continue
            result.append({
                "label":    _OMCHRT.get(str(r[0]), str(r[0])),
                "cohort_n": cohort_n,
                "pct_4yr":  _iv(r[2]),
                "pct_6yr":  _iv(r[3]),
                "pct_8yr":  _iv(r[4]),
            })
        return result
    except Exception:
        return []


@lru_cache(maxsize=256)
def _ipeds_enrollment_demographics(unitid: str) -> dict | None:
    """
    Pull fall enrollment by race/ethnicity from ipeds_ef2024a.
    EFALEVEL=1 is the total undergraduate aggregate.
    Returns dict of race group → count, plus total/male/female.
    """
    if not _valid_unitid(unitid):
        return None
    try:
        with db.engine.connect() as conn:
            row = conn.execute(
                text("""SELECT EFTOTLT, EFTOTLM, EFTOTLW,
                              EFAIANT, EFASIAT, EFBKAAT, EFHISPT, EFWHITT, EF2MORT,
                              EFNRALT, EFUNKNT
                       FROM ipeds_ef2024a
                       WHERE UNITID=:uid AND EFALEVEL='1'
                       LIMIT 1"""),
                {"uid": str(unitid)},
            ).fetchone()
        if not row:
            return None

        def _iv(v):
            try: return int(v) if v and v not in ('-1','-2','') else None
            except: return None

        total = _iv(row[0])
        if not total:
            return None
        return {
            "total":       total,
            "male":        _iv(row[1]),
            "female":      _iv(row[2]),
            "aian":        _iv(row[3]),
            "asian":       _iv(row[4]),
            "black":       _iv(row[5]),
            "hispanic":    _iv(row[6]),
            "white":       _iv(row[7]),
            "two_or_more": _iv(row[8]),
            "nonresident": _iv(row[9]),
            "unknown":     _iv(row[10]),
        }
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Directory — GET /providers
# ---------------------------------------------------------------------------

@root_bp.route("/providers")
def providers_directory():
    county_filter = request.args.get("county", "").strip()
    cred_filter = request.args.get("cred", "").strip()
    # CIP filter: only accept 1-2 digit family codes (e.g. "51") to prevent
    # open-ended LIKE matches or erroneous partial strings.
    _raw_cip = request.args.get("cip", "").strip()
    cip_filter = _raw_cip if _raw_cip.isdigit() and 1 <= len(_raw_cip) <= 2 else ""
    sort = request.args.get("sort", "completions")
    page = max(1, int(request.args.get("page", 1)))
    per_page = 50

    # Compare selection mode — user clicked ⊕ on one provider, now picking a second
    comparing_id = request.args.get("comparing", "").strip()
    comparing_name = None
    if comparing_id:
        cmp_org = db.session.query(Organization).filter_by(org_id=comparing_id, org_type="training").first()
        comparing_name = cmp_org.name if cmp_org else None
        if not comparing_name:
            comparing_id = ""  # invalid id, clear it

    # When a credential filter is active, restrict the completions aggregate
    # to only programs matching that credential — otherwise orgs with mixed
    # credential offerings would show inflated totals in the directory.
    _completions_sum = (
        func.sum(
            db.case(
                (Program.credential_type == cred_filter, Program.completions),
                else_=None,
            )
        )
        if cred_filter
        else func.sum(Program.completions)
    )

    q = (
        db.session.query(
            Organization,
            func.count(Program.program_id).label("program_count"),
            _completions_sum.label("total_completions"),
            func.count(func.distinct(ProgramOccupation.soc)).label("occ_count"),
        )
        .outerjoin(Program, Program.org_id == Organization.org_id)
        .outerjoin(ProgramOccupation, ProgramOccupation.program_id == Program.program_id)
        .filter(Organization.org_type == "training")
        .group_by(Organization.org_id)
    )

    if county_filter:
        q = q.filter(Organization.county_fips == county_filter)

    if cred_filter:
        cred_org_ids = (
            db.session.query(Program.org_id)
            .filter(Program.credential_type == cred_filter)
            .distinct()
            .subquery()
        )
        q = q.filter(Organization.org_id.in_(cred_org_ids))

    if cip_filter:
        cip_org_ids = (
            db.session.query(Program.org_id)
            .filter(Program.cip.like(f"{cip_filter}.%"))
            .distinct()
            .subquery()
        )
        q = q.filter(Organization.org_id.in_(cip_org_ids))

    if sort == "programs":
        q = q.order_by(func.count(Program.program_id).desc())
    elif sort == "name":
        q = q.order_by(Organization.name.asc())
    elif sort == "location":
        q = q.order_by(Organization.city.asc().nulls_last())
    elif sort == "occupations":
        q = q.order_by(func.count(func.distinct(ProgramOccupation.soc)).desc())
    else:
        sort = "completions"
        q = q.order_by(func.sum(Program.completions).desc().nulls_last())

    total_count = q.count()
    rows = q.offset((page - 1) * per_page).limit(per_page).all()

    all_counties = (
        db.session.query(RegionCounty.county_fips, RegionCounty.county_name, RegionCounty.state)
        .filter(RegionCounty.county_fips.in_(
            db.session.query(Organization.county_fips)
            .filter_by(org_type="training")
            .filter(Organization.county_fips.isnot(None))
        ))
        .order_by(RegionCounty.county_name)
        .all()
    )
    all_creds = (
        db.session.query(Program.credential_type)
        .filter(Program.org_id.in_(
            db.session.query(Organization.org_id).filter_by(org_type="training")
        ))
        .distinct()
        .order_by(Program.credential_type)
        .all()
    )

    providers = [
        {
            "org": row.Organization,
            "program_count": row.program_count or 0,
            "total_completions": int(row.total_completions) if row.total_completions else None,
            "occ_count": row.occ_count or 0,
        }
        for row in rows
    ]

    total_pages = max(1, -(-total_count // per_page))

    return render_template(
        "providers/directory.html",
        providers=providers,
        total_count=total_count,
        page=page,
        total_pages=total_pages,
        per_page=per_page,
        county_filter=county_filter,
        cred_filter=cred_filter,
        cip_filter=cip_filter,
        sort=sort,
        all_counties=all_counties,
        all_creds=[r.credential_type for r in all_creds],
        comparing_id=comparing_id,
        comparing_name=comparing_name,
    )



# ---------------------------------------------------------------------------
# Detail page — GET /providers/<org_id>
# ---------------------------------------------------------------------------

@root_bp.route("/providers/<org_id>")
def provider_detail(org_id: str):
    # Validate UUID format to return clean 404 instead of DB error
    if not _UUID_RE.match(org_id):
        abort(404)
    org = _get_provider_or_404(org_id)
    snapshot = _provider_snapshot(org_id)

    # Derive institution type badge from top credential (aligns with IPEDS program data)
    _cred = (snapshot.get('top_credential') or '').lower()
    if any(k in _cred for k in ('bachelor', 'master', 'doctor', 'first-prof')):
        inst_type = '\U0001f393 4-year'
    elif 'associate' in _cred:
        inst_type = '\U0001f4cb 2-year'
    else:
        inst_type = '\U0001f4dc Certificate'

    top_programs = (
        db.session.query(Program)
        .filter_by(org_id=org_id)
        .order_by(Program.completions.desc().nulls_last())
        .limit(10)
        .all()
    )

    cred_mix = (
        db.session.query(Program.credential_type, func.count(Program.program_id).label("cnt"))
        .filter_by(org_id=org_id)
        .group_by(Program.credential_type)
        .order_by(func.count(Program.program_id).desc())
        .all()
    )

    ipeds_data = _get_ipeds_enrichment(org.unitid)

    if request.headers.get("HX-Request"):
        return render_template(
            "providers/partials/tab_overview.html",
            org=org,
            snapshot=snapshot,
            top_programs=top_programs,
            cred_mix=cred_mix,
            ipeds=ipeds_data,
            inst_type=inst_type,
        )

    return render_template(
        "providers/detail.html",
        org=org,
        snapshot=snapshot,
        top_programs=top_programs,
        cred_mix=cred_mix,
        ipeds=ipeds_data,
        active_tab="overview",
        inst_type=inst_type,
    )


# ---------------------------------------------------------------------------
# HTMX tab fragments
# ---------------------------------------------------------------------------

@root_bp.route("/providers/<org_id>/tab/connections")
def provider_tab_connections(org_id: str):
    """Connections tab: occupation links + similar providers by CIP overlap."""
    org = _get_provider_or_404(org_id)

    occ_links = (
        db.session.query(
            Occupation,
            func.count(func.distinct(Program.program_id)).label("program_count"),
        )
        .join(ProgramOccupation, ProgramOccupation.soc == Occupation.soc)
        .join(Program, Program.program_id == ProgramOccupation.program_id)
        .filter(Program.org_id == org_id)
        .group_by(Occupation.soc)
        .order_by(func.count(func.distinct(Program.program_id)).desc())
        .all()
    )

    # CIP-overlap self-join: other providers sharing the most CIP codes with this one
    similar_rows = (
        db.session.query(
            Organization,
            func.count(func.distinct(Program.cip)).label("shared_cip_count"),
        )
        .join(Program, Program.org_id == Organization.org_id)
        .filter(
            Organization.org_type == "training",
            Organization.org_id != org_id,
            Program.cip.in_(
                db.session.query(Program.cip).filter_by(org_id=org_id).subquery()
            ),
        )
        .group_by(Organization.org_id)
        .order_by(func.count(func.distinct(Program.cip)).desc())
        .limit(5)
        .all()
    )

    similar_providers = [
        {"org": row.Organization, "shared_cip_count": row.shared_cip_count}
        for row in similar_rows
    ]

    return render_template(
        "providers/partials/tab_connections.html",
        org=org,
        occ_links=occ_links,
        similar_providers=similar_providers,
    )


@root_bp.route("/providers/<org_id>/tab/geography")
def provider_tab_geography(org_id: str):
    org = _get_provider_or_404(org_id)
    county = (
        db.session.query(RegionCounty)
        .filter_by(county_fips=org.county_fips)
        .first()
    )
    return render_template(
        "providers/partials/tab_geography.html",
        org=org,
        county=county,
    )


@root_bp.route("/providers/<org_id>/tab/outcomes")
def provider_tab_outcomes(org_id: str):
    org = _get_provider_or_404(org_id)
    programs = (
        db.session.query(Program)
        .filter_by(org_id=org_id)
        .order_by(Program.credential_type, Program.completions.desc().nulls_last())
        .all()
    )
    with_data = [p for p in programs if p.completions is not None]
    total = sum(p.completions for p in with_data)

    return render_template(
        "providers/partials/tab_outcomes.html",
        org=org,
        programs=programs,
        total_completions=total,
        suppressed_count=len(programs) - len(with_data),
        ipeds=_get_ipeds_enrichment(org.unitid),
        outcome_measures=_ipeds_outcome_measures(org.unitid),
        enrollment_demo=_ipeds_enrollment_demographics(org.unitid),
    )


@root_bp.route("/providers/<org_id>/tab/evidence")
def provider_tab_evidence(org_id: str):
    org = _get_provider_or_404(org_id)
    alias = db.session.query(OrgAlias).filter_by(org_id=org_id, source="ipeds").first()
    ds_hd = (
        db.session.query(DatasetSource)
        .filter(DatasetSource.source_id.like("ipeds_hd_%"))
        .order_by(DatasetSource.loaded_at.desc())
        .first()
    )
    ds_c = (
        db.session.query(DatasetSource)
        .filter(DatasetSource.source_id.like("ipeds_c_%"))
        .order_by(DatasetSource.loaded_at.desc())
        .first()
    )
    return render_template(
        "providers/partials/tab_evidence.html",
        org=org,
        alias=alias,
        ds_hd=ds_hd,
        ds_c=ds_c,
    )


@root_bp.route("/providers/<org_id>/tab/methods")
def provider_tab_methods(org_id: str):
    org = _get_provider_or_404(org_id)
    return render_template("providers/partials/tab_methods.html", org=org)
