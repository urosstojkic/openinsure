# Frontend Agent — History

## Learnings

- Dashboard API paths must be `/api/v1/...` (not `/api/...`) to match backend router
- Mock fallback is REQUIRED — removing it causes blank dashboards when backend is down
- SQL datetime objects render as "Invalid Date" in JS — backend must return ISO 8601 strings
- Policies need policyholder_name from backend (LEFT JOIN in SQL)
- Claims total_incurred must be a number, not null (causes $NaN display)
