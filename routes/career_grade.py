import pandas as pd
from typing import Dict, Any, List
from models import db, Occupation, OccupationProjection, OccupationWage, OccupationIndustry
from routes.qcew_utils import get_qcew_trends

# Global cache for the dataframe to avoid re-querying and re-ranking on every request
_CAREER_GRADE_DF = None

def _compute_career_grades() -> pd.DataFrame:
    """
    Computes a proprietary "Career Grade" for every occupation in the database.
    Weights:
    - 25% Demand Volume (Annual Openings)
    - 20% Demand Trajectory (10-yr Growth Rate)
    - 20% Compensation (KC Median Wage)
    - 15% Local KC Signal (QCEW momentum of primary industry)
    - 10% Fast ROI (Wage / Job Zone)
    - 10% Future Proof (Inverted Automation Risk)
    
    Returns a DataFrame indexed by SOC code with scores and grades.
    """
    # 1. Fetch core DB inputs 
    occs = Occupation.query.all()
    projs = {p.soc: p for p in OccupationProjection.query.all()}
    
    # Get KC wages, falling back to national if missing
    wages = OccupationWage.query.all()
    soc_wages = {}
    for w in wages:
        # Prefer KC wages
        if w.area_name and "Kansas City" in w.area_name and w.median_wage:
            soc_wages[w.soc] = w.median_wage
        elif w.soc not in soc_wages and w.area_type == 'national' and w.median_wage:
            soc_wages[w.soc] = w.median_wage

    # 2. Fetch QCEW local momentum proxy
    # For each SOC, find its top employing industry's trend
    occ_inds = OccupationIndustry.query.order_by(OccupationIndustry.soc, OccupationIndustry.pct_of_occupation.desc()).all()
    soc_to_naics = {}
    for oi in occ_inds:
        if oi.soc not in soc_to_naics:
            soc_to_naics[oi.soc] = oi.naics
            
    all_naics = list(set(soc_to_naics.values()))
    trends = get_qcew_trends(all_naics, db.session)
    
    soc_momentum = {}
    for soc, naics in soc_to_naics.items():
        t = trends.get(naics)
        if t and t["yoy_pct"] is not None:
            soc_momentum[soc] = t["yoy_pct"]

    # 3. Assemble inputs into a list of dicts for Pandas
    data = []
    for occ in occs:
        p = projs.get(occ.soc)
        w = soc_wages.get(occ.soc)
        m = soc_momentum.get(occ.soc)
        
        # We need at least projection or wage data to grade an occupation sensibly
        if not p and not w:
            continue
            
        wage_val = w if w else None
        openings_val = p.annual_openings if p and p.annual_openings else None
        growth_val = p.pct_change if p and p.pct_change else None
        
        roi_val = None
        if wage_val and occ.job_zone:
            # lower job zone = higher ROI
            roi_val = wage_val / occ.job_zone
            
        data.append({
            "soc": occ.soc,
            "title": occ.title,
            "job_zone": occ.job_zone,
            "bright_outlook": occ.bright_outlook,
            "remote_capable": occ.remote_capable,
            "automation_risk": occ.automation_risk,
            
            # Raw grade inputs
            "raw_wage": wage_val,
            "raw_openings": openings_val,
            "raw_growth": growth_val,
            "raw_momentum": m,
            "raw_roi": roi_val,
            "raw_auto_risk": occ.automation_risk
        })
        
    df = pd.DataFrame(data)
    if df.empty:
        return df
        
    df.set_index("soc", inplace=True)
    
    # 4. Convert raw values to percentiles (0 to 1.0)
    # We rank them ignoring NaNs so the missing values just don't contribute to the score
    df['rank_openings'] = df['raw_openings'].rank(pct=True)
    df['rank_growth'] = df['raw_growth'].rank(pct=True)
    df['rank_wage'] = df['raw_wage'].rank(pct=True)
    df['rank_momentum'] = df['raw_momentum'].rank(pct=True)
    df['rank_roi'] = df['raw_roi'].rank(pct=True)
    
    # For automation risk, lower is better, so we rank descending
    df['rank_future_proof'] = df['raw_auto_risk'].rank(pct=True, ascending=False)
    
    # Fill missing percentile ranks with 0.5 (average) so missing data doesn't penalize harshly 
    # except for momentum and risk where we'll lean slightly conservative (0.4)
    df['rank_openings'] = df['rank_openings'].fillna(0.3)
    df['rank_growth'] = df['rank_growth'].fillna(0.3)
    df['rank_wage'] = df['rank_wage'].fillna(0.3)
    df['rank_momentum'] = df['rank_momentum'].fillna(0.4)
    df['rank_roi'] = df['rank_roi'].fillna(0.4)
    df['rank_future_proof'] = df['rank_future_proof'].fillna(0.5)

    # 5. Compute Weighted Composite Score (0.0 to 1.0)
    df['composite_score'] = (
        (df['rank_openings']     * 0.25) +
        (df['rank_growth']       * 0.20) +
        (df['rank_wage']         * 0.20) +
        (df['rank_momentum']     * 0.15) +
        (df['rank_roi']          * 0.10) +
        (df['rank_future_proof'] * 0.10)
    )
    
    # Output to 100-point scale for readability
    df['score_100'] = (df['composite_score'] * 100).round(1)
    
    # 6. Assign Letter Grades based on final score percentiles
    score_ranks = df['composite_score'].rank(pct=True)
    
    def assign_grade(pct: float) -> str:
        if pct >= 0.95: return "A+"
        if pct >= 0.75: return "A"
        if pct >= 0.60: return "B+"
        if pct >= 0.45: return "B"
        if pct >= 0.25: return "C"
        if pct >= 0.10: return "D"
        return "F"
        
    df['grade'] = score_ranks.apply(assign_grade)
    
    # Map Now/Next/Later
    def assign_tier(jz):
        if pd.isna(jz): return "Unknown"
        if jz in [1, 2]: return "Now"
        if jz == 3: return "Next"
        if jz in [4, 5]: return "Later"
        return "Unknown"
        
    df['tier'] = df['job_zone'].apply(assign_tier)
    
    return df

def get_career_grades(force_refresh=False) -> pd.DataFrame:
    global _CAREER_GRADE_DF
    if _CAREER_GRADE_DF is None or force_refresh:
        _CAREER_GRADE_DF = _compute_career_grades()
    return _CAREER_GRADE_DF
