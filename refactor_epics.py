import os

epics_path = "docs/HAYSTACK_EPICS.md"
archive_path = "docs/archive/phase_1_ipeds/COMPLETED_EPICS_0_9.md"

with open(epics_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

header = lines[0:8]
epics_0_to_9 = []
deferred = []
timeline = []
epic_10 = []
rest = []

# Manually slicing based on earlier inspection:
# Epic 0 starts around line 8.
# "## Deferred to Phase 2+" is line 429
# "## Realistic timeline (solo)" is line 450
# "## Epic 10 - Inverse Search" is line 480
# "## Epic 11 - Ecosystem" is line 516

current_section = "header"
for line in lines[8:]:
    if line.startswith("## Deferred to Phase 2+"):
        current_section = "deferred"
        deferred.append(line)
    elif line.startswith("## Realistic timeline (solo)"):
        current_section = "timeline"
        timeline.append(line)
    elif line.startswith("## Epic 10 — Inverse Search"):
        current_section = "epic10"
        epic_10.append(line)
    elif line.startswith("## Epic 11"):
        current_section = "rest"
        rest.append(line)
    else:
        if current_section == "header":
            epics_0_to_9.append(line)
        elif current_section == "deferred":
            deferred.append(line)
        elif current_section == "timeline":
            timeline.append(line)
        elif current_section == "epic10":
            epic_10.append(line)
        elif current_section == "rest":
            rest.append(line)

# Write out the archive:
with open(archive_path, "w", encoding="utf-8") as f:
    f.write("# Phase 1 Completed Epics Archive\n\n")
    f.writelines(epics_0_to_9)
    f.writelines(epic_10)

# Build the new active HAYSTACK_EPICS
new_active = []
new_active.extend(header)

intro_text = """
> **Note:** Phase 1 (IPEDS Foundation, Epics 0-9) has been completed.
> V1 specifications and historical task lists are archived in `docs/archive/phase_1_ipeds/`.
> This document traces the Phase 2 expansion.

---

## Active Roadmap (Phase 2)

| Epic | Focus | Status |
|---|---|---|
| **10. Non-Title IV Training Base** | WIOA ETPL, Apprenticeships, WEAMS | 🏃 Next Up |
| **11. Workforce Connections** | BLS OEWS wage & demand integration | 🔲 Planned |
| **12. Ecosystem & Network View** | IRS 990 / Nonprofits relationships | 🔲 Planned |
| **13. Briefing Builder** | Deliverable / export generation | 🔲 Planned |

---

"""
new_active.append(intro_text)
new_active.extend(rest)

with open(epics_path, "w", encoding="utf-8") as f:
    f.writelines(new_active)

print("Sliced HAYSTACK_EPICS.md successfully!")
