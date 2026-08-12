import re

def normalize_profile(text):
    t = text.lower()

    def has_any(words):
        return [w for w in words if w.lower() in t]

    years = 0
    m = re.search(r"(\d+)\+?\s*years?\s+of\s+experience", t)
    if m:
        years = int(m.group(1))

    degree = "Bachelor's" if ("b.s." in t or "bachelor" in t) else None

    return {
        "years_experience": years,
        "degree": degree,
        "roles": has_any([
            "organizational development", "change management",
            "people strategy", "consulting", "culture transformation"
        ]),
        "skills": has_any([
            "stakeholder management", "organizational assessment",
            "employee listening", "surveys", "interviews", "focus groups",
            "qualitative coding", "thematic analysis", "executive reporting",
            "project management", "facilitation", "excel", "powerpoint"
        ]),
        "industries": has_any(["entertainment", "biotech", "marketing"]),
    }


def score_job(profile, job):
    reasons = []
    hard_fail = False

    required_years = job.get("min_years_experience", 0)
    actual_years = profile.get("years_experience", 0)

    if actual_years < required_years:
        hard_fail = True
        reasons.append(
            f"Experience gap: requires {required_years}+ years; profile shows about {actual_years}."
        )

    required_degree = job.get("required_degree")
    if required_degree and profile.get("degree") != required_degree:
        hard_fail = True
        reasons.append(f"Education requirement not demonstrated: {required_degree}.")

    profile_text = " ".join(
        str(v) for v in
        profile.get("roles", []) +
        profile.get("skills", []) +
        profile.get("industries", [])
    ).lower()

    role_terms = [x.lower() for x in job.get("role_terms", [])]
    skill_terms = [x.lower() for x in job.get("skill_terms", [])]

    role_hits = sum(term in profile_text for term in role_terms)
    skill_hits = sum(term in profile_text for term in skill_terms)

    role_score = 100 if not role_terms else round(role_hits / len(role_terms) * 100)
    skill_score = 100 if not skill_terms else round(skill_hits / len(skill_terms) * 100)
    experience_score = 100 if actual_years >= required_years else max(
        0, round(actual_years / max(required_years, 1) * 100)
    )
    education_score = 100 if not required_degree or profile.get("degree") == required_degree else 0

    score = round(
        0.30 * (0 if hard_fail else 100)
        + 0.25 * experience_score
        + 0.20 * skill_score
        + 0.10 * role_score
        + 0.05 * education_score
        + 0.10 * min(100, (role_score + skill_score) / 2)
    )

    if not hard_fail:
        reasons.extend([
            f"Experience: {actual_years}+ years vs. {required_years}+ required.",
            f"Role/function alignment: {role_score}%.",
            f"Skill alignment: {skill_score}%.",
            "No hard qualification failure detected."
        ])
    else:
        reasons.append("Hard requirement failure means this should not be treated as an application target.")

    return {
        "score": max(0, min(100, score)),
        "qualified": not hard_fail and score >= 70,
        "reasons": reasons,
    }
