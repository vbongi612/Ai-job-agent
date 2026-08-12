
import re
import html

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
    "employee listening", "employee engagement", "survey", "surveys",
    "interviews", "focus groups", "qualitative", "thematic analysis",
    "qualitative coding", "executive reporting", "executive presentation",
    "project management", "program management", "facilitation",
    "workshop", "excel", "powerpoint", "human resources", "hr"
]

def clean_html(text):
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</p\s*>", "\n", text, flags=re.I)
    text = re.sub(r"</li\s*>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()

def normalize_profile(text):
    t = text.lower()

    years = 0
    matches = re.findall(r"(\d+)\+?\s*years?\s+(?:of\s+)?experience", t)
    if matches:
        years = max(map(int, matches))
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
        "resume_text": text,
    }

def _text(job):
    description = clean_html(job.get("description", ""))
    return " ".join([
        str(job.get("title", "")),
        description,
        " ".join(map(str, job.get("role_terms", []))),
        " ".join(map(str, job.get("skill_terms", []))),
    ]).lower()

def score_job(profile, job):
    text = _text(job)
    title = str(job.get("title", "")).lower()
    reasons = []

    actual_years = profile.get("years_experience", 0)

    year_matches = [int(x) for x in re.findall(r"(\d+)\+?\s+years?", text)]
    required_years = max(year_matches) if year_matches else 0

    hard_fail = False
    verification_gap = False

    if required_years and actual_years < required_years:
        hard_fail = True
        reasons.append(
            f"Experience gap: posting appears to require {required_years}+ years; "
            f"your profile shows {actual_years}+."
        )

    senior_terms = ["senior consultant", "senior manager", "director", "principal", "lead consultant"]
    if any(term in title for term in senior_terms) and actual_years < 5:
        hard_fail = True
        reasons.append("Seniority concern: this is a senior/leadership-level title relative to your experience.")

    experience_language = [
        "deep expertise", "extensive experience", "proven track record",
        "expert in", "subject matter expert"
    ]
    if any(term in text for term in experience_language) and required_years == 0:
        verification_gap = True
        reasons.append(
            "The posting asks for substantial expertise but gives no numeric experience threshold; "
            "qualification cannot be fully verified from the available data."
        )

    role_hits = sum(1 for terms in ROLE_MAP.values() if any(term in text for term in terms))
    role_score = min(100, role_hits * 20)

    profile_skills = profile.get("skills", [])
    skill_hits = sum(skill in text for skill in profile_skills)
    skill_score = min(100, round(skill_hits / max(len(profile_skills), 1) * 100))

    exp_score = 100 if not required_years else min(100, round(actual_years / required_years * 100))

    score = round(
        0.35 * (0 if hard_fail else 100)
        + 0.25 * exp_score
        + 0.25 * skill_score
        + 0.15 * role_score
    )

    if role_score:
        reasons.append(f"Functional alignment: {role_score}%.")
    if skill_score:
        reasons.append(f"Skill alignment: {skill_score}%.")
    if required_years:
        reasons.append(
            f"Experience check: {actual_years}+ years vs. approximately {required_years}+ in the posting."
        )

    if hard_fail:
        status = "DO NOT APPLY"
    elif verification_gap:
        status = "REVIEW"
    elif score >= 75:
        status = "QUALIFIED"
        reasons.append("No detected hard qualification failure.")
    else:
        status = "REVIEW"

    return {
        "score": max(0, min(100, score)),
        "qualified": status == "QUALIFIED",
        "status": status,
        "reasons": reasons,
    }

def _status(requirement, profile, text):
    r = requirement.lower()
    years = profile.get("years_experience", 0)
    skills = " ".join(profile.get("skills", [])).lower()
    roles = " ".join(profile.get("roles", [])).lower()
    resume = profile.get("resume_text", "").lower()

    nums = re.findall(r"(\d+)\+?\s+years?", r)
    if nums:
        needed = int(nums[0])
        if years >= needed:
            return "MEETS", f"Your profile indicates {years}+ years of experience."
        return "MISSING", f"Your profile indicates {years}+ years, below the stated {needed}+ years."

    if "bachelor" in r or "b.s." in r:
        if profile.get("degree"):
            return "MEETS", "A bachelor's degree is represented in the resume."
        return "MISSING", "No bachelor's degree was detected in the resume."

    terms = {
        "organizational development": ["organizational development", "organizational effectiveness"],
        "change management": ["change management"],
        "human resources": ["human resources", "hr"],
        "consulting": ["consulting", "consultant", "advisory"],
        "stakeholder": ["stakeholder"],
        "facilitation": ["facilitation", "facilitating", "workshop"],
        "project management": ["project management", "program management"],
        "qualitative": ["qualitative", "thematic", "interviews", "focus groups"],
    }

    for label, variants in terms.items():
        if label in r or any(v in r for v in variants):
            if any(v in resume or v in skills or v in roles for v in variants):
                return "MEETS", f"Relevant evidence was detected for {label}."
            return "MISSING", f"No clear resume evidence was detected for {label}."

    if any(x in r for x in ["deep expertise", "extensive experience", "proven track record", "expert"]):
        return "CANNOT_VERIFY", "The posting asks for substantial expertise, but the available resume/profile data cannot verify the depth required."

    return "CANNOT_VERIFY", "This requirement needs semantic review of the full resume and posting."

def requirement_matrix(profile, job):
    text = clean_html(job.get("description", ""))
    if not text:
        return []

    # Extract bullet-like requirements and requirement sentences.
    candidates = []
    for line in text.splitlines():
        line = line.strip(" •-\t")
        if len(line) >= 20 and len(line) <= 240:
            if any(k in line.lower() for k in [
                "required", "qualification", "experience", "degree", "ability",
                "knowledge", "expertise", "skills", "you will", "must"
            ]):
                candidates.append(line)

    sentences = re.split(r"(?<=[.!?])\s+", text)
    for s in sentences:
        s = s.strip()
        if 30 <= len(s) <= 240 and any(k in s.lower() for k in [
            "requires", "required", "experience", "degree", "expertise",
            "ability", "knowledge", "skills", "must have"
        ]):
            candidates.append(s)

    # Deduplicate while preserving order.
    out = []
    seen = set()
    for c in candidates:
        key = re.sub(r"\W+", " ", c.lower()).strip()
        if key and key not in seen:
            seen.add(key)
            status, evidence = _status(c, profile, text.lower())
            out.append({
                "requirement": c,
                "status": status,
                "evidence": evidence
            })

    return out[:12]
