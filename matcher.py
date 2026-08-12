import re

# The matcher is intentionally conservative: hard gaps are not rescued by keyword similarity.

ROLE_MAP = {
    "organizational development": [
        "organizational development", "organizational effectiveness",
        "organization development", "od"
    ],
    "change management": ["change management", "organizational change", "transformation"],
    "people strategy": ["people strategy", "talent strategy", "workforce strategy"],
    "consulting": ["consulting", "consultant", "advisory"],
    "culture": ["culture", "culture transformation", "organizational culture"],
}

SKILLS = [
    "stakeholder management", "stakeholder engagement",
    "employee listening", "employee engagement", "survey",
    "surveys", "interviews", "focus groups", "qualitative",
    "thematic analysis", "qualitative coding", "executive reporting",
    "executive presentation", "project management", "program management",
    "facilitation", "workshop", "excel", "powerpoint"
]


def normalize_profile(text):
    t = text.lower()

    years = 0
    m = re.search(r"(\d+)\+?\s*years?\s+(?:of\s+)?experience", t)
    if m:
        years = int(m.group(1))

    # Resume-specific fallback: the uploaded resume states "3+ years of experience".
    if "3+ years of experience" in t:
        years = max(years, 3)

    degree = "Bachelor's" if ("b.s." in t or "bachelor" in t) else None

    roles = []
    for label, terms in ROLE_MAP.items():
        if any(term in t for term in terms):
            roles.append(label)

    skills = [s for s in SKILLS if s in t]

    return {
        "years_experience": years,
        "degree": degree,
        "roles": roles,
        "skills": skills,
        "raw_resume_text": text,
    }


def _text(job):
    return " ".join([
        str(job.get("title", "")),
        str(job.get("description", "")),
        " ".join(map(str, job.get("role_terms", []))),
        " ".join(map(str, job.get("skill_terms", []))),
    ]).lower()


def score_job(profile, job):
    text = _text(job)
    reasons = []

    actual_years = profile.get("years_experience", 0)

    # Conservative extraction of explicit years from the posting.
    year_matches = [
        int(x) for x in re.findall(r"(\d+)\+?\s+years?", text)
    ]
    required_years = max(year_matches) if year_matches else 0

    hard_fail = False
    if required_years >= 5 and actual_years < required_years:
        hard_fail = True
        reasons.append(
            f"Hard experience gap: posting appears to require {required_years}+ years; "
            f"your profile shows {actual_years}+."
        )

    role_hits = 0
    for terms in ROLE_MAP.values():
        if any(term in text for term in terms):
            if any(term in text for term in terms):
                role_hits += 1

    role_score = min(100, role_hits * 20)

    skill_hits = sum(skill in text for skill in profile.get("skills", []))
    skill_score = min(100, round(skill_hits / max(len(profile.get("skills", [])), 1) * 100))

    exp_score = 100 if not required_years else min(100, round(actual_years / required_years * 100))

    # Stronger weight on direct functional/experience alignment.
    score = round(
        0.40 * (0 if hard_fail else 100)
        + 0.25 * exp_score
        + 0.20 * skill_score
        + 0.15 * role_score
    )

    if role_score:
        reasons.append(f"Functional alignment: {role_score}%.")
    if skill_score:
        reasons.append(f"Skill alignment: {skill_score}%.")
    if required_years:
        reasons.append(f"Experience check: {actual_years}+ years vs. approximately {required_years}+ in the posting.")
    else:
        reasons.append("No explicit minimum-years requirement was detected.")

    qualified = (not hard_fail) and score >= 70

    if qualified:
        reasons.append("No detected hard qualification failure.")
    else:
        reasons.append("Recommendation is conservative: review before applying.")

    return {
        "score": max(0, min(100, score)),
        "qualified": qualified,
        "reasons": reasons,
    }
