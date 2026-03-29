from flask import render_template

from models import db
from routes.career_grade import get_career_grades
from models import SOC_MAJOR_GROUPS
from . import root_bp

@root_bp.route("/outlook")
def outlook_index():
    df = get_career_grades()
    
    # 1. Summary Stats
    total_openings = int(df['raw_openings'].sum())
    ab_openings = int(df[df['grade'].isin(['A+', 'A', 'B+', 'B'])]['raw_openings'].sum())
    ab_concentration = (ab_openings / total_openings * 100) if total_openings else 0
    
    # Average wage for A grades vs overall
    avg_wage_all = df['raw_wage'].mean()
    avg_wage_a = df[df['grade'].isin(['A+', 'A'])]['raw_wage'].mean()
    wage_premium = ((avg_wage_a - avg_wage_all) / avg_wage_all * 100) if avg_wage_all else 0
    
    summary = {
        "total_openings": total_openings,
        "ab_openings": ab_openings,
        "ab_concentration": ab_concentration,
        "wage_premium": wage_premium,
        "avg_wage_all": avg_wage_all,
        "avg_wage_a": avg_wage_a
    }
    
    # 2. Major Occupation Groups
    # Group by major SOC (first two digits)
    df['soc_major'] = df.index.str[:2]
    
    groups = []
    for major, group_df in df.groupby('soc_major'):
        name = SOC_MAJOR_GROUPS.get(major, "Other Occupations")
        tot = group_df['raw_openings'].sum()
        if tot == 0: continue
        
        ab_tot = group_df[group_df['grade'].isin(['A+', 'A', 'B+', 'B'])]['raw_openings'].sum()
        pct = (ab_tot / tot) * 100 if tot else 0
        groups.append({
            "code": major,
            "name": name,
            "total": int(tot),
            "ab_total": int(ab_tot),
            "pct": pct
        })
        
    # Sort by total openings descending, keep top 10
    groups.sort(key=lambda x: x['total'], reverse=True)
    groups = groups[:10]
    
    # 3. Top jobs by tier
    tiers = {}
    for t in ['Now', 'Next', 'Later']:
        tier_df = df[df['tier'] == t]
        # Only take A+, A, B+, B for the top list, sorted by score then openings
        top_df = tier_df[tier_df['grade'].isin(['A+', 'A', 'B+', 'B'])].sort_values(
            by=['composite_score', 'raw_openings'], ascending=[False, False]
        )
        
        # Take the top 15
        top_records = top_df.head(15).reset_index().to_dict('records')
        tiers[t] = top_records
        
    return render_template(
        "outlook/index.html",
        summary=summary,
        groups=groups,
        tiers=tiers
    )
