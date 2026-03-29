# Epic 19 — KC Career Intelligence Dashboard

**Status:** 🟡 In Design — Data Downloads Pending  
**Goal:** Build a `/outlook` page and occupation-level "Career Grades" inspired by MERIC's KC Region Top Grade Jobs report, using our existing data plus three new free datasets.

---

## What We're Building

An interactive **KC Career Intelligence Dashboard** at `/outlook` that surfaces:

1. **Career Grades (A+ → F)** — a transparent, weighted score for each occupation based on 6 dimensions (vs. MERIC's 3)  
2. **Now / Next / Later tiers** — grouping occupations by training investment required (derived from O*NET job zones we already have)
3. **Top Occupation Groups table** — SOC major-group breakdown of total openings, high-grade openings, and concentration %
4. **Top-graded jobs by tier** — top 10 occupations per training tier, with grade, openings, growth rate, wage

---

## Why Our Version Is Better Than MERIC's

| Feature | MERIC (PDF) | Haystack |
|---|---|---|
| KC-specific wages | ✅ | ✅ |
| KC local employment momentum | ❌ | ✅ QCEW trend |
| Automation risk warning | ❌ | ✅ (after data download) |
| Training ROI signal | ❌ | ✅ wage ÷ job_zone |
| Local supply pressure | ❌ | ✅ IPEDS completions |
| Linkable to programs | ❌ | ✅ |
| Interactive / filterable | ❌ | ✅ |
| Updated quarterly | ❌ (annual PDF) | ✅ |

---

## Step 1: Download These Three Free Datasets (You Do This)

### A. O*NET Bright Outlook Flags 🔗

**URL:** https://www.onetcenter.org/dl_files/database/db_29_3_excel/Bright%20Outlook%20Occupations.xlsx

**What it is:** BLS/O*NET flags ~900 occupations that are projected to grow much faster than average, have large numbers of openings, or are new & emerging. It's a free, curated quality signal.

**How to download:**
1. Go to https://www.onetcenter.org/database.html#individual-files
2. Under **"Occupation-Level Data"**, download **"Bright Outlook Occupations"** (Excel or txt)
3. Save as: `data/raw/onet/bright_outlook.xlsx`

**Expected columns:** `O*NET-SOC Code`, `Title`, `Bright Outlook Category` (`Grow Rapidly`, `Numerous Openings`, `New & Emerging`)

---

### B. Automation Risk (Frey & Osborne) 🔗

**URL:** https://raw.githubusercontent.com/owid/owid-datasets/master/datasets/Share%20of%20workers%20at%20risk%20of%20automation%20-%20Frey%20and%20Osborne%20(2017)/Share%20of%20workers%20at%20risk%20of%20automation%20-%20Frey%20and%20Osborne%20(2017).csv

**What it is:** Oxford researchers computed automation probability (0–1.0) for 702 US occupations in 2013. Still the most widely cited dataset. Mapped to 6-digit SOC codes.

**How to download:**
1. Download directly from the URL above OR
2. Go to https://www.oxfordmartin.ox.ac.uk/downloads/academic/The_Future_of_Employment.pdf (Appendix table, page 57+) — the data is also in Supplementary Table at https://github.com/owid/owid-datasets/tree/master/datasets/Share%20of%20workers%20at%20risk%20of%20automation%20-%20Frey%20and%20Osborne%20(2017)
3. Save as: `data/raw/automation_risk.csv`

**Expected columns:** `SOC` or `occupation`, `probability` (0.0–1.0)

> **Note:** The Frey & Osborne SOC codes are older (SOC 2010). We'll need to do a simple crosswalk — most codes still match directly, and we'll skip or null-out the ~10% that don't map.

---

### C. Remote Work Potential (Dingel & Neiman) 🔗

**URL:** https://github.com/jdingel/DingelNeiman-workathome/raw/master/occ_workathome/output/teleworkable_occ.csv

**What it is:** Two economists classified every SOC occupation as "can be done from home" (1) or "cannot" (0) based on O*NET task descriptors. Published 2020, still the standard dataset. 741 occupations covered.

**How to download:**
1. Go to https://github.com/jdingel/DingelNeiman-workathome
2. Download `occ_workathome/output/teleworkable_occ.csv`
3. Save as: `data/raw/remote_work_potential.csv`

**Expected columns:** `onetsoccode`, `title`, `teleworkable` (0 or 1)

---

## Step 2: Data Loader Tasks (Antigravity Does This After Downloads)

Once the three files are in `data/raw/`, Antigravity will:

1. **Write `loaders/load_onet_bright_outlook.py`** — ingest into a new `OccupationSignal` table (or add columns to existing `Occupation` model)
2. **Write `loaders/load_automation_risk.py`** — ingest Frey-Osborne scores, with SOC 2010→2019 crosswalk
3. **Write `loaders/load_remote_potential.py`** — ingest Dingel-Neiman binary flag

---

## Step 3: Grade Computation (Antigravity Does This)

### Grading Inputs & Weights

| Dimension | Input | Weight | Source |
|---|---|---|---|
| Demand volume | Annual openings — percentile rank | 25% | OccupationProjection |
| Demand trajectory | 10-yr growth rate — percentile rank | 20% | OccupationProjection |
| Compensation | KC median wage — percentile rank | 20% | OccupationWage (KC) |
| Local KC signal | KC QCEW YoY momentum of primary industry | 15% | qcew_utils (just built!) |
| Accessibility/ROI | KC wage ÷ job_zone (training cost proxy) | 10% | Occupation.job_zone |
| Future risk | Automation probability (inverted) | 10% | Frey & Osborne (after download) |

> **Optional bonus signals** (add if data download succeeds):
> - O*NET Bright Outlook flag → +0.5 grade step up
> - Remote-capable flag → noted in UI but not in grade score

### Grade Thresholds (percentile of composite score)

| Grade | Percentile | Description |
|---|---|---|
| A+ | Top 5% | Exceptional on 3+ dimensions |
| A | 75th–95th | Above average on 2+ dimensions |
| B+ | 60th–75th | Above average on 1 dimension, strong elsewhere |
| B | 45th–60th | Average overall performance |
| C | 25th–45th | Below average on 1+ dimensions |
| D | 10th–25th | Below average on 2+ dimensions |
| F | Bottom 10% | Below average on 3+ dimensions |

---

## Step 4: Now / Next / Later Mapping

| Job Zone | Tier | Description |
|---|---|---|
| 1 | **Now** | Little to no preparation needed |
| 2 | **Now** | Some preparation — HS diploma + short training |
| 3 | **Next** | Medium preparation — certificate or associates |
| 4 | **Later** | Considerable preparation — bachelor's degree |
| 5 | **Later** | Extensive preparation — advanced degree |

---

## Step 5: UI — `/outlook` Page (Antigravity Does This)

### Sections
1. **Hero header** — "KC Career Intelligence" — total openings, % in A/B grade
2. **Grade legend card** — explain A+ to F with our methodology (fully transparent)
3. **Top Occupation Groups table** — major SOC group, total openings, A&B openings, concentration
4. **Now / Next / Later tabs (or sections)** — top 10 per tier sorted by grade then openings, with:
   - Grade badge (A+/A/B+/B/C)
   - Occupation title (linked to detail page)
   - Annual openings
   - 10-yr growth %
   - KC median wage
   - ⚡ Bright Outlook badge if flagged
   - 🤖 Automation risk indicator if >70%
   - 🏠 Remote-capable badge if flagged

---

## Data Flow Diagram

```
OccupationProjection  ──┐
OccupationWage (KC)   ──┤
Occupation.job_zone   ──┤
QCEW KC momentum      ──┤──→ career_grade.py → grade score → /outlook
Frey-Osborne risk     ──┤
O*NET Bright Outlook  ──┤
Dingel-Neiman remote  ──┘
```

---

## File Checklist

### Data Downloads (You)
- [ ] `data/raw/onet/bright_outlook.xlsx` — O*NET Bright Outlook
- [ ] `data/raw/automation_risk.csv` — Frey & Osborne
- [ ] `data/raw/remote_work_potential.csv` — Dingel & Neiman

### Loaders (Antigravity, after downloads)
- [ ] `loaders/load_onet_bright_outlook.py`
- [ ] `loaders/load_automation_risk.py`
- [ ] `loaders/load_remote_potential.py`

### Application Code (Antigravity)
- [ ] `routes/career_grade.py` — weighted scoring engine
- [ ] `routes/outlook.py` — `/outlook` route
- [ ] `templates/outlook/index.html` — full dashboard UI
- [ ] Update `templates/base.html` — add "Outlook" to nav
- [ ] Update `templates/home.html` — add gateway card
- [ ] Update `HAYSTACK_EPICS.md` to mark Epic 19 in roadmap

---

## Sources & Attribution

- **Employment Projections:** BLS National Employment Matrix (2024–2034)
- **Wages:** BLS OEWS (Occupational Employment and Wage Statistics), KC-MSA
- **Industry Trends:** BLS QCEW (Quarterly Census of Employment and Wages), KC Metro counties
- **Automation Risk:** Frey & Osborne (2013) via Oxford Martin School. *"The Future of Employment: How susceptible are jobs to computerisation?"*
- **Remote Work Potential:** Dingel & Neiman (2020). *"How Many Jobs Can be Done at Home?"* Journal of Public Economics.
- **Bright Outlook:** O*NET OnLine, National Center for O*NET Development
