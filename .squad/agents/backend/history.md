# Backend Agent — History

## Learnings

- SQL repos need `_to_sql_row()` / `_from_sql_row()` with `_str()` helper using `isoformat()` for datetime objects
- UUID FK columns (applicant_id, insured_id) must be NULL — store names in JSON metadata
- Event publishing must be wrapped in try/catch — Event Grid format errors crash requests otherwise
- SubmissionResponse fields need defaults for SQL compatibility (NULL values)
- Status enums must match SQL CHECK constraints: received/triaging/underwriting/quoted/bound/declined/expired
- Policies SQL query needs LEFT JOIN parties to get policyholder_name
- Claims need total_incurred computed as total_reserved + total_paid
- WorkflowEngine delegates multi-agent orchestration through Foundry agents
- EscalationService holds items exceeding authority for human approval (returns 202 Accepted)

## Enterprise Audit Findings (2026-03-19)

- CRITICAL: UW Workbench calls `/underwriter/queue` — endpoint NOT IMPLEMENTED (mock only)
- CRITICAL: Claims Workbench calls `/claims/queue` — endpoint NOT IMPLEMENTED (mock only)
- CRITICAL: Executive Dashboard calls `/dashboard/executive` — endpoint NOT IMPLEMENTED (mock only)
- CRITICAL: Broker Portal calls `/broker/*` — endpoints NOT IMPLEMENTED
- CRITICAL: Reinsurance, Actuarial, Finance, MGA, Renewals — ALL in-memory only, no SQL repos
- Need: SqlReinsuranceRepository, SqlActuarialRepository, SqlFinanceRepository, SqlMGARepository
- Need: SQL migration to add tables for these modules
- Submission CREATE was always setting status to "received" — fixed to accept status from request body
