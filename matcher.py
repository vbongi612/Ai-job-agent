
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
    """
    Conservative role-fit scorer.

    The previous version rewarded broad skill overlap, which could let unrelated
    jobs (e.g. cybersecurity/audit) through. This version first establishes
    whether the job belongs to the user's target occupational family, then
    scores skills/experience only inside that relevant family.
    """
    title = (job.get("title") or "").lower()
    desc = (job.get("description") or "").lower()
    text = f"{title} {desc}"

    target_roles = [str(x).lower() for x in (profile.get("target_roles") or [])]
    resume_text = (profile.get("resume_text") or "").lower()

    # Explicit occupational families for the user's stated targets.
    target_terms = {
        "organizational development": [
            "organizational development", "organization development", "od consultant",
            "organizational effectiveness", "organization effectiveness"
        ],
        "change management": [
            "change management", "change consultant", "organizational change",
            "change transformation", "change strategy"
        ],
        "people strategy": [
            "people strategy", "people consulting", "people advisory",
            "workforce strategy", "talent strategy", "human capital"
        ],
        "management consulting": [
            "management consulting", "management consultant", "strategy consulting",
            "strategy consultant", "business consulting", "advisory consultant"
        ],
    }

    # Strong exclusion families. A job dominated by these areas should not
    # receive a high fit score merely because it shares generic consulting terms.
    exclusion_terms = {
        "cybersecurity": ["cybersecurity", "cyber security", "penetration testing", "soc", "siem"],
        "it audit": ["it audit", "information technology audit", "technology audit"],
        "software engineering": ["software engineer", "software developer", "full stack", "backend engineer", "frontend engineer"],
        "data science": ["data scientist", "machine learning engineer", "deep learning"],
        "accounting": ["staff accountant", "tax accountant", "audit senior", "public accounting"],
        "nursing": ["registered nurse", "rn ", "nurse practitioner"],
        "physician": ["physician", "surgeon", "medical doctor"],
        "legal": ["attorney", "lawyer", "paralegal"],
        "sales": ["sales development representative", "account executive", "outside sales", "territory sales"],
    }

    # Determine whether title/description contains a meaningful target-family signal.
    family_hits = []
    for family, terms in target_terms.items():
        hits = [t for t in terms if t in text]
        if hits:
            family_hits.append((family, hits))

    exclusion_hits = []
    for family, terms in exclusion_terms.items():
        hits = [t for t in terms if t in text]
        if hits:
            exclusion_hits.append((family, hits))

    title_target_hits = []
    for family, terms in target_terms.items():
        hits = [t for t in terms if t in title]
        if hits:
            title_target_hits.extend(hits)

    title_exclusion_hits = []
    for family, terms in exclusion_terms.items():
        hits = [t for t in terms if t in title]
        if hits:
            title_exclusion_hits.extend(hits)

    # A target-family title is the strongest signal. A target phrase only in a
    # long description is weaker because postings often mention adjacent work.
    if title_target_hits:
        functional = 95
    elif family_hits:
        functional = 75
    else:
        functional = 15

    # Explicit wrong-family title is a hard relevance penalty.
    hard_wrong_family = bool(title_exclusion_hits)
    if hard_wrong_family:
        functional = 0

    # Resume skills/experience overlap.
    profile_skills = set(
        str(x).lower() for x in (profile.get("skills") or [])
        if str(x).strip()
    )
    job_skills = set(
        str(x).lower() for x in (job.get("skill_terms") or [])
        if str(x).strip()
    )

    overlap = 0
    if job_skills:
        overlap = int(100 * len(profile_skills & job_skills) / max(1, len(job_skills)))

    # Relevant experience terms, deliberately broad but only used after role fit.
    experience_terms = [
        "consulting", "organizational development", "change management",
        "organizational effectiveness", "human resources", "human capital",
        "talent", "learning", "development", "facilitation", "stakeholder",
        "strategy", "culture", "dei", "diversity", "inclusion"
    ]
    exp_hits = sum(1 for t in experience_terms if t in resume_text and t in text)
    experience_score = min(100, exp_hits * 12)

    # Final score heavily weights occupational relevance.
    score = int(round(functional * 0.65 + overlap * 0.15 + experience_score * 0.20))
    score = max(0, min(100, score))

    reasons = [
        f"Functional alignment: {functional}%.",
        f"Skill alignment: {overlap}%.",
        f"Relevant experience signal: {experience_score}%.",
    ]

    if title_target_hits:
        reasons.append("Target role family appears directly in the job title.")
    elif family_hits:
        reasons.append("Target role family appears in the job description.")
    else:
        reasons.append("No strong target-role-family signal was found.")

    if hard_wrong_family:
        reasons.append("Job title indicates a different occupational family; do not prioritize.")
    if exclusion_hits:
        reasons.append("Adjacent/unrelated specialty detected: " + ", ".join(x[0] for x in exclusion_hits))

    # Status is intentionally stricter than the numeric score.
    if hard_wrong_family:
        status = "DO_NOT_APPLY"
    elif functional < 50:
        status = "DO_NOT_APPLY"
    elif score >= 80:
        status = "QUALIFIED"
    elif score >= 65:
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
