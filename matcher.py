
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



def score_job(profile, job, target_roles=None):
    """
    Target-role-driven matcher.

    target_roles comes directly from the app's Target roles field. The matcher
    treats those phrases as the primary occupational relevance signal and does
    not assume a fixed career family.
    """
    title = (job.get("title") or "").lower()
    desc = (job.get("description") or "").lower()
    text = f"{title} {desc}"

    # The UI is the source of truth for what the user wants to find.
    requested_roles = [
        str(x).strip().lower()
        for x in (target_roles or [])
        if str(x).strip()
    ]

    # Match exact/near phrase signals from the target-role field.
    role_hits = []
    title_role_hits = []
    for role in requested_roles:
        # Full phrase match is strongest.
        if role in text:
            role_hits.append(role)
        if role in title:
            title_role_hits.append(role)
            continue

        # For multi-word role phrases, allow a title to contain most
        # meaningful words while avoiding generic filler terms.
        words = [
            w for w in re.findall(r"[a-z0-9]+", role)
            if w not in {"and", "or", "the", "of", "for", "in", "to"}
            and len(w) >= 3
        ]
        if len(words) >= 2:
            title_words = set(re.findall(r"[a-z0-9]+", title))
            hits = sum(1 for w in words if w in title_words)
            if hits >= max(2, int(len(words) * 0.67)):
                title_role_hits.append(role)

    # If the user entered roles, relevance is driven by those roles.
    # Title matches are strongest, body matches are meaningful but weaker.
    if title_role_hits:
        functional = 100
    elif role_hits:
        functional = 80
    elif requested_roles:
        # Give a small amount of credit only for broad semantic overlap,
        # based on individual meaningful words from the requested roles.
        meaningful = set()
        for role in requested_roles:
            meaningful.update(
                w for w in re.findall(r"[a-z0-9]+", role)
                if w not in {"and", "or", "the", "of", "for", "in", "to"}
                and len(w) >= 4
            )
        text_words = set(re.findall(r"[a-z0-9]+", text))
        word_hits = len(meaningful & text_words)
        functional = min(55, word_hits * 12)
    else:
        # No target roles: do not invent a career direction.
        functional = 0

    # Skill overlap is secondary to role relevance.
    profile_skills = set(
        str(x).lower() for x in (profile.get("skills") or [])
        if str(x).strip()
    )
    job_skills = set(
        str(x).lower() for x in (job.get("skill_terms") or [])
        if str(x).strip()
    )
    overlap = int(100 * len(profile_skills & job_skills) / max(1, len(job_skills))) if job_skills else 0

    resume_text = (profile.get("resume_text") or "").lower()
    experience_terms = [
        "consulting", "organizational development", "change management",
        "organizational effectiveness", "human resources", "human capital",
        "talent", "learning", "development", "facilitation", "stakeholder",
        "strategy", "culture", "dei", "diversity", "inclusion"
    ]
    exp_hits = sum(1 for t in experience_terms if t in resume_text and t in text)
    experience_score = min(100, exp_hits * 12)

    score = int(round(functional * 0.70 + overlap * 0.12 + experience_score * 0.18))
    score = max(0, min(100, score))

    reasons = [
        f"Target-role alignment: {functional}%.",
        f"Skill alignment: {overlap}%.",
        f"Relevant experience signal: {experience_score}%.",
    ]

    if title_role_hits:
        reasons.append("Target role phrase appears in the job title: " + ", ".join(title_role_hits))
    elif role_hits:
        reasons.append("Target role phrase appears in the job description: " + ", ".join(role_hits))
    elif requested_roles:
        reasons.append("No strong direct target-role phrase match was found.")
    else:
        reasons.append("No target roles were entered.")

    # A job must have a meaningful target-role relationship to be surfaced.
    if not requested_roles:
        status = "REVIEW" if score >= 65 else "DO_NOT_APPLY"
    elif title_role_hits:
        status = "QUALIFIED" if score >= 75 else "REVIEW"
    elif role_hits:
        status = "QUALIFIED" if score >= 80 else "REVIEW"
    elif functional >= 50:
        status = "REVIEW"
    else:
        status = "DO_NOT_APPLY"

    return {
        "score": score,
        "status": status,
        "reasons": reasons,
        "functional_alignment": functional,
        "skill_alignment": overlap,
    }

def _status(requirement, profile, job_text):
    """
    Classify an extracted job requirement against the resume profile.

    This helper was missing in the previous v13 build, which caused the
    NameError shown in the app when requirement analysis was expanded.
    """
    req = (requirement or "").lower()
    resume = str(profile.get("resume_text", "")).lower()

    # Strong negative signals: explicit requirements that are clearly absent.
    degree_required = any(x in req for x in [
        "bachelor", "b.s.", "b.a.", "master", "m.s.", "m.a.", "mba",
        "degree required", "degree in"
    ])
    if degree_required and not profile.get("degree"):
        return "MISSING", "No matching degree was detected in the resume."

    # Experience requirement.
    years = 0
    import re as _re
    year_matches = [int(x) for x in _re.findall(r"(\d+)\+?\s*years?", req)]
    if year_matches:
        required_years = max(year_matches)
        candidate_years = int(profile.get("years_experience") or 0)
        if candidate_years >= required_years:
            return "MATCH", f"Resume profile indicates about {candidate_years} years of experience."
        if candidate_years:
            return "PARTIAL", f"Resume profile indicates about {candidate_years} years; requirement asks for {required_years}."
        return "MISSING", f"Requirement asks for {required_years}+ years; no matching years were detected."

    # Skills/keywords: use the profile's detected skills first, then exact
    # phrase presence in the resume.
    profile_skills = set(str(x).lower() for x in (profile.get("skills") or []))
    for skill in profile_skills:
        if skill in req:
            return "MATCH", f"Resume contains the related skill: {skill}."

    # Role/domain evidence.
    role_terms = set(str(x).lower() for x in (profile.get("roles") or []))
    for role in role_terms:
        if role in req:
            return "MATCH", f"Resume profile contains related role/domain experience: {role}."

    # Direct phrase evidence from the resume.
    meaningful = [
        w for w in _re.findall(r"[a-z][a-z-]{3,}", req)
        if w not in {"required", "preferred", "experience", "ability", "knowledge",
                     "skills", "candidate", "years", "working", "including",
                     "strong", "excellent"}
    ]
    hits = [w for w in meaningful if w in resume]
    if len(hits) >= 2:
        return "MATCH", "Resume contains multiple relevant requirement terms: " + ", ".join(hits[:5]) + "."

    if hits:
        return "PARTIAL", "Resume contains some related terminology: " + hits[0] + "."

    return "UNCLEAR", "The available resume text does not provide enough evidence to verify this requirement."

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
