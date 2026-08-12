import streamlit as st
from pypdf import PdfReader

from matcher import normalize_profile, score_job
from jobs_api import search_himalayas, search_adzuna

st.set_page_config(page_title="AI Job Agent", page_icon="💼", layout="wide")
st.title("💼 AI Job Agent")
st.caption("Live jobs → qualification-first matching → ranked applications")

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
    max_results = st.slider("Maximum jobs to analyze", 10, 40, 20)

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

        # Remote: Himalayas is a public, no-key API.
        if "Remote" in work_style:
            for q in role_queries[:4]:
                try:
                    jobs.extend(search_himalayas(q, country="US", limit=max_results))
                except Exception as e:
                    st.warning(f"Remote feed error for '{q}': {e}")

        # Chicago / broader US: optional Adzuna integration.
        # Add ADZUNA_APP_ID and ADZUNA_APP_KEY to Streamlit Secrets to enable it.
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

        # Deduplicate.
        unique = {}
        for j in jobs:
            key = j.get("id") or j.get("url") or (j.get("title"), j.get("company"))
            unique[key] = j
        jobs = list(unique.values())

        if not jobs:
            st.warning(
                "No live jobs were returned. Remote search uses Himalayas automatically. "
                "For Chicago jobs, add Adzuna credentials in Streamlit Secrets."
            )
        else:
            scored = []
            for job in jobs:
                result = score_job(st.session_state.profile, job)
                if job.get("salary_min") and job["salary_min"] < min_salary:
                    continue
                scored.append((result, job))

            scored.sort(key=lambda x: (x[0]["qualified"], x[0]["score"]), reverse=True)
            displayed = [x for x in scored if x[0]["score"] >= min_score][:max_results]

            st.success(f"Analyzed {len(scored)} live listings; showing {len(displayed)} above your threshold.")

            for result, job in displayed:
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

                    if result["qualified"]:
                        st.success("QUALIFIED — worth reviewing")
                    else:
                        st.error("DO NOT APPLY")

                    st.write(job.get("description", "")[:1800])

                    st.markdown("**Why this score?**")
                    for reason in result["reasons"]:
                        st.write("• " + reason)

                    if job.get("salary"):
                        st.write(f"**Salary:** {job['salary']}")

                    if job.get("url"):
                        st.link_button("View / Apply", job["url"])

st.divider()
st.caption(
    "Live remote listings are supplied by Himalayas. Chicago listings can be supplied by Adzuna. "
    "This app does not submit applications automatically."
)
