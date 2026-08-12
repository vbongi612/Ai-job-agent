import json
from pathlib import Path

import streamlit as st
from pypdf import PdfReader

from matcher import score_job, normalize_profile
from openai_adapter import extract_profile_with_openai, evaluate_job_with_openai

st.set_page_config(page_title="AI Job Agent", page_icon="💼", layout="wide")
st.title("💼 AI Job Agent")
st.caption("Resume → qualification-first job matching → application preparation")

if "profile" not in st.session_state:
    st.session_state.profile = None

with st.sidebar:
    st.header("Search criteria")
    roles = st.text_input(
        "Target roles",
        "Organizational Development, Change Management, People Strategy, Management Consulting"
    )
    location = st.text_input("Location", "Chicago, IL")
    work_style = st.multiselect("Work style", ["Hybrid", "Remote", "On-site"], ["Hybrid", "Remote"])
    min_salary = st.number_input("Minimum salary ($)", min_value=0, value=60000, step=5000)
    min_score = st.slider("Minimum match score", 50, 100, 80)

st.subheader("1. Upload your resume")
uploaded = st.file_uploader("PDF resume", type=["pdf"])

if uploaded:
    reader = PdfReader(uploaded)
    resume_text = "\n".join((p.extract_text() or "") for p in reader.pages)
    st.success(f"Read {len(reader.pages)} page(s) from {uploaded.name}")

    if st.button("Build candidate profile", type="primary"):
        with st.spinner("Building profile..."):
            profile = extract_profile_with_openai(resume_text)
            st.session_state.profile = profile or normalize_profile(resume_text)

if st.session_state.profile:
    st.subheader("2. Candidate profile")
    st.json(st.session_state.profile)

st.subheader("3. Jobs")
st.info(
    "Representative job records are included so you can test the matching engine immediately. "
    "Phase 2 replaces these with permitted live job feeds."
)

sample_jobs = json.loads(Path("sample_jobs.json").read_text())
filtered = []

for job in sample_jobs:
    if job.get("salary_min", 0) < min_salary:
        continue

    loc = job.get("location", "").lower()
    city = location.lower().split(",")[0].strip()
    if city not in loc and loc != "remote":
        if "remote" not in [x.lower() for x in work_style]:
            continue

    filtered.append(job)

for job in filtered:
    if st.session_state.profile:
        result = score_job(st.session_state.profile, job)
    else:
        result = {"score": 0, "qualified": False, "reasons": ["Upload a resume first."]}

    if result["score"] < min_score:
        continue

    with st.container(border=True):
        c1, c2 = st.columns([4, 1])
        with c1:
            st.markdown(f"### {job['title']}")
            st.write(f"**{job['company']}** · {job['location']} · {job['employment_type']}")
        with c2:
            st.metric("Match", f"{result['score']}%")

        if result["qualified"]:
            st.success("QUALIFIED")
        else:
            st.error("DO NOT APPLY")

        st.write(job["description"])

        left, right = st.columns(2)
        with left:
            st.markdown("**Qualification analysis**")
            for reason in result["reasons"]:
                st.write("• " + reason)
        with right:
            st.markdown("**Required qualifications**")
            for req in job["required"]:
                st.write("• " + req)

        if st.button("Evaluate with AI", key=f"ai_{job['id']}"):
            ai_result = evaluate_job_with_openai(st.session_state.profile, job)
            if ai_result:
                st.json(ai_result)
            else:
                st.warning("Set OPENAI_API_KEY to enable the AI evaluator.")

st.divider()
st.subheader("Roadmap")
st.markdown("""
**Phase 1 — current:** resume parsing + qualification-first matching

**Phase 2:** live job APIs / permitted feeds + database + deduplication

**Phase 3:** tailored resume + cover letter + application-question generator

**Phase 4:** application autofill with human approval

**Phase 5:** controlled auto-submit for sites where automation is permitted
""")
