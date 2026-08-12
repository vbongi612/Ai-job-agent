import os
import json

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

def _client():
    key = os.getenv("OPENAI_API_KEY")
    if not key or OpenAI is None:
        return None
    return OpenAI(api_key=key)

def extract_profile_with_openai(resume_text):
    client = _client()
    if not client:
        return None

    prompt = """Extract a structured job-search candidate profile from this resume.
Do not invent qualifications. Return JSON with:
years_experience, degree, roles, skills, industries, evidence.
Use only information supported by the resume.

RESUME:
""" + resume_text

    response = client.responses.create(model="gpt-5.6", input=prompt)
    try:
        return json.loads(response.output_text)
    except Exception:
        return None

def evaluate_job_with_openai(profile, job):
    client = _client()
    if not client:
        return None

    prompt = f"""Evaluate this candidate against this job.
Prioritize explicit required qualifications over keyword similarity.
Never invent experience.
Return JSON:
score_0_100, qualified_boolean, hard_failures, strong_matches, gaps, recommendation.

CANDIDATE:
{json.dumps(profile)}

JOB:
{json.dumps(job)}
"""

    response = client.responses.create(model="gpt-5.6", input=prompt)
    try:
        return json.loads(response.output_text)
    except Exception:
        return {"raw": response.output_text}
