
import os
import requests

HIMALAYAS_URL = "https://himalayas.app/jobs/api/search"
ADZUNA_BASE = "https://api.adzuna.com/v1/api/jobs/us/search/1"

def _secret(name):
    value = os.getenv(name)
    try:
        import streamlit as st
        if not value and name in st.secrets:
            value = st.secrets[name]
    except Exception:
        pass
    return str(value).strip() if value is not None else ""

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
            f"{x.get('currency', '')} {x.get('minSalary')}–{x.get('maxSalary')} per {x.get('salaryPeriod', 'year')}"
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
    r = requests.get(
        HIMALAYAS_URL,
        params={"q": query, "country": country, "sort": "relevant", "page": 1},
        timeout=20
    )
    r.raise_for_status()
    data = r.json()
    raw = data.get("jobs", data.get("results", data if isinstance(data, list) else []))
    return [_himalayas_job(x) for x in raw[:limit]]

def _adzuna_credentials():
    return _secret("ADZUNA_APP_ID"), _secret("ADZUNA_APP_KEY")

def test_adzuna():
    app_id, app_key = _adzuna_credentials()

    if not app_id or not app_key:
        return {
            "ok": False,
            "message": "Streamlit is not seeing one or both Adzuna secrets.",
            "details": "Expected root-level secrets named ADZUNA_APP_ID and ADZUNA_APP_KEY."
        }

    # Use the simplest possible endpoint to isolate credentials from search filters.
    url = "https://api.adzuna.com/v1/api/version"
    try:
        r = requests.get(
            url,
            params={"app_id": app_id, "app_key": app_key, "content-type": "application/json"},
            timeout=20
        )
    except Exception as e:
        return {"ok": False, "message": "Could not reach Adzuna.", "details": repr(e)}

    if r.ok:
        return {"ok": True, "message": "Adzuna credentials are valid and the API is reachable."}

    return {
        "ok": False,
        "message": f"Adzuna rejected the credentials/request (HTTP {r.status_code}).",
        "details": r.text[:1500]
    }


def search_adzuna(query, where="Chicago", salary_min=0, limit=20):
    app_id, app_key = _adzuna_credentials()

    if not app_id or not app_key:
        raise RuntimeError(
            "Streamlit is not seeing ADZUNA_APP_ID and/or ADZUNA_APP_KEY. "
            "Add them as root-level Streamlit Secrets."
        )

    base = {
        "app_id": app_id,
        "app_key": app_key,
        "results_per_page": min(limit, 20),
        "what": query,
        "where": where,
        "content-type": "application/json",
        "sort_by": "date",
    }

    # Start with the user's salary floor. If that produces nothing, retry
    # without optional employment filters; this prevents a valid search from
    # becoming empty simply because Adzuna lacks salary/type metadata.
    attempts = [
        {**base, "salary_min": salary_min, "full_time": 1, "permanent": 1},
        {**base, "salary_min": salary_min},
        {**base},
    ]

    last_error = None
    data = None

    for params in attempts:
        try:
            r = requests.get(ADZUNA_BASE, params=params, timeout=20)
        except Exception as e:
            last_error = f"Could not reach Adzuna: {e}"
            continue

        if r.ok:
            data = r.json()
            if data.get("results"):
                break
        else:
            last_error = f"Adzuna HTTP {r.status_code}: {r.text[:1000]}"

    if data is None:
        raise RuntimeError(last_error or "Adzuna returned no response.")

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
            "role_terms": [
                x.get("title", ""),
                (x.get("category") or {}).get("label", "")
            ],
            "skill_terms": [],
            "required": [],
        })
    return jobs


def _norm_public_job(source, raw, title, company, location, description, url,
                     salary_min=None, salary_max=None, employment_type=None):
    return {
        "id": f"{source}:{raw}",
        "title": title or "Untitled",
        "company": company or "Unknown company",
        "location": location or "Not specified",
        "employment_type": employment_type or "Not specified",
        "salary_min": salary_min,
        "salary_max": salary_max,
        "salary": (f"${salary_min:,.0f}–${salary_max:,.0f}"
                   if isinstance(salary_min,(int,float)) or isinstance(salary_max,(int,float)) else None),
        "description": description or "",
        "url": url,
        "source": source,
        "role_terms": [title or ""],
        "skill_terms": [],
        "required": [],
    }

def _public_job_matches(job, queries, location=""):
    hay = f"{job.get('title','')} {job.get('description','')}".lower()
    role_ok = not queries or any(q.lower() in hay for q in queries)
    wanted_city = (location or "").lower().split(",")[0].strip()
    loc = (job.get("location") or "").lower()
    return role_ok and (not wanted_city or wanted_city in loc or "remote" in loc)

def search_greenhouse(board_tokens, queries, location="", limit=50):
    out=[]
    for token in board_tokens:
        try:
            r=requests.get(f"https://boards-api.greenhouse.io/v1/boards/{token.strip()}/jobs",
                           params={"content":"true"},timeout=20); r.raise_for_status()
            for x in r.json().get("jobs",[]):
                loc=x.get("location",{}); loc=loc.get("name","") if isinstance(loc,dict) else loc
                j=_norm_public_job("Greenhouse",x.get("id"),x.get("title"),token,loc,x.get("content",""),x.get("absolute_url"))
                if _public_job_matches(j,queries,location): out.append(j)
                if len(out)>=limit:return out
        except Exception: continue
    return out

def search_lever(accounts, queries, location="", limit=50):
    out=[]
    for account in accounts:
        try:
            r=requests.get(f"https://api.lever.co/v0/postings/{account.strip()}",
                           params={"mode":"json"},timeout=20); r.raise_for_status()
            for x in r.json():
                c=x.get("categories") or {}
                j=_norm_public_job("Lever",x.get("id"),x.get("text"),account,c.get("location",""),
                                   x.get("descriptionPlain") or x.get("description",""),
                                   x.get("hostedUrl") or x.get("applyUrl"))
                if _public_job_matches(j,queries,location): out.append(j)
                if len(out)>=limit:return out
        except Exception: continue
    return out

def search_ashby(board_names, queries, location="", limit=50):
    out=[]
    for board in board_names:
        try:
            r=requests.get(f"https://api.ashbyhq.com/posting-api/job-board/{board.strip()}",
                           params={"includeCompensation":"true"},timeout=20); r.raise_for_status()
            for x in r.json().get("jobs",[]):
                locs=[x.get("location","")]+[z.get("location","") for z in (x.get("secondaryLocations") or [])]
                j=_norm_public_job("Ashby",x.get("jobUrl") or x.get("title"),x.get("title"),board,
                                   ", ".join(z for z in locs if z),
                                   x.get("descriptionPlain") or x.get("descriptionHtml",""),
                                   x.get("jobUrl") or x.get("applyUrl"))
                if _public_job_matches(j,queries,location): out.append(j)
                if len(out)>=limit:return out
        except Exception: continue
    return out

def parse_slugs(text):
    return [x.strip() for x in re.split(r"[\n,]+",text or "") if x.strip()]
