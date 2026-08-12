# AI Job Agent v8

Fixes Streamlit rerun/state behavior:
- Extracted resume text is persisted in session state.
- Candidate profile persists after AI buttons and other interactions.
- The UI shows Resume loaded ✓ after the initial upload.
- AI screening reads the persisted resume text instead of relying on the uploader.
- Job results are retained in session state.

Keep OPENAI_API_KEY and Adzuna secrets in Streamlit Secrets, never GitHub.
