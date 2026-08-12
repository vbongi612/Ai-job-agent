# AI Job Agent — Live Jobs MVP

This version replaces the sample jobs with live job feeds.

## Included

- Resume PDF upload
- Candidate profile extraction
- Qualification-first scoring
- Live remote job search via Himalayas (no API key)
- Optional Chicago/US job search via Adzuna
- Salary filtering
- Match-score filtering
- Direct application links

Himalayas is a public JSON API for remote jobs and requires no authentication.
Adzuna requires an `app_id` and `app_key`.

## Streamlit Secrets

To enable Chicago/US search, add:

```toml
ADZUNA_APP_ID = "your_app_id"
ADZUNA_APP_KEY = "your_app_key"
```

in Streamlit App Settings → Secrets.

Do not commit API keys to GitHub.

## Next phase

- Better requirement extraction with an LLM
- Persistent database
- Job history / deduplication
- Tailored resume generation
- Cover letters
- Application-question generation
- Human-approved browser autofill
- Application tracker
