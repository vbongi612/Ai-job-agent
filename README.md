# AI Job Agent v7

Adds the real AI qualification layer on top of the working v6 Chicago/Adzuna search.

The AI:
- compares the complete resume with the complete job posting;
- separates required vs preferred qualifications where possible;
- uses MEETS / PARTIAL / MISSING / CANNOT_VERIFY;
- flags hard failures;
- returns APPLY / REVIEW / DO_NOT_APPLY conservatively.

Streamlit Secrets:
OPENAI_API_KEY = "..."
OPENAI_MODEL = "gpt-5.6"  # optional

Never put API keys in GitHub.
