
import os
import requests

HIMALAYAS_URL = "https://himalayas.app/jobs/api/search"
ADZUNA_URL = "https://api.adzuna.com/v1/api/jobs/us/search/1"

def _himalayas_job(x):
    return {
        "id": f"himalayas:{x.get('guid')}",
        "title": x.get("title", "Untitled"),
        "company": x.get("companyName", "Unknown company"),
        "location": ", ".join(x.get("locationRestrictions") or []) or "Remote",
        "employment_type": x.get("employmentType", "Not specified"),
        "salary_min": x.get("minSalary"),
        "salary_max": x.get("maxSalary"),
        "salary": (
            f"{x.get('currency', '')} {x.get('minSalary')}–{x.get('maxSalary')} "
            f"per {x.get('salaryPeriod', 'year')}"
            if x.get("minSalary") or x.get("maxSalary") else None
        ),
        "description": x.get("description") or x.get("excerpt") or "",
        "url": x.get("applicationLink"),
        "source": "Himalayas",
        "role_terms": [x.get("title", "")] + (x.get("category") or []) + (x.get("parentCategories") or []),
        "skill_terms": x.get("category") or [],
        "required": [],
    }

def search_himalayas(query, country="US", limit=20):
    params = {"q": query, "country": country, "sort": "relevant", "page": 1}
    r = requests.get(HIMALAYAS_URL, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()
    raw = data.get("jobs", data.get("results", data if isinstance(data, list) else []))
    return [_himalayas_job(x) for x in raw[:limit]]

def search_adzuna(query, where="Chicago", salary_min=0, limit=20):
    app_id = os.getenv("ADZUNA_APP_ID")
    app_key = os.getenv("ADZUNA_APP_KEY")

    try:
        import streamlit as st
        app_id = app_id or st.secrets.get("ADZUNA_APP_ID")
        app_key = app_key or st.secrets.get("ADZUNA_APP_KEY")
    except Exception:
        pass

    if not app_id or not app_key:
        raise RuntimeError(
            "Chicago live search needs Adzuna credentials. "
            "Remote search does not require this key."
        )

    params = {
        "app_id": app_id,
        "app_key": app_key,
        "results_per_page": min(limit, 20),
        "what": query,
        "where": where,
        "salary_min": salary_min,
        "full_time": 1,
        "permanent": 1,
        "content-type": "application/json",
        "sort_by": "date",
    }

    r = requests.get(ADZUNA_URL, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()

    jobs = []
    for x in data.get("results", []):
        loc = (x.get("location") or {}).get("display_name") or where
        company = (x.get("company") or {}).get("display_name") or "Unknown company"

        jobs.append({
            "id": f"adzuna:{x.get('id')}",
            "title": x.get("title", "Untitled"),
            "company": company,
            "location": loc,
            "employment_type": x.get("contract_time") or "Full-time",
            "salary_min": x.get("salary_min"),
            "salary_max": x.get("salary_max"),
            "salary": (
                f"${x.get('salary_min', '')}–${x.get('salary_max', '')}"
                if x.get("salary_min") or x.get("salary_max") else None
            ),
            "description": x.get("description", ""),
            "url": x.get("redirect_url"),
            "source": "Adzuna",
            "role_terms": [x.get("title", ""), (x.get("category") or {}).get("label", "")],
            "skill_terms": [],
            "required": [],
        })
    return jobs
