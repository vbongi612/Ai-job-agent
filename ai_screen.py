
import json
import os

def _get_key():
    key = os.getenv("OPENAI_API_KEY")
    try:
        import streamlit as st
        key = key or st.secrets.get("OPENAI_API_KEY")
    except Exception:
        pass
    return key

def ai_screen_job(profile, job):
    key = _get_key()
    if not key:
        return None

    try:
        from openai import OpenAI
    except Exception:
        return None

    client = OpenAI(api_key=key)

    resume = profile.get("resume_text", "")
    description = job.get("description", "")

    prompt = f"""
You are a conservative job-qualification screening engine.

Compare the candidate resume against the complete job posting.
Do NOT infer qualifications that are not supported by the resume.
Do NOT treat keyword overlap as proof of experience.
A requirement is:
- MEETS only when the resume clearly supports it.
- PARTIAL when related evidence exists but the exact requirement is not fully demonstrated.
- MISSING when the resume conflicts with or lacks a required qualification.
- CANNOT_VERIFY when the wording is subjective or the available posting/resume does not allow a reliable determination.

Return ONLY valid JSON with this structure:
{{
  "recommendation": "APPLY" | "REVIEW" | "DO_NOT_APPLY",
  "summary": "brief explanation",
  "requirements": [
    {{
      "requirement": "specific requirement",
      "status": "MEETS" | "PARTIAL" | "MISSING" | "CANNOT_VERIFY",
      "evidence": "resume evidence or explanation"
    }}
  ]
}}

CANDIDATE RESUME:
{resume}

JOB POSTING:
{description}
"""

    try:
        response = client.responses.create(
            model="gpt-5.6",
            input=prompt
        )
        text = response.output_text.strip()
        return json.loads(text)
    except Exception:
        return None
