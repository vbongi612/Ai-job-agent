
import json
import os
import re

def _secret(name):
    value = os.getenv(name)
    try:
        import streamlit as st
        if not value and name in st.secrets:
            value = st.secrets[name]
    except Exception:
        pass
    return str(value).strip() if value is not None else ""

def _extract_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if match:
            return json.loads(match.group(0))
    return None

def ai_screen_job(resume_text, job):
    key = _secret("OPENAI_API_KEY")
    if not key:
        return None

    try:
        from openai import OpenAI
    except Exception:
        return None

    client = OpenAI(api_key=key)
    model = _secret("OPENAI_MODEL") or "gpt-5.6"

    description = job.get("description", "") or ""
    title = job.get("title", "")
    company = job.get("company", "")
    location = job.get("location", "")

    prompt = f"""
You are a conservative job-qualification engine for a real job seeker.

Your job is NOT to make the candidate look better than the evidence supports.
Compare the candidate's resume against the complete job posting.

Rules:
1. Separate REQUIRED/MUST-HAVE qualifications from PREFERRED qualifications whenever the posting allows it.
2. MEETS means the resume clearly demonstrates the requirement.
3. PARTIAL means related experience exists, but the exact requirement is not fully demonstrated.
4. MISSING means the resume clearly lacks a stated required qualification or contradicts it.
5. CANNOT_VERIFY means the requirement is subjective or the posting/resume does not contain enough evidence.
6. Do not infer years of experience from job seniority alone.
7. Do not convert a general skill into specialized expertise unless the resume supports the specialization.
8. If a required degree, certification, license, location, work authorization, or numeric experience requirement is absent or contradicted, flag it.
9. If the job asks for "deep expertise", "extensive experience", "expert", "proven track record", etc., do not automatically treat ordinary exposure as MEETS.
10. A candidate can receive APPLY only when there is no important unverified or missing required qualification.
11. If an important requirement cannot be verified, prefer REVIEW.
12. DO_NOT_APPLY is appropriate when a hard requirement is clearly missing.

Return ONLY JSON in this exact shape:
{{
  "recommendation": "APPLY" | "REVIEW" | "DO_NOT_APPLY",
  "summary": "2-4 sentence explanation",
  "hard_failures": ["..."],
  "requirements": [
    {{
      "requirement": "specific requirement from the posting",
      "importance": "REQUIRED" | "PREFERRED" | "UNCLEAR",
      "status": "MEETS" | "PARTIAL" | "MISSING" | "CANNOT_VERIFY",
      "evidence": "specific evidence from the resume, or why it cannot be verified"
    }}
  ]
}}

JOB:
Title: {title}
Company: {company}
Location: {location}

JOB DESCRIPTION:
{description}

CANDIDATE RESUME:
{resume_text}
"""

    try:
        response = client.responses.create(
            model=model,
            input=prompt,
        )
        return _extract_json(response.output_text)
    except Exception:
        return None
