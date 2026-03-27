"""
cip_utils.py — Shared CIP code helpers for The Haystack.

Imported by routes/fields.py and routes/programs.py.
Do not add Flask or SQLAlchemy imports here — keep this pure Python.
"""

# ---------------------------------------------------------------------------
# 2-digit CIP family → human-readable label
# Source: NCES Classification of Instructional Programs (CIP 2020)
# ---------------------------------------------------------------------------
CIP_FAMILY_NAMES: dict[str, str] = {
    "01": "Agriculture",
    "03": "Natural Resources",
    "04": "Architecture",
    "05": "Area & Cultural Studies",
    "09": "Communication",
    "10": "Communications Tech",
    "11": "Computer Science",
    "12": "Personal Services",
    "13": "Education",
    "14": "Engineering",
    "15": "Engineering Tech",
    "16": "Foreign Languages",
    "19": "Family Sciences",
    "22": "Legal",
    "23": "English",
    "24": "Liberal Arts",
    "25": "Library Science",
    "26": "Biology",
    "27": "Mathematics",
    "28": "Military",
    "29": "Military Tech",
    "30": "Interdisciplinary",
    "31": "Parks & Recreation",
    "38": "Philosophy",
    "39": "Theology",
    "40": "Physical Sciences",
    "41": "Science Tech",
    "42": "Psychology",
    "43": "Homeland Security",
    "44": "Public Admin",
    "45": "Social Sciences",
    "46": "Construction",
    "47": "Mechanic & Repair",
    "48": "Precision Production",
    "49": "Transportation",
    "50": "Visual & Performing Arts",
    "51": "Health Professions",
    "52": "Business",
    "54": "History",
    "60": "Residency Programs",
}


def cip_family_label(cip: str) -> str:
    """
    Return 'Health Professions (51)' style label for a CIP code.
    Works for both 2-digit family codes ('51') and full CIP codes ('51.3801').
    """
    if not cip:
        return "—"
    family = cip.split(".")[0] if "." in cip else cip[:2]
    name = CIP_FAMILY_NAMES.get(family, "")
    return f"{name} ({family})" if name else family


def cip_title(program_name: str) -> str:
    """
    Strip the credential suffix from a stored program name.
    Stored format: 'Nursing — Associate Degree'
    Returns: 'Nursing'
    """
    if " — " in program_name:
        return program_name.split(" — ")[0].strip()
    return program_name


def cip_family_code(cip: str) -> str | None:
    """
    Extract the 2-digit family code from a CIP string.
    Returns None if cip is empty or unparseable.
    """
    if not cip:
        return None
    return cip.split(".")[0] if "." in cip else cip[:2]
