
import json
import os
import re
from pathlib import Path

import streamlit as st
from pypdf import PdfReader

from matcher import normalize_profile, score_job, clean_html, requirement_matrix
from jobs_api import search_himalayas, search_adzuna, test_adzuna
from ai_screen import ai_screen_job

st.set_page_config(page_title="AI Job Agent", page_icon="💼", layout="wide")

# Streamlit reruns the script after button clicks. Session state normally survives,
# but we also persist the extracted profile in a small server-side JSON file so a
# transient rerun/reconnect doesn't force the user to upload the resume again.
STATE_FILE = Path("/tmp/ai_job_agent_state.json")

def load_saved_state():
    try:
        if STATE_FILE.exists():
            return json.loads(STATE_FILE.read_text())
    except Exception:
        pass
    return {}

def save_saved_state():
    try:
        payload = {
            "resume_name": st.session_state.get("resume_name"),
            "resume_text": st.session_state.get("resume_text"),
            "profile": st.session_state.get("profile"),
        }
        STATE_FILE.write_text(json.dumps(payload))
    except Exception:
        pass

saved = load_saved_state()

for key, default in {
    "profile": saved.get("profile"),
    "resume_name": saved.get("resume_name"),
    "resume_text": saved.get("resume_text"),
    "jobs": [],
    "search_complete": False,
    "ai_results": {},
    "target_roles": [],
}.items():
    if key not in st.session_state or (st.session_state[key] is None and saved.get(key) is not None):
        st.session_state[key] = default

st.title("💼 AI Job Agent")
if st.session_state.profile:
    st.success(f"Resume loaded ✓  {st.session_state.resume_name or 'Saved resume'}")
st.caption("Live jobs → qualification screening → AI requirement analysis")

with st.sidebar:
    st.header("Job criteria")
    st.caption("Target roles determine the relevance component of the score. Minimum match score is the only display threshold.")
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
    max_results = st.slider("Maximum jobs to analyze", 5, 40, 15)
    use_ai = st.checkbox("AI qualification analysis", value=True)
    ai_top_n = st.slider("AI-analyze top jobs", 1, 5, 3)
    st.caption("AI analysis uses your OpenAI API key from Streamlit Secrets.")

    st.subheader("Job sources")
    use_adzuna = st.checkbox("Adzuna", value=True)
    use_himalayas = st.checkbox("Himalayas", value=True)
    use_greenhouse = st.checkbox("Greenhouse public boards", value=True)
    use_lever = st.checkbox("Lever public boards", value=True)
    use_ashby = st.checkbox("Ashby public boards", value=True)
    with st.expander("Public ATS board lists"):
        greenhouse_boards = st.text_area("Greenhouse board tokens (one per line)", "")
        lever_boards = st.text_area("Lever accounts (one per line)", "")
        ashby_boards = st.text_area("Ashby job boards (one per line)", "")

st.subheader("1. Resume")

uploaded = st.file_uploader(
    "Upload your resume PDF",
    type=["pdf"],
    key="resume_uploader"
)

if uploaded is not None:
    try:
        reader = PdfReader(uploaded)
        extracted = "\n".join((p.extract_text() or "") for p in reader.pages)
        if extracted.strip():
            st.session_state.resume_text = extracted
            st.session_state.resume_name = uploaded.name
            st.session_state.profile = normalize_profile(extracted)
            save_saved_state()
            st.success(f"Resume loaded and profile built ✓  {uploaded.name}")
    except Exception as e:
        st.error(f"Could not read the PDF: {e}")

if st.session_state.profile:
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Rebuild profile from saved resume"):
            st.session_state.profile = normalize_profile(st.session_state.resume_text or "")
            save_saved_state()
            st.success("Candidate profile rebuilt.")
    with col2:
        if st.button("Clear saved resume"):
            for k in ["profile", "resume_name", "resume_text", "jobs", "ai_results"]:
                st.session_state[k] = None if k in ["profile", "resume_name", "resume_text"] else {}
            try:
                STATE_FILE.unlink(missing_ok=True)
            except Exception:
                pass
            st.rerun()

    with st.expander("Candidate profile", expanded=False):
        st.json(st.session_state.profile)
else:
    st.info("Upload your resume. The app will save the extracted profile during this session.")

st.subheader("2. Live job search")
with st.expander("📡 Source status", expanded=False):
    st.write("Connected: Adzuna · Himalayas")
    st.write("Public ATS adapters: Greenhouse · Lever · Ashby")
    st.caption("LinkedIn, Indeed, and ZipRecruiter are not scraped or bypassed; authorized API/partner access can be added later.")

if "Chicago" in location:
    with st.expander("Chicago / Adzuna connection", expanded=False):
        if st.button("Test Chicago job connection"):
            result = test_adzuna()
            if result["ok"]:
                st.success(result["message"])
            else:
                st.error(result["message"])
                if result.get("details"):
                    st.code(result["details"])

if not st.session_state.profile:
    st.info("Build your candidate profile before searching.")
else:
    if st.button("🔎 Find live jobs", type="primary"):
        role_queries = [x.strip() for x in roles_text.splitlines() if x.strip()]
        st.session_state.target_roles = role_queries
        jobs = []
        errors = []

        if use_himalayas and "Remote" in work_style:
            for q in role_queries[:4]:
                try: jobs.extend(search_himalayas(q, country="US", limit=max_results))
                except Exception as e: errors.append(f"Remote / Himalayas ({q}): {e}")

        if use_adzuna and "Chicago" in location:
            for q in role_queries[:4]:
                try: jobs.extend(search_adzuna(query=q, where="Chicago", salary_min=min_salary, limit=max_results))
                except Exception as e: errors.append(f"Chicago / Adzuna ({q}): {e}")

        if use_greenhouse and greenhouse_boards.strip():
            jobs.extend(search_greenhouse(parse_slugs(greenhouse_boards), role_queries, location, max_results*2))
        if use_lever and lever_boards.strip():
            jobs.extend(search_lever(parse_slugs(lever_boards), role_queries, location, max_results*2))
        if use_ashby and ashby_boards.strip():
            jobs.extend(search_ashby(parse_slugs(ashby_boards), role_queries, location, max_results*2))

        for err in errors:
            st.error(err)

        unique = {}
        for j in jobs:
            key = j.get("id") or j.get("url") or (j.get("title"), j.get("company"))
            unique[key] = j
        jobs = list(unique.values())
        if jobs:
            counts={}
            for j in jobs:
                s=j.get("source","Unknown"); counts[s]=counts.get(s,0)+1
            st.caption("Listings by source: "+" · ".join(f"{k}: {v}" for k,v in sorted(counts.items())))

        scored = []
        for job in jobs:
            if job.get("salary_min") and job["salary_min"] < min_salary:
                continue
            scored.append((score_job(st.session_state.profile, job, role_queries), job))

        scored.sort(
            key=lambda x: (
                x[0]["status"] == "QUALIFIED",
                x[0]["status"] == "REVIEW",
                x[0]["score"]
            ),
            reverse=True
        )

        # Never show a clearly wrong occupational family just because its
        # generic skills overlap with the resume.
        # The Minimum match score is the single score threshold.
        # Target roles affect the score itself; there is no hidden second cutoff.
        displayed = [
            x for x in scored
            if x[0]["score"] >= min_score
        ][:max_results]
        st.session_state.jobs = [j for _, j in displayed]
        st.session_state.search_complete = True

        # AI runs as part of the search action, so there is no second button
        # that can reset the resume uploader state.
        if use_ai and displayed:
            st.info(f"Running AI qualification analysis on the top {min(ai_top_n, len(displayed))} matches…")
            st.session_state.ai_results = {}
            for i, (result, job) in enumerate(displayed[:ai_top_n]):
                try:
                    ai_result = ai_screen_job(
                        st.session_state.resume_text or "",
                        job
                    )
                    st.session_state.ai_results[job.get("id") or str(i)] = ai_result
                except Exception as e:
                    st.session_state.ai_results[job.get("id") or str(i)] = {
                        "recommendation": "REVIEW",
                        "summary": f"AI analysis failed safely: {e}",
                        "hard_failures": [],
                        "requirements": []
                    }

        st.success(
            f"Analyzed {len(scored)} live listings; showing {len(displayed)} genuinely relevant jobs above your threshold."
        )

    # Results persist across reruns because they are in session state.
    if st.session_state.get("search_complete"):
        displayed = []
        for job in st.session_state.jobs:
            displayed.append((score_job(st.session_state.profile, job, st.session_state.target_roles), job))

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

                status = result["status"]
                score = result["score"]
                if score >= 90:
                    band = "Excellent match"
                elif score >= 80:
                    band = "Strong match"
                elif score >= 70:
                    band = "Good match"
                elif score >= 60:
                    band = "Possible match"
                else:
                    band = "Weak match"

                st.caption(f"Match band: **{band}**")

                if status == "QUALIFIED":
                    st.success("QUALIFIED — worth applying")
                elif status == "REVIEW":
                    st.warning("REVIEW — relevant, but qualification is not fully verified")
                else:
                    st.error("DO NOT APPLY — score meets your threshold, but a qualification/relevance issue was detected")

                description = clean_html(job.get("description", ""))
                if description:
                    with st.expander("Job description"):
                        st.write(description)

                st.markdown("**Initial screening**")
                for reason in result["reasons"]:
                    st.write("• " + reason)

                with st.expander("🎯 Requirement-by-requirement analysis"):
                    matrix = requirement_matrix(st.session_state.profile, job)
                    if matrix:
                        for req in matrix:
                            s = req["status"]
                            line = f"{req['requirement']}\n\n{req['evidence']}"
                            if s == "MEETS":
                                st.success("✅ **MEETS** — " + line)
                            elif s == "PARTIAL":
                                st.warning("🟡 **PARTIAL** — " + line)
                            elif s == "MISSING":
                                st.error("❌ **NOT DEMONSTRATED** — " + line)
                            else:
                                st.info("❓ **CANNOT VERIFY** — " + line)

                key = job.get("id") or str(idx)
                ai_result = st.session_state.ai_results.get(key)
                if ai_result:
                    with st.expander("🤖 AI qualification analysis", expanded=True):
                        rec = ai_result.get("recommendation", "REVIEW")
                        if rec == "APPLY":
                            st.success("🤖 AI RECOMMENDATION: APPLY")
                        elif rec == "REVIEW":
                            st.warning("🤖 AI RECOMMENDATION: REVIEW")
                        else:
                            st.error("🤖 AI RECOMMENDATION: DO NOT APPLY")

                        st.write(ai_result.get("summary", ""))

                        for item in ai_result.get("hard_failures", []):
                            st.error("Hard issue: " + item)

                        for item in ai_result.get("requirements", []):
                            s = item.get("status", "CANNOT_VERIFY")
                            icon = {"MEETS":"✅", "PARTIAL":"🟡", "MISSING":"❌", "CANNOT_VERIFY":"❓"}.get(s, "❓")
                            importance = item.get("importance", "UNCLEAR")
                            st.write(f"{icon} **{s} · {importance}** — {item.get('requirement','')}")
                            if item.get("evidence"):
                                st.caption(item["evidence"])

                if job.get("salary"):
                    st.write(f"**Salary:** {job['salary']}")
                if job.get("url"):
                    st.link_button("View / Apply", job["url"])

st.divider()
st.caption("Applications are not submitted automatically.")
