# AI Job Agent v6

Chicago search fix:
- Searches each target role separately instead of using one OR query.
- Uses Adzuna's documented keyword + location search pattern.
- Retries without optional full-time/permanent filters if a restrictive query returns no results.
- Keeps salary filtering and requirement screening.

Adzuna credentials remain in Streamlit Secrets only.
