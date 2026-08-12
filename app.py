
import json
import os

import streamlit as st
from pypdf import PdfReader

from matcher import normalize_profile, score_job, clean_html, requirement_matrix
from jobs_api import search_himalayas, search_adzuna
from ai_screen import ai_screen_job

st.set_page_config(page_title="AI Job Agent", page_icon="💼", layout="wide")
st.title("💼 AI Job Agent")
st.caption("Live jobs → requirement-by-requirement screening → ranked applications")

if "profile" not in st.session_state:
    st.session_state.profile = None

with st.sidebar:
    st.header("Job criteria")
    roles_text = st.text_area(
        "Target roles",
        "Organizational Development\nChange Management\nPeople Strategy\nManagement Consulting"
    )
    location = st.text_input("Location", "Chicago, IL")
    work_style = st.multiselect(
        "Work style",
        ["Hybrid", "Remote", "On-site"],
        ["Hybrid", "Remote"]
    )
    min_salary = st.number_input("Minimum salary ($)", min_value=0, value=60000, step=5000)
    min_score = st.slider("Minimum match score", 50, 100, 80)
    max_results = st.slider("Maximum jobs to analyze", 10, 50, 20)
    use_ai = st.checkbox("Use AI requirement analysis", value=True)
    st.caption("AI analysis requires an OpenAI API key in Streamlit Secrets. The rule-based screen works without one.")

st.subheader("1. Resume")
uploaded = st.file_uploader("Upload your resume PDF", type=["pdf"])

if uploaded:
    reader = PdfReader(uploaded)
    resume_text = "\n".join((p.extract_text() or "") for p in reader.pages)
    st.success(f"Read {len(reader.pages)} page(s).")

    if st.button("Build candidate profile", type="primary"):
        st.session_state.profile = normalize_profile(resume_text)

if st.session_state.profile:
    with st.expander("Candidate profile", expanded=False):
        st.json(st.session_state.profile)

st.subheader("2. Find live jobs")

if not st.session_state.profile:
    st.info("Upload your resume and build the candidate profile first.")
else:
    if st.button("🔎 Find live jobs", type="primary"):
        role_queries = [x.strip() for x in roles_text.splitlines() if x.strip()]
        jobs = []

        if "Remote" in work_style:
            for q in role_queries[:4]:
                try:
                    jobs.extend(search_himalayas(q, country="US", limit=max_results))
                except Exception as e:
                    st.warning(f"Remote feed error for '{q}': {e}")

        if "Chicago" in location:
            try:
                jobs.extend(search_adzuna(
                    query=" OR ".join(role_queries[:3]),
                    where="Chicago",
                    salary_min=min_salary,
                    limit=max_results
                ))
            except RuntimeError as e:
                st.info(str(e))
            except Exception as e:
                st.warning(f"Chicago feed error: {e}")

        unique = {}
        for j in jobs:
            key = j.get("id") or j.get("url") or (j.get("title"), j.get("company"))
            unique[key] = j
        jobs = list(unique.values())

        if not jobs:
            st.warning(
                "No live jobs were returned. Remote search works without a key. "
                "Chicago search requires Adzuna credentials in Streamlit Secrets."
            )
        else:
            scored = []
            for job in jobs:
                result = score_job(st.session_state.profile, job)
                if job.get("salary_min") and job["salary_min"] < min_salary:
                    continue
                scored.append((result, job))

            scored.sort(
                key=lambda x: (
                    x[0]["status"] == "QUALIFIED",
                    x[0]["status"] == "REVIEW",
                    x[0]["score"]
                ),
                reverse=True
            )

            displayed = [x for x in scored if x[0]["score"] >= min_score][:max_results]
            st.success(
                f"Analyzed {len(scored)} live listings; showing {len(displayed)} above your threshold."
            )

            for idx, (result, job) in enumerate(displayed):
                with st.container(border=True):
                    left, right = st.columns([4, 1])

                    with left:
                        st.markdown(f"### {job['title']}")
                        st.write(
                            f"**{job['company']}** · {job.get('location', 'Not specified')} "
                            f"· {job.get('employment_type', 'Not specified')}"
                        )
                        if job.get("source"):
                            st.caption(f"Source: {job['source']}")

                    with right:
                        st.metric("Match", f"{result['score']}%")

                    if result["status"] == "QUALIFIED":
                        st.success("QUALIFIED — worth applying")
                    elif result["status"] == "REVIEW":
                        st.warning("REVIEW — relevant, but qualification is not fully verified")
                    else:
                        st.error("DO NOT APPLY")

                    description = clean_html(job.get("description", ""))
                    if description:
                        with st.expander("Job description", expanded=False):
                            st.write(description)

                    st.markdown("**Initial screening**")
                    for reason in result["reasons"]:
                        st.write("• " + reason)

                    # Requirement-by-requirement screen.
                    with st.expander("🎯 Requirement-by-requirement analysis", expanded=True):
                        matrix = requirement_matrix(st.session_state.profile, job)

                        if matrix:
                            for req in matrix:
                                status = req["status"]
                                if status == "MEETS":
                                    st.success(f"✅ **MEETS** — {req['requirement']}\n\n{req['evidence']}")
                                elif status == "PARTIAL":
                                    st.warning(f"🟡 **PARTIAL** — {req['requirement']}\n\n{req['evidence']}")
                                elif status == "MISSING":
                                    st.error(f"❌ **NOT DEMONSTRATED** — {req['requirement']}\n\n{req['evidence']}")
                                else:
                                    st.info(f"❓ **CANNOT VERIFY** — {req['requirement']}\n\n{req['evidence']}")
                        else:
                            st.info("No explicit requirements could be extracted from this listing.")

                        if use_ai:
                            if st.button("Run AI requirement analysis", key=f"ai_{idx}"):
                                with st.spinner("Reading the resume and full job description..."):
                                    ai_result = ai_screen_job(
                                        st.session_state.profile,
                                        job
                                    )
                                if ai_result:
                                    st.markdown("### AI screening result")
                                    if ai_result.get("recommendation") == "APPLY":
                                        st.success("AI recommendation: APPLY")
                                    elif ai_result.get("recommendation") == "REVIEW":
                                        st.warning("AI recommendation: REVIEW")
                                    else:
                                        st.error("AI recommendation: DO NOT APPLY")

                                    st.write(ai_result.get("summary", ""))
                                    for item in ai_result.get("requirements", []):
                                        s = item.get("status", "CANNOT_VERIFY")
                                        icon = {"MEETS": "✅", "PARTIAL": "🟡", "MISSING": "❌", "CANNOT_VERIFY": "❓"}.get(s, "❓")
                                        st.write(f"{icon} **{s}** — {item.get('requirement', '')}")
                                        if item.get("evidence"):
                                            st.caption(item["evidence"])
                                else:
                                    st.warning(
                                        "AI screening is not configured. Add OPENAI_API_KEY to Streamlit Secrets."
                                    )

                    if job.get("salary"):
                        st.write(f"**Salary:** {job['salary']}")

                    if job.get("url"):
                        st.link_button("View / Apply", job["url"])

st.divider()
st.caption(
    "This version screens applications conservatively. It does not submit applications automatically."
)
