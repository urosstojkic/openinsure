# Backend Agent — History

## Learnings

- SQL repos need `_to_sql_row()` / `_from_sql_row()` with `_str()` helper using `isoformat()` for datetime objects
- UUID FK columns (applicant_id, insured_id) must be NULL — store names in JSON metadata
- Event publishing must be wrapped in try/catch — Event Grid format errors crash requests otherwise
- SubmissionResponse fields need defaults for SQL compatibility (NULL values)
- Status enums must match SQL CHECK constraints: received/triaging/underwriting/quoted/bound/declined/expired
- Policies SQL query needs LEFT JOIN parties to get policyholder_name
- Claims need total_incurred computed as total_reserved + total_paid
