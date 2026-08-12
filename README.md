# AI Job Agent — MVP

This local prototype:
1. Accepts a resume PDF.
2. Extracts a structured candidate profile.
3. Lets you define target roles, location, salary, and minimum match score.
4. Scores jobs using qualification-first matching.
5. Flags hard requirement failures.
6. Provides an OpenAI-powered evaluator when `OPENAI_API_KEY` is configured.

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

The MVP uses representative jobs in `sample_jobs.json`. Replace that fixture with permitted live job feeds in the next phase.

The prototype does not auto-submit applications. The safe next phases are live job ingestion, application-question generation, human approval, browser autofill, and controlled submission where automation is permitted.
