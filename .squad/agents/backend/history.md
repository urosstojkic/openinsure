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

## Product JSON → Relational Migration (2026-03-30, #164)

- **Dual-write pattern**: `SqlProductRepository.create()`/`.update()` calls `ProductRelationsRepository.sync_from_product()` to keep JSON + relational in sync
- **Consumer fallback**: all consumers (rating, triage, knowledge sync, API) prefer relational data and fall back to JSON blob when relational rows don't exist
- **RatingEngine class**: product-aware wrapper around CyberRatingEngine; loads industry/revenue_band factors from `rating_factor_tables` SQL table, caches per product_id
- **Appetite check**: `ProductRelationsRepository.check_appetite()` evaluates relational rules with typed operators (>=, <=, between, in, not_in, eq, neq)
- **Knowledge sync enrichment**: `_product_to_knowledge_document()` now accepts optional relational data params, producing richer knowledge docs from typed columns
- **List endpoint stays lightweight**: GET /products does NOT load relations per product (N+1 avoidance)
- **JSON columns marked DEPRECATED** but NOT dropped — migration period allows rollback

## Escalation Thresholds & Authority Matrix (2026-03-22)

### Authority limits (from `rbac/authority.py` DEFAULT_AUTHORITY_CONFIG)

| Action     | Auto-execute | Sr UW / Adjuster | LOB Head / CCO | CUO      |
|------------|-------------|-------------------|----------------|----------|
| Quote      | ≤$50K       | ≤$250K            | ≤$1M           | >$1M     |
| Bind       | ≤$25K       | ≤$100K            | ≤$500K         | >$500K   |
| Settlement | —           | Adjuster ≤$25K    | CCO ≤$250K     | ≤$1M     |
| Reserve    | ≤$25K       | Adjuster ≤$100K   | —              | —        |

### Key findings

- `dev-key-change-me` API key maps to **CUO** role (`rbac/auth.py` line 119) — CUO never triggers ESCALATE, only REQUIRE_APPROVAL
- ESCALATE decision only fires when user role is **below** the required role in the hierarchy
- **FIXED**: Dev mode now reads `X-User-Role` header to map portal personas to RBAC roles (`auth.py` role_mapping dict)
- Frontend Axios client now sends `X-User-Role` header from `localStorage('openinsure_role')` on every request
- Portal UserRole keys (AuthContext.tsx) map to backend Role enum: ceo→CEO, cuo→CUO, senior_uw→SENIOR_UNDERWRITER, uw_analyst→UW_ANALYST, claims_manager→CLAIMS_MANAGER, adjuster→CLAIMS_ADJUSTER, cfo→CFO, compliance→COMPLIANCE_OFFICER, product_mgr→PRODUCT_MANAGER, operations→OPERATIONS, broker→BROKER
- Without the header, dev mode still defaults to CUO (backward compatible)
- To trigger real escalations: select a low-authority persona (e.g. "Sarah Chen — Underwriter" → uw_analyst) in the portal
- Added `POST /escalations` admin endpoint for manual escalation creation when natural flow cannot trigger them
- UW hierarchy: UW_ANALYST → SENIOR_UNDERWRITER → LOB_HEAD → CUO → CEO
- Claims hierarchy: CLAIMS_ADJUSTER → CLAIMS_MANAGER → CUO → CEO
- Bind endpoint has a bug: `Logger._log() got an unexpected keyword argument 'submission_id'` — needs investigation

## Renewal Flow (2026-03-22)

- `POST /renewals/{policy_id}/generate` calls Foundry `openinsure-underwriting` agent for renewal terms
- Returns: `renewal_premium`, `rate_change_pct`, `conditions[]`, `recommendation`, `confidence`, `source`
- Foundry returns realistic +5% rate changes with security conditions (pen test, MFA, backups)
- `POST /renewals/{policy_id}/process` does full workflow: AI assessment → create renewal policy → compliance audit → publish `policy.renewed` event
- `GET /renewals/upcoming?days=N` returns policies approaching renewal with urgency breakdowns (30/60/90 days)
- Frontend: `Policies.tsx` "Renew" button calls `generateRenewalTerms()`, `RenewalsPage.tsx` "Process Renewal" button calls `processRenewal()`
- Renewal records stored in-memory (no SQL repo yet — see Enterprise Audit)

## Document & Channel Integration (2026-03-22)

- `POST /documents/upload` — file upload with auto-classification and OCR extraction (50 MB limit)
- `POST /submissions/acord-ingest` — ACORD 125/126 XML parsing to submission (uses `acord_parser.py`)
- Document Intelligence uses `prebuilt-document` model with regex fallback when Azure DI unavailable
- Blob storage adapter supports chunked upload (>4 MiB), SAS URL generation (1h expiry)
- `SubmissionChannel.EMAIL` enum exists but no email ingestion code is built
- Service Bus consumer (`EventBusAdapter.subscribe`) is ready for inbound event processing
- Created `docs/guides/document-channels.md` — covers upload, ACORD, OCR, and email roadmap

## Enterprise Audit Findings (2026-03-19)

- CRITICAL: UW Workbench calls `/underwriter/queue` — endpoint NOT IMPLEMENTED (mock only)
- CRITICAL: Claims Workbench calls `/claims/queue` — endpoint NOT IMPLEMENTED (mock only)
- CRITICAL: Executive Dashboard calls `/dashboard/executive` — endpoint NOT IMPLEMENTED (mock only)
- CRITICAL: Broker Portal calls `/broker/*` — endpoints NOT IMPLEMENTED
- CRITICAL: Reinsurance, Actuarial, Finance, MGA, Renewals — ALL in-memory only, no SQL repos
- Need: SqlReinsuranceRepository, SqlActuarialRepository, SqlFinanceRepository, SqlMGARepository
- Need: SQL migration to add tables for these modules
- Submission CREATE was always setting status to "received" — fixed to accept status from request body
