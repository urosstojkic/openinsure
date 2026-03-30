# Changelog

All notable changes to OpenInsure will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## v110 — Policy Transactions, Polymorphic Documents, Work Items (2026-04-01)

### Summary
Three data model features: transaction-based policy history for time-travel queries (#173),
unified polymorphic documents table replacing per-entity document tables (#175), and
structured work items with SLA tracking and inbox-style queues (#176).
3 new migrations, 2 new services, 1 new API module, 34 new tests.

### Database — New Tables (Migrations 020–022)
- **`policy_transactions`** — Every policy mutation (bind, endorse, renew, cancel, reinstate) creates an immutable transaction record with coverage/terms snapshots. Enables "what was in effect on date X?" queries (migration 020, #173)
- **`documents`** — Polymorphic document tracking for any entity (submission, policy, claim, endorsement). Replaces per-entity document tables. Includes soft-delete, classification confidence, extracted data (migration 021, #175)
- **`work_items`** — Structured task tracking with assignee, priority (low/medium/high/urgent), status (open/in_progress/completed/cancelled/escalated), due date, SLA hours, completion tracking (migration 022, #176)

### Database — Data Migration
- Existing `submission_documents` rows migrated into `documents` table with `entity_type='submission'` (old table retained for backward compatibility) (#175)

### New Capabilities
- **Transaction-based policy history** — `policy_transaction_service.py` records every lifecycle operation. `PolicyLifecycleService.bind_policy()` → `new_business`, `endorse_policy()` → `endorsement` (with coverage snapshot), `renew_policy()` → `renewal`, `cancel_policy()` → `cancellation` (#173)
- **Polymorphic document CRUD** — `POST/GET/PUT/DELETE /api/v1/documents/records` with filtering by entity_type, entity_id, document_type. Soft-delete support. Extends existing blob-storage document endpoints (#175)
- **Work item service** — `create_work_item()`, `complete_work_item()`, `get_inbox()` with SLA auto-calculation from `sla_hours`. Inbox returns open/in_progress items for a user (#176)
- **Work items API** — `GET /api/v1/work-items?assigned_to=X`, `POST /api/v1/work-items`, `POST /api/v1/work-items/{id}/complete` (#176)
- **Escalation → work item integration** — When an escalation is created, a corresponding `escalation_review` work item is auto-created with high priority and 24h SLA (#176)
- **Policy transactions endpoint** — `GET /api/v1/policies/{id}/transactions` returns chronological transaction history (#173)

### Metrics
- 34 new tests (policy transactions: 11, work items: 16, documents: 7)
- 896 unit tests pass (up from 862)
- 45 database tables across 21 migrations (up from 42/18)
- 182 API endpoints across 32 modules (up from 172/31)

### Agents
- Backend (#173, #175, #176)

---

## v109 — Data-Driven Workflow Templates & DDD Aggregate Boundaries (2026-04-01)

### Summary
Two DDD/innovation features: data-driven workflow templates configurable per product (#180) and
proper aggregate boundaries with domain event-driven cross-aggregate communication (#170).
1 new migration, 3 new aggregate roots, 1 workflow registry service, 3 bind event handlers,
57 new tests.

### Database — New Tables
- **`workflow_templates`** — Configurable workflow definitions per product with type, version, and status (migration 025, #180)
- **`workflow_steps`** — Ordered steps within a template: agent assignment, dependencies, timeouts, conditions, optional flags (migration 025, #180)

### Database — Seed Data
- Default **new_business** workflow (5 steps: orchestration → enrichment → intake → underwriting → compliance)
- Default **claims** workflow (3 steps: orchestration → assessment → compliance)
- Default **renewal** workflow (4 steps: orchestration → assessment → policy_review → compliance)

### New Capabilities
- **Data-driven workflow templates** — `WorkflowRegistry.get_workflow_for_product(product_id, workflow_type)` loads workflow steps from DB per product, falling back to defaults. Products can now have custom workflow steps without code changes (#180)
- **DDD aggregate roots** — `SubmissionAggregate`, `PolicyAggregate`, `ClaimAggregate` in `domain/aggregates/`: each owns its state transitions (validates before mutating), emits domain events, never directly modifies another aggregate (#170)
- **SubmissionBound event** — New domain event emitted when a submission is bound, replacing direct cross-aggregate writes (#170)
- **Bind event handlers** — `PolicyCreationHandler`, `BillingHandler`, `ReinsuranceHandler` each listen for `SubmissionBound` and operate on their own aggregate boundary (#170)
- **Workflow engine registry integration** — `execute_workflow()` accepts `product_id` parameter to load product-specific workflow templates from the registry (#180)

### Refactoring
- `SubmissionService.bind()` refactored to use `SubmissionAggregate` for state validation and `dispatch_bind_events()` for cross-aggregate side-effects (#170)
- Bind flow now follows DDD: aggregate validates → emits event → handlers create policy/billing/cessions in response (#170)

### Metrics
- 57 new tests (aggregates: 27, workflow registry: 20, bind handlers: 10)
- 862 unit tests pass (up from 805)
- 42 database tables across 18 migrations (up from 40/15)

### Agents
- Backend (#170, #180)

---

## v108 — Multi-Currency, Product Inheritance, Rating Factor Versioning (2026-04-01)

### Summary
Three medium-priority innovations: multi-currency foundation across all monetary tables (#174),
product template inheritance for LOB specialization (#177), and rating factor version history
for regulatory audit (#181). 2 new migrations (023–024), 1 new table, currency columns on 12
existing tables, inheritance columns on products.

### Database — New Tables
- **`exchange_rates`** — Currency conversion reference table with `from_currency`, `to_currency`, `rate`, `effective_date`; seeded with USD↔GBP, USD↔EUR baseline rates (migration 023, #174)

### Database — Schema Changes
- **Multi-currency** — `currency NVARCHAR(3) DEFAULT 'USD'` added to: `policies`, `claims`, `claim_reserves`, `claim_payments`, `billing_accounts`, `invoices`, `reinsurance_treaties`, `reinsurance_cessions`, `reinsurance_recoveries`, `products`, `submissions` (migration 023, #174)
- **Product inheritance** — `parent_product_id UNIQUEIDENTIFIER REFERENCES products(id)` and `is_template BIT DEFAULT 0` on `products` table with filtered index (migration 024, #177)

### New Capabilities
- **Product template inheritance** — `SqlProductRepository.get_effective_product()` resolves parent chains (max depth 10, circular-ref safe). Child overrides parent for non-NULL scalars; coverages, rating factors, and appetite rules merge additively unless child defines same code. API: `GET /products/{id}/effective` (#177)
- **Historical rating** — `GET /products/{id}/rate?as_of=YYYY-MM-DD` rates with factors effective at a specific date for regulatory audit. `RatingEngine.calculate(as_of_date=)` filters `rating_factor_tables` by `effective_date`/`expiration_date` (#181)
- **Rating factor versioning** — `ProductRelationsRepository.version_rating_factor()` inserts a new factor version and expires the old one (INSERT + SET expiration_date, never UPDATE) (#181)
- **Rated-with tracking** — `Submission.rated_with_snapshot_id` records which factor set was used for a quote (#181)

### Metrics
- 110 tests pass on affected modules (81 existing + 29 new)
- 41 database tables across 17 migrations (up from 40/15)
- 175+ API endpoints

### Agents
- Backend (#174, #177, #181)

---

## v107 — Data Model Hardening Complete (2026-03-31)

### Summary
Final documentation and verification pass after completing the full data model hardening block:
9 new SQL migrations (006–015), 10 GitHub issues (#156–#165), 9 new tables, bringing total from 26 to 40.

### Database — New Tables
- **`change_log`** — Data-level audit trail; immutable append-only event log recording every INSERT/UPDATE/DELETE with actor, entity, field-level diffs (migration 009, #161)
- **`consent_records`** — GDPR Art. 7 consent tracking with purpose, evidence, grant/revoke timestamps (migration 014, #165)
- **`retention_policies`** — GDPR data retention schedules per entity type with configurable periods (migration 014, #165)
- **9 product relational tables** — `product_coverages`, `coverage_deductibles`, `product_rating_factors`, `rating_factor_tables`, `product_appetite_rules`, `product_authority_limits`, `product_territories`, `product_forms`, `product_pricing` (migration 015, #164)

### Database — Schema Hardening
- **Referential integrity** — 17 foreign key constraints with RESTRICT/CASCADE semantics (migration 006, #156)
- **Performance indexes** — 17 NONCLUSTERED indexes for query-path and analytics (migration 007, #158)
- **Soft deletes** — `deleted_at DATETIME2` column on 10 core tables; queries filter by default (migration 008, #160)
- **Concurrency control** — `ROWVERSION` columns on 5 high-contention tables for optimistic locking (migration 010, #159)
- **Business constraints** — 7 CHECK constraints (date ordering, non-negative financials) (migration 011, #162)
- **Unique constraints** — 3 composite unique indexes (active policies, billing per policy, active renewals) (migration 012, #163)
- **Party indexes** — 4 indexes on parties (tax_id, name, registration_number) for deduplication (migration 013, #157)

### New Services
- **`AuditService`** — change_log querying, entity history reconstruction
- **`GDPRService`** — consent management, right to erasure (anonymization), data portability export
- **`PartyResolutionService`** — party deduplication and matching using tax_id, name, registration_number

### New API Module
- **`/api/v1/gdpr`** (6 endpoints) — consent grant/revoke/list, right to erasure, data portability, retention policy management

### Metrics
- 750 tests passing (up from 665)
- 172 API endpoints across 31 modules (up from 153/28)
- 40 database tables across 15 migrations (up from 26/3)

### Agents
- Backend (#156, #157, #158, #159, #160, #161, #162, #163, #164, #165)
- Security (#165)
- Scribe (documentation refresh)

---

## v106 — Product Data: JSON → Relational Migration (#164) (2026-03-30)

### Added
- **`ProductRelationsRepository`** — normalised relational tables for product sub-entities
  (`product_coverages`, `rating_factor_tables`, `product_appetite_rules`, `product_authority_limits`,
  `product_territories`, `product_forms`, `product_pricing`) with dual-write sync from JSON blobs.
- **`RatingEngine`** — product-aware rating engine that loads factors from `rating_factor_tables` SQL
  table. Falls back to hardcoded `INDUSTRY_RISK_FACTORS` / `REVENUE_BANDS` dicts when no relational
  data exists (backward compat).
- **`check_appetite()`** — evaluates product appetite rules from relational DB against submission risk
  data during triage fallback. Supports operators: `>=`, `<=`, `between`, `in`, `not_in`, `eq`, `neq`.
- **`get_product_relations_repository()`** factory function for DI.
- **`ProductSummary`** response model for lightweight list endpoint.
- **Relational enrichment** on `GET /products/{id}` — assembles response from normalised tables,
  falls back to JSON columns.

### Changed
- **Rating engine** (`CyberRatingEngine`) now accepts optional DB-loaded factors via `set_db_factors()`.
  Industry and revenue band lookups prefer relational data when available.
- **Triage service** (`SubmissionService.run_triage`) checks relational appetite rules before legacy
  in-memory knowledge store rules.
- **Knowledge sync** (`ProductKnowledgeSyncService.sync_product`) loads relational coverages, factors,
  and rules when available, building richer knowledge documents from typed columns instead of JSON parsing.
- **Product coverages endpoint** (`GET /products/{id}/coverages`) prefers relational table data.
- **Product list endpoint** (`GET /products`) remains lightweight — does NOT load relations per product.

### Deprecated
- JSON blob columns on `products` table (`coverages`, `rating_factors`, `appetite_rules`,
  `authority_limits`, `territories`, `forms`, `metadata`) — marked deprecated in code comments.
  Will be removed after migration period when all consumers read from relational tables.

### Metrics
- 665 unit tests passing
- 0 regressions from JSON → relational migration

## v105 — Service Layer Extraction for Submissions (#137) (2026-03-27)

### Refactored
- **800+ LOC of business logic extracted from API handlers into `SubmissionService`** — Triage, quote, bind, and full-workflow logic previously inline in `api/submissions.py` endpoint handlers is now encapsulated in `services/submission_service.py`. API handlers are thin (~10-25 LOC) delegators that extract request params, call the service, and return the response.
- **`SubmissionService.run_triage()`** — Foundry triage invocation, compliance decision recording, domain event publishing, and knowledge-store rule-based fallback.
- **`SubmissionService.generate_quote()`** — Foundry underwriting with prompt builder, rating engine fallback, authority check with escalation, compliance recording.
- **`SubmissionService.bind()`** — Authority check, Foundry policy review, declaration page generation, billing account creation, reinsurance cession calculation, domain event publishing.
- **`SubmissionService.process()`** — Full multi-agent workflow orchestration (triage → quote → authority → auto-bind) with compliance recording.
- **Shared helpers extracted** — `_record_decision()`, `_check_authority_and_escalate()`, `_auto_cession()`, `_build_policy_data()`, `_parse_json_field()` reduce duplication across service methods.

### Architecture
- **API layer is now thin** — No endpoint handler exceeds 30 LOC. All business logic (Foundry calls, rating calculations, authority checks, escalation, compliance recording, event publishing) lives in the service layer.
- **Testability improved** — Business logic can be unit-tested by instantiating `SubmissionService` directly, without going through HTTP. Foundry client and repos are mockable.
- **Reusability** — MCP tools, CLI, or other interfaces can call `SubmissionService` methods directly without duplicating logic.

### Agents
- Backend (#137)

### Metrics
- 627 unit tests passing
- Live lifecycle test (Create → Triage → Quote → Bind) verified on deployed backend

---

## v104 — Transaction Management for Multi-Step Operations (2026-03-27)

### Fixed
- **No transaction management (#136)** — Bind, quote, and cession operations now execute within explicit database transactions. Previously, if policy creation succeeded but the billing account or submission status update failed, the system could leave orphan policies and inconsistent state.

### Architecture
- **`TransactionContext` async wrappers** — Added `async_execute_query`, `async_fetch_one`, `async_fetch_all` to `TransactionContext` so transaction-bound operations can be safely `await`ed from the event loop without blocking.
- **Repository `txn` parameter** — `SqlSubmissionRepository`, `SqlPolicyRepository`, `SqlBillingRepository`, and `SqlCessionRepository` `create()`/`update()` methods now accept an optional `txn: TransactionContext` keyword argument. When provided, queries run on the transaction's connection instead of acquiring a separate pooled connection.
- **Bind transaction boundary** — Core bind ops (INSERT policy, INSERT billing account, UPDATE submission status) are wrapped in a single atomic transaction. Cessions use a separate transaction. Non-critical operations (Foundry AI review, event publishing, compliance logging) remain outside transactions.
- **Quote transaction boundary** — Submission status update to "quoted" is wrapped in a transaction.
- **Cession atomicity** — All cession INSERTs for a bind are wrapped in their own transaction so partial cession sets are never committed.

### Agents
- Backend (#136)

### Metrics
- 627 unit tests passing
- Live lifecycle test (Create → Triage → Quote → Bind) verified on v104 deployment

---

## v103 — GDPR Compliance: Consent & Data Retention (#165) (2026-03-29)

### Added
- **`consent_records` table** — tracks GDPR Art. 7 consent with purpose, evidence, grant/revoke timestamps
- **`retention_policies` table** — configurable data retention schedules per entity type (7 years financial, 10 years claims)
- **`GDPRService`** — consent management, right to erasure (anonymization), data portability export
- **GDPR API** (`/api/v1/gdpr`) — 6 endpoints: consent grant, consent revoke, consent list, right to erasure, data portability, retention policies

### Migration
- `014_gdpr.sql` — creates tables with seed retention policies for all entity types

### Agents
- Backend (#165), Security (#165)

---

## v102 — Unique Constraints & Party Deduplication (#163, #157) (2026-03-29)

### Added
- **3 composite unique indexes** — prevent duplicate active policies per submission, duplicate billing per policy, duplicate active renewals (migration 012, #163)
- **4 party indexes** — tax_id, name, registration_number, and party_type for deduplication queries (migration 013, #157)
- **`PartyResolutionService`** — party matching and deduplication using indexed columns

### Agents
- Backend (#157, #163)

---

## v101 — Business Constraints & Concurrency Control (#162, #159) (2026-03-28)

### Added
- **7 CHECK constraints** — effective_date < expiration_date, non-negative premiums/reserves/payments, claim date ≤ report date (migration 011, #162)
- **ROWVERSION columns** on 5 high-contention tables — submissions, policies, claims, billing_accounts, reinsurance_treaties for optimistic locking (migration 010, #159)

### Agents
- Backend (#159, #162)

---

## v100 — Data-Level Audit Trail (#161) (2026-03-28)

### Added
- **`change_log` table** — immutable append-only audit trail recording every data mutation with actor, entity type, entity ID, action (INSERT/UPDATE/DELETE), field-level before/after values, and correlation IDs
- **`AuditService`** — queries change_log for entity history, actor activity, and compliance reporting
- **2 indexes** on change_log (entity lookup, actor + timestamp) for efficient audit queries

### Migration
- `009_audit_trail.sql` — creates change_log table with indexes

### Agents
- Backend (#161)

---

## v99 — Soft Deletes (#160) (2026-03-28)

### Added
- **`deleted_at DATETIME2` column** on 10 core tables — parties, products, submissions, policies, claims, billing_accounts, reinsurance_treaties, renewal_records, mga_authorities, mga_bordereaux
- Repository queries now filter `WHERE deleted_at IS NULL` by default; admin queries can include soft-deleted records
- Supports GDPR right-to-erasure workflow (anonymize then soft-delete)

### Migration
- `008_soft_deletes.sql` — adds deleted_at to all core tables (idempotent)

### Agents
- Backend (#160)

---

## v98 — Foundry Agents Live + Portal E2E Fixes (2026-03-27)

### Fixed
- **Foundry agents now invoked** — deployed gpt-5.2 model, fixed `agent_reference` key (#118)
  - Triage returns real AI risk analysis (appetite matching, industry scrutiny, data completeness)
  - Risk scores are AI-assessed (not flat 5.0)
- **Dashboard form field mapping** — 13 fields corrected: applicant_name, risk_data.*, cyber_risk_data.* (#117)
- **Dashboard API auth** — nginx forwards X-API-Key header, removed mock fallbacks (#115)
- **CodeQL + Dependabot** — 12 CodeQL alerts fixed (stack trace exposure, sensitive logging), 3 npm vulnerabilities patched (#116)

### Added
- 12 GitHub issues filed from UX review (#119-#130): pagination, confirmation dialogs, toast feedback, status-aware buttons, mobile responsive fixes

---

## v97 — Referential Integrity & Performance Indexes (#156, #158) (2026-03-27)

### Added
- **17 foreign key constraints** with ON DELETE RESTRICT (integrity) and CASCADE (child records) semantics across all entity relationships (migration 006, #156)
- **17 NONCLUSTERED indexes** on high-traffic query paths: submission status, policy dates, claim status, billing lookups, reinsurance treaty queries, knowledge search (migration 007, #158)

### Architecture
- Database now enforces referential integrity at the SQL level (previously application-only)
- Query performance improved for dashboard aggregations and list endpoints

### Migration
- `006_referential_integrity.sql` — 17 FK constraints
- `007_performance_indexes.sql` — 17 indexes

### Agents
- Backend (#156, #158)

---

## v96 — Bug Fixes: Auth Enforcement, Product Creation, Claims Validation, Compliance UI (2026-03-27)

### Fixed
- **Auth enforcement** (#111) — API now returns `401 Unauthorized` / `403 Forbidden` for missing or invalid API keys when `OPENINSURE_API_KEY` is configured. Previously, unauthenticated requests were silently allowed.
- **Product creation** (#112) — `POST /api/v1/products` now auto-generates `product_code` (LOB prefix + UUID) when not provided, coerces `version` to INT for SQL compatibility, and defaults `effective_date` to today.
- **Claims validation** (#113) — `POST /api/v1/claims` now returns `422 Unprocessable Entity` when referencing a non-existent policy. Previously returned `500 Internal Server Error`.
- **Compliance workbench UI** (#110) — Fixed React "Objects are not valid as a React child" crash in the decision audit display by serializing complex decision objects before rendering.

### Metrics
- CI green: 636 tests passing (up from 566)

## v95 — Tech Debt Refactoring: 16 Issues Resolved (2026-03-26)

All 16 tech-debt issues (#92–#107) identified in the v94 codebase audit have been resolved in a single structural refactoring block.

### Architecture
- **prompts.py god file → `agents/prompts/` package** — 1,265-line monolith split into 13 focused modules (`_triage.py`, `_underwriting.py`, `_claims.py`, `_policy.py`, `_compliance.py`, `_document.py`, `_enrichment.py`, `_knowledge.py`, `_analytics.py`, `_billing.py`, `_comparable.py`, `_orchestrator.py`, `__init__.py` re-exports) (#92)
- **Policy lifecycle consolidated** — duplicate logic between `policy_agent.py` and `services/policy_lifecycle.py` merged into single authoritative service (#93)
- **Knowledge paths unified** — 8 redundant retrieval paths consolidated into single Cosmos → AI Search pipeline (#97)

### Reliability
- **Rating engine as Foundry fallback (3-tier cascade)** — Foundry agent → `CyberRatingEngine` (local) → LOB-appropriate minimum premium. Eliminates flat $5K hardcode (#94)
- **State machine enums aligned** — `referred`, `reinstated`, `reported` now defined in `domain/state_machine.py` enums, matching the actual state diagrams (#99)

### Code Quality
- **Phantom agents → Foundry wrappers** — 5 stub agents (enrichment, analytics, document, knowledge, compliance) now delegate to Foundry client with graceful fallback (#96)
- **Compliance repos implement BaseRepository** — `ComplianceRepository` now extends the same base as all other repos (#98)
- **Centralized authority limits** — 30+ hardcoded limits extracted to `domain/limits.py` (`AuthorityLimitsConfig`, `ReserveGuidelines`) (#103)
- **Typed API endpoints** — 13 raw-dict endpoints replaced with Pydantic response models (#100)
- **Domain events wired** — 7 event classes (`SubmissionReceived`, `SubmissionTriaged`, `SubmissionQuoted`, `PolicyBound`, etc.) now emitted via `event_publisher` on state changes (#102)
- **Knowledge data extracted** — 738 lines of embedded data removed from `knowledge_agent.py`, now served from Cosmos/AI Search (#105)
- **Duplicate routes cleaned** — hidden `include_in_schema=False` routes removed, API naming normalized to plural paths (#106, #107)
- **Duplicate bias monitoring consolidated** — single `services/bias_monitor.py` replaces parallel implementations (#95)
- **Duplicate workflow paths removed** — redundant workflow definitions collapsed (#101)

### Product Pipeline
- **Product API persistence + knowledge sync** — all product mutations persist to Azure SQL and trigger async sync: SQL → Cosmos DB → AI Search → Foundry agents. `ProductKnowledgeSyncService` handles the pipeline (#104)

### Fixed
- CI green: 566 tests passing (up from 520)
- API surface: 153 endpoints across 28 modules (up from 118/21)

## v94 — SQL Product Data Model + Tech Debt Audit (2026-03-25)

### Changed
- **Products migrated to Azure SQL** — proper relational data model replaces in-memory seed data (#91)
  - Migration `005_products_table.sql` adds JSON columns (coverages, rating_factors, appetite_rules, authority_limits, territories, forms, metadata)
  - `SqlProductRepository` with full CRUD, filtering, pagination
  - 4 seed products (Cyber SMB, Professional Indemnity, D&O, Tech E&O)
  - Factory pattern auto-selects SQL repo in Azure mode
- **Unified Technical Documentation** — `docs/TECHNICAL_OVERVIEW.md` (53KB) replaces 5 redundant docs
  - Deleted: `ai-native-assessment.md`, `mcp-integration.md`, `e2e-demo-case.md`, `e2e-test-results.md`, `document-channels.md`
  - 12 sections with Mermaid architecture diagrams
- **16 tech-debt issues filed (#92–#107)** from deep codebase audit
  - Critical: prompts.py god file, duplicate policy lifecycle, rating engine fallback
  - High: phantom agents, knowledge path consolidation, SQL repo parity
  - Medium: duplicate workflows, unused events, embedded knowledge data
- **Documentation hygiene** — all env-specific URLs removed from docs (19+ files cleaned)
- **Foundry agents on GPT-5.2** — all 10 agents upgraded from gpt-4o

### Fixed
- Product Management page now shows SQL-persisted products (not empty)
- CI green: 520+ tests passing (ruff, mypy, bandit, pytest)

## v90 — GPT-5.2 + Knowledge Verification (2026-03-25)
- All 10 Foundry agents upgraded to GPT-5.2 (from gpt-4o)
- Playwright verified: Knowledge page (7 tabs), UW Workbench, Executive Dashboard all show Cosmos data
- Fixed: Compliance Workbench blank page (bias report error handling)
- CI green: all mypy errors resolved

## v89 — Unified Knowledge Architecture (2026-03-25)
- Cosmos DB as central knowledge source of truth (13 docs seeded)
- Cosmos private endpoint (10.0.2.5/10.0.2.6) — no public access needed
- AI Search index (50 docs) attached to all 10 Foundry agents
- Admin endpoints: /admin/seed-knowledge, /admin/deploy-agents
- Knowledge API reads from Cosmos with in-memory fallback
- Cosmos → AI Search sync architecture documented

## v85-v88 — Foundry Tools + Knowledge + AI-Native (2026-03-24)
- Azure AI Search tool attached to all 10 agents (autonomous knowledge retrieval)
- Function calling on underwriting agent (get_rating_factors, get_comparable_accounts)
- Conversations API support for multi-turn agent interactions
- Knowledge indexer script (index_knowledge.py)
- Foundry integration strategy documented (474 lines)

## v84 — AI-Native Knowledge Pipeline (2026-03-24)
- Decision Learning Loop — tracks outcomes, feeds accuracy back to agents
- Comparable Account Retrieval — agents see similar past submissions
- Dynamic Knowledge Retrieval — submission-specific context (industry, SIC, jurisdiction)
- Intelligent fallbacks — CyberRatingEngine + knowledge-based appetite rules
- 520 tests, 29 MCP tools

## [0.7.0] — Unified Knowledge Architecture

### Added
- **Cosmos DB as Single Source of Truth**: All knowledge data (guidelines, rating factors, coverage options, claims precedents, compliance rules, industry profiles, jurisdiction rules) is stored in Cosmos DB. The API reads/writes Cosmos first, falling back to the in-memory store when Cosmos is unavailable.
- **Key-Based Auth Fallback**: `CosmosKnowledgeStore` now accepts an optional `cosmos_key` parameter. When RBAC (`DefaultAzureCredential`) fails, the system falls back to key-based authentication — resolving the months-long RBAC access issue.
- **Cosmos → AI Search Auto-Sync**: `src/scripts/setup_cosmos_search_sync.py` creates an AI Search **data source** and **indexer** that auto-syncs from Cosmos every 5 minutes. Changes made in the portal propagate to Foundry agents automatically.
- **Comprehensive Knowledge Seeder**: `src/scripts/seed_cosmos_knowledge.py` reads ALL knowledge from YAML files (`knowledge/`) AND the rich in-memory store (`knowledge_store.py`) — industry profiles, jurisdiction rules, billing rules, workflow rules — and uploads everything to Cosmos DB.
- **New API Endpoints**:
  - `GET /knowledge/industry-profiles` — list all industry risk profiles
  - `GET /knowledge/industry-profiles/{industry}` — get profile by industry
  - `GET /knowledge/jurisdiction-rules` — list all jurisdiction compliance rules
  - `GET /knowledge/jurisdiction-rules/{territory}` — get rules by territory
  - `PUT /knowledge/claims-precedents/{claim_type}` — update claims precedent (writes to Cosmos)
  - `PUT /knowledge/compliance-rules/{framework}` — update compliance rule (writes to Cosmos)
  - `GET /knowledge/sync-status` — check Cosmos availability and active data source
- **Dashboard Enhancements**: Knowledge page now has 7 tabs (added Industry Profiles and Jurisdiction Rules), a live sync-status badge showing Cosmos vs in-memory source, and all existing tabs now read Cosmos-first.
- **Full CRUD on CosmosKnowledgeStore**: `bulk_upsert`, `query_rating_factors`, `query_coverage_options`, `query_claims_precedents`, `query_compliance_rules`, `query_industry_profiles`, `query_jurisdiction_rules`, `delete_document`

### Changed
- `config.py`: Added `cosmos_key` and `search_admin_key` settings for fallback auth
- `factory.py`: `get_knowledge_store()` now passes `cosmos_key` to `CosmosKnowledgeStore`
- `cosmos_nosql.py`: Rewritten with key-based auth fallback, `updated_at` timestamps, all entity-type query methods
- `api/knowledge.py`: All endpoints now try Cosmos first with graceful in-memory fallback; PUT endpoints write to Cosmos; new `/sync-status` endpoint
- `dashboard/src/api/knowledge.ts`: Added API calls for industry profiles, jurisdiction rules, and sync status
- `dashboard/src/pages/KnowledgePage.tsx`: Added Industry Profiles tab, Jurisdiction Rules tab, and SyncStatusBadge component

### Architecture
```
Portal (React) → REST API → Cosmos DB (source of truth)
                                  ↓ (indexer, every 5 min)
                           AI Search Index
                                  ↓ (AI Search tool)
                           Foundry Agents (10)
```
- **Write path**: Portal → API → Cosmos DB → Indexer → AI Search → Agents see it
- **Read path**: API → Cosmos DB (or in-memory fallback) → Portal
- **Agent path**: Agent → AI Search tool → openinsure-knowledge index (auto-synced from Cosmos)
- **Graceful degradation**: When Cosmos is unavailable, all reads fall back to the in-memory knowledge store seamlessly

## [0.6.0] — 10/10 AI-Native with Foundry Tools

### Added
- **Azure AI Search Knowledge Tool**: All 10 Foundry agents now have `AzureAISearchToolDefinition` attached. Agents autonomously search the `openinsure-knowledge` index for underwriting guidelines, rating factors, regulatory requirements, and coverage rules — replacing the prompt injection pattern in `prompts.py`.
  - Knowledge indexer script: `src/scripts/index_knowledge.py` — parses YAML knowledge files into chunked documents with hybrid vector + keyword schema, optional embeddings via `text-embedding-ada-002`, `--dry-run` support
  - Index schema: `id`, `content`, `title`, `category`, `source`, `tags`, `content_vector` (1536-dim HNSW)
- **Web Search for Enrichment**: `openinsure-enrichment` agent gets `WebSearchPreviewToolDefinition` for real-time company research, breach database lookups, and regulatory change detection. Replaces simulated data from `enrichment.py`.
- **Foundry Memory for Session Continuity**: `openinsure-underwriting` and `openinsure-claims` agents get `MemoryToolDefinition` for cross-session user preference storage, conversation summaries, and agent knowledge accumulation.
- **Function Calling for Underwriting**: `openinsure-underwriting` agent gets two `FunctionToolDefinition` tools:
  - `get_rating_factors(lob)` — fetches cyber insurance rating factors by line of business
  - `get_comparable_accounts(industry_sic, annual_revenue?, employee_count?)` — finds similar historical accounts for pricing comparison
- **Multi-Turn Conversation Support**: `foundry_client.py` now supports Foundry conversations via `create_conversation()` and `invoke_in_conversation()`. The existing `invoke()` method accepts an optional `conversation_id` kwarg for backward compatibility.
- **Canonical Deploy Script**: `src/scripts/deploy_foundry_agents.py` is now the single source of truth for agent deployment — creates all 10 agents with tools, discovers search connections at runtime, environment-driven configuration.

### Changed
- `config.py`: Added `search_connection_id` setting for Foundry project connection to AI Search
- `.env`: Added `OPENINSURE_FOUNDRY_PROJECT_ENDPOINT` for Foundry Agent Service
- `foundry_client.py`: Refactored JSON parsing into `_parse_response()` static method (DRY)
- `docs/architecture/foundry-integration-strategy.md`: Updated status to "Implemented (Phases 1–4)" with full implementation log

### Architecture
- **Tool assignment matrix**: AI Search (all agents), Web Search (enrichment), Memory (underwriting + claims), Function Calling (underwriting)
- **Graceful degradation**: All tools are optional — agents deploy without tools when connections are unavailable
- **Preserved**: DecisionRecord/EU AI Act compliance, learning loop, orchestrator, knowledge_store fallback, enrichment fallback

## [0.5.0] — AI-Native Knowledge Pipeline

### Added
- **Decision Learning Loop** (`services/learning_loop.py`): Tracks AI decision outcomes for continuous improvement. When claims are filed or policies renew/cancel, outcomes are correlated with the original triage/quote/bind decisions. Computes per-agent accuracy metrics and detects systematic biases (e.g., "Healthcare submissions were underpriced by 15%"). Historical accuracy context is injected into agent prompts so agents self-correct over time.
  - API: `GET /api/v1/analytics/decision-accuracy`, `POST /api/v1/analytics/decision-outcome`
  - MCP tool: `get_decision_accuracy`
  - Closes #86
- **Comparable Account Retrieval** (`services/comparable_accounts.py`): When assessing a new submission, agents now see how similar past submissions were handled. Matches by LOB, industry (SIC prefix), revenue band (±50%), employee count (±50%), and security maturity. Returns pricing history, claim outcomes, and loss ratios.
  - API: `GET /api/v1/submissions/{id}/comparables`
  - MCP tool: `get_comparable_accounts`
  - Triage prompt includes: "COMPARABLE ACCOUNTS: 3 similar tech companies — 2 proceeded, 1 declined"
  - Underwriting prompt includes: "COMPARABLE PRICING: Similar companies priced at $8K-$15K. Average loss ratio: 42%"
  - Closes #87
- **Dynamic Knowledge Retrieval** (enhanced `agents/prompts.py`): Knowledge retrieval is now contextual per submission. A healthcare company gets HIPAA rules, a fintech gets PCI/GLBA requirements, and a ransomware-heavy industry gets ransomware precedents. Jurisdiction-aware regulatory context (US/EU/UK) is included automatically.
  - New knowledge store methods: `get_industry_guidelines()`, `get_compliance_rules_for_jurisdiction()`, `get_claims_precedents_by_type()`
  - 6 industry profiles: healthcare, financial_services, technology, retail, manufacturing, education
  - 3 jurisdiction profiles: US, EU, UK
  - Closes #88
- **55 new unit tests** covering all three features (520 total, up from 465)
- **2 new MCP tools** (`get_decision_accuracy`, `get_comparable_accounts`) bringing total to 29

### Changed
- `build_triage_prompt()` and `build_underwriting_prompt()` now accept `dynamic_knowledge`, `comparable_context`, and `learning_context` keyword arguments for AI-native context injection
- `build_prompt_for_step()` (workflow engine dispatcher) automatically retrieves and injects learning loop context, comparable accounts, and dynamic knowledge for intake and underwriting steps
- `InMemoryKnowledgeStore` expanded with industry-specific guidelines, jurisdiction compliance rules, and fuzzy claims precedent matching

## [0.4.0] - 2026-03-19

### Added
- ProcessWorkflowModal: Microsoft Foundry AI pipeline visualization in dashboard
- Squad agent team: 7 specialized development agents with persistent knowledge
- 3-year comprehensive seed script (1,200 submissions, 420 policies, 85 claims)
- Real SQL data rendering on all dashboard pages (field mapping fixes)
- Process buttons on Submissions and Claims pages

### Fixed
- SQL→dashboard field mapping (dates, names, severities, totals)
- Dashboard mock fallback restored for resilience
- SQL network access persistence
- CI pipeline green (lint + mypy fixes)

## [0.3.0] - 2026-07-22

### Added

- **Reinsurance Management**: Treaty lifecycle management (quota share, excess-of-loss, surplus, facultative), automatic cession calculation on policy bind, capacity utilization tracking, recovery calculation on claim payments, bordereau generation, Reinsurance Dashboard
- **Actuarial Analytics**: Loss development triangle generation, IBNR estimation (chain-ladder method), reserve adequacy analysis by LOB and accident year, rate adequacy testing, Actuarial Workbench with interactive triangles and charts
- **MGA Oversight**: Delegated authority management and monitoring, bordereaux ingestion and validation, authority utilization tracking, performance scoring and audit trail, MGA Oversight Dashboard with scorecards
- **Renewal Management**: 90/60/30-day renewal identification, automated renewal term generation, renewal processing (auto or manual review)
- **Financial Reporting**: Premium analytics (written, earned, unearned), claims analytics (paid, reserved, incurred), cash flow management and forecasting, commission tracking and reconciliation, Finance Dashboard
- **REST API endpoints**: `/api/v1/reinsurance/*`, `/api/v1/actuarial/*`, `/api/v1/mga/*`, `/api/v1/renewals/*`, `/api/v1/finance/*`
- **Test suite**: Expanded to 375 tests covering all new modules and Foundry AI pipeline

## [0.1.0] - 2026-03-09

### Added

- **Core Domain Model**: Party, Submission, Policy, Claim, Product, Billing entities (Pydantic v2)
- **REST API**: Full CRUD endpoints for all insurance operations (FastAPI)
- **AI Agent Framework**: Base agent class with EU AI Act decision record logging
  - Submission Agent (intake, extraction, triage)
  - Underwriting Agent (risk assessment, pricing, authority management)
  - Policy Agent (lifecycle: bind, endorse, renew, cancel)
  - Claims Agent (FNOL, coverage verification, reserving, settlement)
  - Document Agent (classification, extraction, generation)
  - Knowledge Agent (knowledge graph queries)
  - Compliance Agent (audit, bias monitoring, regulatory checking)
  - Multi-agent Orchestrator (new business and claims workflows)
- **Azure Infrastructure (Bicep IaC)**:
  - Azure SQL Database (transactional data)
  - Cosmos DB with Gremlin API (knowledge graph)
  - Azure AI Search (vector + keyword hybrid)
  - Azure Blob Storage (documents)
  - Azure Event Grid + Service Bus (event-driven architecture)
  - Managed Identity + RBAC (security)
  - Azure Monitor + Application Insights (observability)
- **Compliance Layer**:
  - Decision Record store (EU AI Act Art. 12)
  - Immutable audit trail
  - Bias monitoring with 4/5ths rule detection
- **Knowledge Base**:
  - Cyber liability SMB product definition
  - Cyber underwriting guidelines
  - US regulatory requirements
- **MCP Server**: OpenInsure exposed as MCP server for agent integration
- **CI/CD**: GitHub Actions pipeline (lint, type check, security scan, tests)
- **Documentation**: README, CONTRIBUTING, SECURITY, ADRs, deployment guide
