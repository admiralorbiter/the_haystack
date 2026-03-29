"""
qcew_utils.py — Shared QCEW trend calculation logic.

Provides a single `get_qcew_trends(naics_list, session)` function used by:
  - routes/occupations.py  (Who Hires This? badges)
  - routes/industries.py   (directory + detail pages)
  - routes/__init__.py     (Home page Pulse widget)

Design decisions:
  - "Latest Complete Quarter" heuristic: if the newest quarter's KC-aggregated
    employment is <60% of the trailing 4-quarter average, we treat it as an
    incomplete/preliminary BLS release and fall back to the prior quarter.
    This prevents false-alarm massive 40-60% YoY drops from partial data.
  - YoY: compares to same quarter one year prior (seasonality-safe).
  - Trend Slope: simple least-squares linear regression across ALL available
    quarterly data points, expressed as annualised % change per year.
    This signal is immune to single-quarter noise and uses every data point.
"""

from __future__ import annotations
from sqlalchemy import func
from models import IndustryQCEW


def _linear_trend_pct_per_year(values: list[float]) -> float | None:
    """
    Fits a least-squares line to a time series (one value per quarter, chronological).
    Returns the slope expressed as annualised % change per year, or None if insufficient data.
    """
    n = len(values)
    if n < 4:
        return None
    mean_x = (n - 1) / 2.0
    mean_y = sum(values) / n
    if mean_y == 0:
        return None

    numer = sum((i - mean_x) * (values[i] - mean_y) for i in range(n))
    denom = sum((i - mean_x) ** 2 for i in range(n))
    if denom == 0:
        return None

    slope_per_quarter = numer / denom
    # 4 quarters per year → annualise; express as % of mean level
    return round((slope_per_quarter / mean_y) * 4 * 100, 1)


def _detect_complete_quarter(
    per_quarter: dict[int, dict[int, float]]
) -> tuple[int, int, bool]:
    """
    Given {year: {quarter: employment}}, returns (year, quarter, is_complete).
    Flags the latest quarter as incomplete if its employment is below 60% of
    the trailing 4-quarter average, and falls back to the prior quarter.
    """
    periods = sorted(
        [(y, q) for y, qs in per_quarter.items() for q in qs],
        reverse=True
    )
    if not periods:
        return 0, 0, False

    ly, lq = periods[0]
    latest_emp = per_quarter[ly][lq]

    prior_values = [per_quarter[y][q] for y, q in periods[1:5]]
    if prior_values:
        avg_prior = sum(prior_values) / len(prior_values)
        if avg_prior > 0 and latest_emp < avg_prior * 0.60:
            # Likely incomplete — fall back to previous quarter
            if len(periods) > 1:
                py, pq = periods[1]
                return py, pq, False
    return ly, lq, True


def get_qcew_trends(naics_list: list[str], session) -> dict:
    """
    Returns a dict mapping NAICS -> TrendResult for each NAICS in naics_list.

    TrendResult keys:
      latest_emp       : int   — KC-area employment for the reference quarter
      ref_quarter      : str   — e.g. "Q2 2025"
      is_complete      : bool  — True if reference quarter is fully released
      yoy_pct          : float | None — YoY % vs same quarter prior year
      direction        : str   — "UP" | "DOWN" | "FLAT" | "UNKNOWN"
      trend_slope_pct  : float | None — annualised linear trend %/yr
      trend_direction  : str   — "UP" | "DOWN" | "FLAT" | "UNKNOWN"
    """
    if not naics_list:
        return {}

    rows = (
        session.query(
            IndustryQCEW.naics,
            IndustryQCEW.year,
            IndustryQCEW.quarter,
            func.sum(IndustryQCEW.employment).label("emp"),
        )
        .filter(IndustryQCEW.naics.in_(naics_list))
        .group_by(IndustryQCEW.naics, IndustryQCEW.year, IndustryQCEW.quarter)
        .order_by(IndustryQCEW.year, IndustryQCEW.quarter)
        .all()
    )

    # Build per-naics time series: {naics: {year: {quarter: emp}}}
    raw: dict[str, dict[int, dict[int, float]]] = {}
    for r in rows:
        raw.setdefault(r.naics, {}).setdefault(r.year, {})[r.quarter] = r.emp or 0

    results = {}
    for naics in naics_list:
        if naics not in raw:
            continue

        per_quarter = raw[naics]
        ref_y, ref_q, is_complete = _detect_complete_quarter(per_quarter)
        if not ref_y:
            continue

        latest_emp = per_quarter[ref_y][ref_q]
        ref_quarter_str = f"Q{ref_q} {ref_y}"

        # YoY: same quarter, prior year
        prev_year = ref_y - 1
        yoy_pct = None
        direction = "UNKNOWN"
        if prev_year in per_quarter and ref_q in per_quarter[prev_year]:
            prev_emp = per_quarter[prev_year][ref_q]
            if prev_emp and prev_emp > 0:
                yoy_pct = round(((latest_emp - prev_emp) / prev_emp) * 100.0, 1)
                if yoy_pct > 0.5:
                    direction = "UP"
                elif yoy_pct < -0.5:
                    direction = "DOWN"
                else:
                    direction = "FLAT"

        # Linear trend — build chronological series up to and including ref quarter
        chronological = []
        for y in sorted(per_quarter.keys()):
            for q in sorted(per_quarter[y].keys()):
                if (y, q) <= (ref_y, ref_q):
                    chronological.append(float(per_quarter[y][q]))

        trend_slope = _linear_trend_pct_per_year(chronological)
        if trend_slope is None:
            trend_direction = "UNKNOWN"
        elif trend_slope > 0.5:
            trend_direction = "UP"
        elif trend_slope < -0.5:
            trend_direction = "DOWN"
        else:
            trend_direction = "FLAT"

        results[naics] = {
            "latest_emp": latest_emp,
            "ref_quarter": ref_quarter_str,
            "is_complete": is_complete,
            "yoy_pct": yoy_pct,
            "direction": direction,
            "trend_slope_pct": trend_slope,
            "trend_direction": trend_direction,
        }

    return results
