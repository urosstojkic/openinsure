# OpenInsure: Process Completeness Assessment

> Audit of insurance process workflows — what exists, what's missing, and what should be delegated to external integrations.

**Assessed by:** Insurance Domain Agent
**Date:** 2025-07-16
**Scope:** Full platform — carrier and MGA deployment profiles
**Input documents:** architecture-spec-v01, operating-model-v02, process-flows, data-model, and all `src/openinsure/api/` + `src/openinsure/services/` + `src/openinsure/domain/` implementation code

---

## Table of Contents

- [A. Core Platform Processes](#a-core-platform-processes)
  - [1. New Business / Submission Intake](#1-new-business--submission-intake)
  - [2. Underwriting](#2-underwriting)
  - [3. Policy Issuance & Administration](#3-policy-issuance--administration)
  - [4. Claims Management](#4-claims-management)
  - [5. Billing & Finance](#5-billing--finance)
  - [6. Reinsurance](#6-reinsurance)
  - [7. Renewals](#7-renewals)
  - [8. Compliance & Audit](#8-compliance--audit)
  - [9. Reporting & Analytics](#9-reporting--analytics)
- [B. Integration Points](#b-integration-points-external-systems)
- [C. Gap Analysis Table](#c-gap-analysis-table)
- [D. Recommended Roadmap](#d-recommended-roadmap)

---

## A. Core Platform Processes

### 1. New Business / Submission Intake

| Sub-process | Status | Implementation Evidence | Gap |
|---|---|---|---|
| **ACORD ingestion** | ✅ Implemented | `submissions.py` `POST /acord-ingest` endpoint with `acord_parser.parse_acord_xml()`. Parses ACORD 125/126 XML, extracts applicant, risk data, and cyber data fields. 50 MB upload limit. | Only XML supported today; no AL3 or ACORD JSON ingestion. No ACORD 260 (cyber supplement) parser. |
| **Manual entry** | ✅ Implemented | `submissions.py` `POST /submissions` with `SubmissionCreate` model: applicant name, email, channel, LOB, risk data, metadata. | Complete for current needs. |
| **Broker portal submission** | ✅ Implemented | `SubmissionChannel` enum includes `portal`, `broker`, `agent`. Process-flows doc confirms React broker portal (`/portal/broker`) with restricted RBAC. | Portal exists in dashboard; no direct file upload from broker portal to pre-fill submissions. |
| **Triage / appetite check** | ✅ Implemented | Workflow engine `new_business` workflow Step 2 (`intake`): Submission Agent checks SIC code, revenue band, security maturity, prior incidents. Appetite: IT/Tech (SIC 7xxx), Financial (SIC 6xxx), Prof Services. Revenue $500K–$50M. | Appetite rules are hardcoded in prompt templates; no configurable appetite definition engine in the knowledge graph yet. |
| **Data enrichment** | ⚠️ Designed, not implemented | Architecture spec §4.2 describes enrichment step (SecurityScorecard, BitSight, firmographics, news/litigation). No enrichment service or external data connector exists in `src/`. | No `enrichment.py` service or external API integration. Enrichment step is missing from the `new_business` workflow definition. |
| **Referral routing** | ✅ Implemented | `SubmissionStatus.REFERRED` state in state machine. `workflow_engine.py` checks authority limits and escalates. 8 referral triggers documented in process-flows (risk score ≥ 8, prior ransomware, revenue > $25M, etc.). Escalation API endpoints in `escalations.py`. | Referral triggers are documented but the matching logic is in agent prompts, not in deterministic rules. |

**Overall assessment:** 80% complete. The happy path from submission creation through AI-driven triage to quoting works end-to-end. The major gap is the **data enrichment step** — the architecture spec envisions external data integrations (security ratings, firmographics, news monitoring) that are not yet wired up. The ACORD parser handles basic XML but lacks support for broader form types.

---

### 2. Underwriting

| Sub-process | Status | Implementation Evidence | Gap |
|---|---|---|---|
| **Risk assessment / scoring** | ✅ Implemented | Workflow engine Step 3 (`underwriting`): Underwriting Agent scores risk with base rate $1.50/$1K revenue, adjusts for industry, security, incidents. `SubmissionResponse` includes `risk_score`. | Scoring is LLM-prompt-based; no deterministic rating model exists alongside the AI model. |
| **Pricing / rating engine** | ✅ Implemented | 7 factor tables documented in charter (industry, revenue, security, controls, incidents, limits, deductibles). Premium calculation in `_build_policy_data()` allocates across 5 cyber coverages (breach response 30%, third-party 30%, regulatory 15%, BI 15%, ransomware 10%). | Factor tables are referenced in prompts but not stored as configurable data in the knowledge graph or DB. No rate versioning. |
| **Terms & conditions generation** | ✅ Implemented | Workflow Step 4 (`policy_review`): Policy Agent reviews UW terms, verifies coverages, checks pricing within guidelines. Default coverages generated with limits/deductibles from submission data. | T&C generation is AI-driven; no template-based deterministic fallback for standard terms. |
| **Subjectivities management** | ✅ Implemented | `SubmissionResponse` has a `subjectivities` field (list of dicts). CRUD endpoints for creating, tracking, and clearing subjectivities. Bind-blocking when outstanding subjectivities exist. | No automated subjectivity follow-up reminders or expiry tracking. |
| **Authority matrix / escalation** | ✅ Implemented | `AuthorityEngine` with `check_bind_authority()`, `check_quote_authority()`. 4-tier authority (auto-bind $25K/agent → Junior UW $100K → Sr UW $250K → Committee $500K+). Full escalation API with approve/reject. Escalation chain documented in process-flows. | Authority tiers are hardcoded in `AuthorityEngine`; not yet configurable per deployment. |
| **Decline with reason tracking** | ✅ Implemented | `SubmissionStatus.DECLINED` with `declined_at` timestamp. `SubmissionResponse` has `declination_reason` field. State machine enforces valid transitions to `declined` from `received`, `triaging`, `underwriting`, `referred`, `quoted`. | Decline reason is captured but not categorized (no taxonomy of decline codes for reporting). |

**Overall assessment:** 85% complete. Core underwriting workflow is functional — risk scoring, pricing, authority checks, escalation, and subjectivities tracking all work. The gaps are: (1) the **rating engine** relies on LLM prompts rather than fully configurable factor tables (though rating breakdown display is now implemented), and (2) there is no **rate versioning** or **rate change impact analysis**.

---

### 3. Policy Issuance & Administration

| Sub-process | Status | Implementation Evidence | Gap |
|---|---|---|---|
| **Quote → Bind → Issue** | ✅ Implemented | `submissions.py` has `POST /submissions/{id}/process` for the full workflow: triage → quote → bind. Creates policy with `_build_policy_data()`, sets coverages, creates billing account. `policies.py` has `POST /policies` for direct creation. State machine: `quoted → bound`. | Quote document generation is not implemented (no PDF/document output). |
| **Policy document generation** | ⚠️ Stub only | `policies.py` `GET /{policy_id}/documents` returns placeholder `DocumentItem` objects. No actual document generation service. | No template engine, no PDF generation, no declarations page assembly. The endpoint exists but returns dummy data. |
| **Endorsements / mid-term changes** | ✅ Implemented | `POST /{policy_id}/endorse` with `EndorsementRequest`: description, changes dict, effective date, premium delta. Supports add/remove coverage, update limits/deductibles. Premium automatically recalculated. Endorsement history stored on policy. | No pro-rata premium calculation for mid-term endorsements. Premium delta is manually specified. |
| **Cancellation with return premium** | ✅ Implemented | `POST /{policy_id}/cancel` with pro-rata and short-rate methods. Calculates return premium based on elapsed/remaining days. Short-rate applies 10% penalty. State machine enforces `active → cancelled`. | Cancellation for non-payment workflow (notice sequences, grace periods) not implemented. |
| **Reinstatement** | ✅ Implemented | `POST /{policy_id}/reinstate` with reason and effective date. State machine: `cancelled → reinstated → active`. Reinstatement metadata stored on policy. | No lapse-in-coverage handling (gap coverage check, reinstatement fee). |
| **Non-renewal** | ✅ Implemented | Renewal workflow supports `non_renew` recommendation. `process_renewal` checks recommendation and skips new policy creation on `non_renew`. Renewal record stored with `non_renewed` status. | No non-renewal notice generation or regulatory notice timing enforcement. |

**Overall assessment:** 80% complete. The full policy lifecycle (quote → bind → endorse → cancel → reinstate → renew) is mechanically implemented with proper state machine enforcement. The main gap is **document generation** — no actual policy documents, declarations pages, or certificates of insurance are produced. Additionally, cancellation for non-payment (notice sequences) is not built.

---

### 4. Claims Management

| Sub-process | Status | Implementation Evidence | Gap |
|---|---|---|---|
| **First Notice of Loss (FNOL)** | ✅ Implemented | `POST /claims` with `ClaimCreate`: policy ID, claim type (6 cyber types), description, date of loss, reporter info. Auto-generates claim number. Resolves policy number from linked policy. Sets `notification_required` flag for data breach/regulatory claims. | No conversational FNOL intake (described in architecture but not implemented). API-only. |
| **Coverage verification** | ✅ Implemented | Claims workflow Step 2 (`assessment`): Claims Agent verifies `coverage_confirmed` (true/false) and identifies coverage issues. Policy lookup resolves policy number. | Verification is LLM-based; no deterministic coverage matching against policy terms/exclusions. |
| **Investigation workflow** | ✅ Implemented | `ClaimStatus` includes `UNDER_INVESTIGATION`. Claims queue (`GET /claims/queue`) sorts by severity priority. Investigation support step in claims workflow. | No structured investigation checklist, no document collection workflow, no third-party assignment. |
| **Reserve management (case + IBNR)** | ✅ Implemented | `POST /{claim_id}/reserve` with category, amount, currency, notes. AI-assisted reserve recommendation via Foundry (advisory, human value prevails). Authority check on reserve setting. Actuarial API has IBNR via chain-ladder method. Reserves stored in `claim_reserves` table. | No bulk reserve review, no reserve adequacy alerts, no reserve development tracking over time. |
| **Settlement / payment** | ✅ Implemented | `POST /{claim_id}/payment` with payee, amount, category, reference. Authority check via `check_settlement_authority()`. Escalation to CCO for amounts above adjuster authority ($25K). | No payment scheduling, no partial settlement tracking, no salvage/deductible recovery. |
| **Subrogation / recovery** | ❌ Not implemented | Not present in `claims.py` or any other API module. Reinsurance recoveries exist but subrogation against third parties is absent. | No subrogation identification, pursuit tracking, or recovery accounting. |
| **Regulatory notifications (breach notification)** | ✅ Implemented | `ClaimCreate` sets `notification_required=True` for data breach and regulatory proceeding claims. `ClaimResponse` has `notification_sent_at` field. Claims notification endpoint tracks and records notifications. | No 72-hour timer enforcement. No regulatory body routing. Notification tracking exists but no automated sending to regulatory bodies. |
| **Fraud detection** | ✅ Implemented | Claims workflow produces `fraud_score` (0.0–1.0). Documented fraud indicators: recent inception (<90 days), late reporting (>30 days), revenue mismatch, frequent claims, inconsistent descriptions, known patterns. Score > 0.7 triggers CCO + Compliance review. `ClaimResponse` has `fraud_score` field. | Fraud detection is in agent prompts only; no ML model or rules engine for deterministic fraud scoring. |

**Overall assessment:** 80% complete. FNOL through settlement is implemented with authority checks and AI-assisted reserving. Notifications are tracked. Gaps: (1) **subrogation** is entirely absent, (2) **investigation workflows** lack structured task management, and (3) automated notification sending to regulatory bodies is not implemented. The fraud detection indicators are well-designed but rely on LLM judgment.

---

### 5. Billing & Finance

| Sub-process | Status | Implementation Evidence | Gap |
|---|---|---|---|
| **Premium invoicing** | ⚠️ Schema only | `billing_accounts` and `invoices` tables defined in data model with full lifecycle (draft → issued → due → paid → overdue → void → written_off). Billing plans: full_pay, quarterly, monthly, agency_bill, direct_bill. | No billing API endpoints in `src/`. The `submissions.py` bind process mentions `INSERT billing_account + invoices` but the actual billing module is not implemented in code. |
| **Payment collection / reconciliation** | ✅ Implemented | `finance.py` `GET /reconciliation` computes premium receivables, claims payables, commission payables, reinsurance recoverables, tax reserves from actual policy/claim data. | Reconciliation is read-only computation; no actual payment collection, no payment application, no bank integration. |
| **Commission calculation & payment** | ✅ Implemented | `finance.py` `GET /commissions` aggregates by broker with configurable rates (Broker 12%, Email 10%, Portal 8%, API 6%, Direct 5%). Shows paid/pending/overdue status. | Commission rates are hardcoded. No commission statement generation, no payment processing, no broker-level agreement management. |
| **Installment plans** | ⚠️ Schema only | `billing_accounts.billing_plan` supports `quarterly`, `monthly` in the data model. | No installment schedule generation, no installment-level tracking, no cancellation-for-non-payment workflow. |
| **Earned / unearned premium** | ✅ Implemented | `finance.py` `_earned_premium()` computes pro-rata earned premium by elapsed term days. `financial_summary` returns `premium_written`, `premium_earned`, `premium_unearned`. Policies store `written_premium`, `earned_premium`, `unearned_premium`. | No scheduled earned premium recognition (batch monthly earning). Computed on-demand only. |
| **Financial reporting** | ✅ Implemented | `GET /finance/summary` returns full financial summary: written/earned/unearned premium, claims paid/reserved/incurred, loss ratio, expense ratio (hardcoded 34%), combined ratio, investment income (4% on unearned), operating income. `GET /finance/cashflow` returns monthly collections vs disbursements. | Expense ratio is hardcoded. No statutory reporting format (Annual Statement Schedule P, etc.). |

**Overall assessment:** 55% complete. Financial reporting and derived metrics (loss ratio, combined ratio, earned premium, commissions, reconciliation) are well-implemented as computed views over policy/claim data. However, the **transactional billing pipeline** (invoicing, payment collection, installment management) is schema-only with no API implementation. This is one of the largest gaps in the platform.

---

### 6. Reinsurance

| Sub-process | Status | Implementation Evidence | Gap |
|---|---|---|---|
| **Treaty management** | ✅ Implemented | Full CRUD in `reinsurance.py`: `POST/GET /treaties`, support for quota_share, excess_of_loss, surplus, facultative. Treaty fields: reinsurer, dates, LOBs, retention, limit, rate, capacity, reinstatements. | No treaty negotiation workflow, no treaty terms versioning, no sliding scale commission tracking. |
| **Automatic cession on bind** | ✅ Implemented | `POST /cessions` for cession recording. Policy bind event triggers automatic cession creation per active treaty terms. Links treaty → policy with ceded premium and limit. Updates treaty capacity_used. | No sliding scale commission tracking. |
| **Bordereaux generation** | ✅ Implemented | `GET /bordereaux/{treaty_id}` generates bordereau by treaty with period filtering. Returns cessions, recoveries, totals. Also `POST /finance/bordereaux/generate` for MGA bordereaux. | No standard ACORD bordereau format output. No scheduled generation. |
| **Recovery on claims** | ✅ Implemented | `POST /recoveries` records reinsurance recoveries linked to treaty + claim. Recovery statuses: pending, submitted, collected, disputed. `GET /recoveries` with filtering by treaty, claim, status. | No automatic recovery calculation from treaty terms. Manual recording only. |
| **Capacity tracking** | ✅ Implemented | `GET /treaties/{treaty_id}/utilization` and `GET /treaties/{treaty_id}/capacity`. Calculates utilization from actual cessions. Returns capacity total/used/remaining/pct. | No capacity exhaustion alerts. No aggregate capacity view across all treaties. |

**Overall assessment:** 85% complete. Treaty CRUD, cessions, recoveries, bordereaux, and automatic cession on bind are all functional. Capacity tracking works but lacks alerting when approaching limits. No treaty negotiation workflow or sliding scale commission tracking.

---

### 7. Renewals

| Sub-process | Status | Implementation Evidence | Gap |
|---|---|---|---|
| **Expiry detection** | ✅ Implemented | `GET /renewals/upcoming` with configurable look-ahead (1–365 days). `identify_renewals()` service scans policies. Returns 30/60/90-day buckets with policy details and days-to-expiry. | No automated scheduling (no cron/Logic App trigger). Detection is on-demand via API call. |
| **Renewal terms calculation** | ✅ Implemented | `POST /renewals/{policy_id}/generate` uses Foundry Underwriting Agent for AI-driven renewal pricing. Local fallback via `generate_renewal_terms()`. Considers claims history. Rate change factors documented: -5% (no claims) to +35% (3+ claims / >$500K). | Renewal pricing factors are in documentation/service code but not configurable by users. |
| **Re-underwriting** | ✅ Implemented | `POST /renewals/{policy_id}/process` Step 1 invokes Underwriting Agent for full renewal assessment. Step 3 runs Compliance Agent audit. | Re-underwriting relies on expiring policy data only; no refresh of external risk data or updated application. |
| **Renewal quote → bind** | ✅ Implemented | `process_renewal` creates new policy record with updated dates and renewal premium. Links to original via `renewal_of` metadata. Stores `renewal_records` with expiring premium, renewal premium, rate change %, recommendation. | No separate renewal quote presentation step. Goes directly from terms generation to new policy creation. Missing broker acceptance flow. |

**Overall assessment:** 85% complete. The renewal pipeline from detection through re-underwriting to new policy creation is solid. It's one of the more complete workflows. Gaps: (1) no **automated scheduling** for renewal detection (manual trigger only), (2) no **broker acceptance step** between terms generation and binding, and (3) no updated risk data refresh during re-underwriting.

---

### 8. Compliance & Audit

| Sub-process | Status | Implementation Evidence | Gap |
|---|---|---|---|
| **AI decision audit trail** | ✅ Implemented | `decision_records` table with 16 columns capturing agent_id, model, input/output summary, reasoning, confidence, fairness metrics, human oversight. `compliance.py` `GET /decisions` with filtering by type, entity, pagination. `GET /audit-trail` for system-wide events. Workflow engine records DecisionRecord for every agent step. | Immutability relies on database constraints; no append-only log or blockchain-style integrity verification. |
| **EU AI Act compliance** | ✅ Implemented | `GET /system-inventory` returns Art. 60 AI system inventory with risk classification (HIGH for triage & fraud, LIMITED for rating). 3 registered AI systems. Every workflow step logs decisions per Art. 12. Risk levels: UNACCEPTABLE, HIGH, LIMITED, MINIMAL. | No FRIA (Fundamental Rights Impact Assessment) generator. No conformity assessment workflow. No Art. 13 transparency reporting for end users. |
| **Bias monitoring** | ✅ Implemented | `POST /bias-report` runs real bias monitoring engine (4/5ths rule, statistical parity, disparate impact analysis) over all submissions via `bias_monitor.generate_bias_report()`. Protected attributes: industry, company size, geography. `BiasMetric` model with threshold comparison. Dashboard visualization with labelled metrics. | No automated alerting on threshold breaches. No protected class expansion beyond the 3 default attributes. |
| **Human oversight framework** | ✅ Implemented | Confidence gating (< 0.5 triggers escalation in workflow). Authority matrix (complexity × consequence). Escalation queue with approve/reject. Every decision records `human_oversight` field (`required`, `recommended`). Override tracking with mandatory reason logging. | No aggregate dashboard for human override frequency. No feedback loop from overrides to model improvement. |
| **Regulatory reporting** | ⚠️ Partially implemented | Financial summary endpoint provides loss/combined ratio. Actuarial reserves and triangles available. MGA bordereaux generation. | No statutory reporting formats (NAIC Annual Statement, Schedule P, IEE). No state DOI submission. No ORSA (EU Solvency II). |

**Overall assessment:** 85% complete. Compliance is a strength of the platform — the EU AI Act foundations (decision logging, system inventory, bias monitoring with real disparate impact analysis, human oversight) are significantly more mature than most insurance platforms. The gaps are in **regulatory reporting output formats** (statutory filings) and **proactive monitoring** (automated alerts on bias threshold breaches).

---

### 9. Reporting & Analytics

| Sub-process | Status | Implementation Evidence | Gap |
|---|---|---|---|
| **Executive dashboards** | ✅ Implemented | React dashboard with executive view (`/executive`). `finance.py` provides summary, cashflow, commissions, reconciliation endpoints. 25-page dashboard with role-based views including knowledge graph UI. | Dashboard data is served but no persistent reporting (no report archive, no scheduled report generation). |
| **Underwriting performance** | ⚠️ Partially implemented | Submission listing with status/channel/LOB filtering. Quote-to-bind tracking (status progression). No dedicated UW performance endpoint. | No hit ratio, no quote-to-bind conversion, no time-to-quote metrics, no broker performance analytics. |
| **Claims analytics** | ⚠️ Partially implemented | Claims listing with status/type filtering. Claims queue with severity-based priority. Total reserved/paid/incurred on each claim. | No claims development visualization, no severity trend analysis, no adjuster performance metrics. |
| **Loss ratio / combined ratio** | ✅ Implemented | `finance.py` computes loss ratio (incurred / earned premium), expense ratio (34% fixed), combined ratio. Rate adequacy endpoint in actuarial API. | Loss ratio is aggregate only; no segmentation by LOB, territory, underwriting year. Expense ratio is hardcoded. |
| **Actuarial reserves & triangles** | ✅ Implemented | `actuarial.py`: `GET /triangles/{lob}` builds loss-development triangles from claims data. `GET /ibnr/{lob}` runs chain-ladder estimation. `GET /reserves` aggregates case reserves by LOB/accident year. `GET /rate-adequacy` compares actual vs target loss ratio. | Triangles built from limited development pattern (5 periods). No paid-vs-incurred comparison. No alternative methods (Bornhuetter-Ferguson, Cape Cod). |

**Overall assessment:** 65% complete. Actuarial analytics (triangles, IBNR, rate adequacy) are a standout feature. Financial reporting derived from live data is solid. The gaps are in **operational analytics** — underwriting performance metrics, claims analytics, and segmented reporting are largely absent.

---

## B. Integration Points (External Systems)

The following capabilities should **not** be built into the core platform. They are best handled by external systems integrated via API, webhook, or Foundry Tools connectors.

| External System | Why External | Integration Approach | Current Status |
|---|---|---|---|
| **Document Management System (DMS)** | Full document lifecycle (versioning, retention, permissions, search) is a solved problem. Azure Blob Storage handles raw storage; a DMS adds governance. | Azure Blob Storage (current) + SharePoint or Hyland/OnBase connector via Foundry Tools. Policy documents, claims evidence, correspondence. | Blob Storage in place. No DMS integration. |
| **Payment Gateway** | Actual payment processing (credit card, ACH, wire) requires PCI-DSS compliance, bank integrations, and fraud detection that are outside insurance core competency. | Stripe, PayPal, or bank transfer APIs. Webhook callbacks on payment success/failure update billing records. | Not integrated. Reconciliation endpoint assumes payments are externally collected. |
| **Email / Communication** | Customer notifications, broker correspondence, statutory notices require deliverability infrastructure, template management, and opt-out compliance. | SendGrid, Azure Communication Services, or M365 Outlook APIs. Domain events trigger notifications. The architecture spec shows a Notification Service subscriber on Service Bus topics. | Not integrated. Architecture describes it; no implementation. |
| **CRM** | Customer relationship management — tracking broker interactions, prospect pipeline, account planning — is a separate concern from insurance transaction processing. | Salesforce, Dynamics 365 via Foundry Tools (1,400+ connectors). Party data synced bidirectionally. | Not integrated. Party module exists but no CRM sync. |
| **Rating Bureau** | ISO/AAIS loss costs, rate filings, approved forms, and statistical reporting are provided by rating bureaus. The core platform applies rates; the bureau provides the base data. | ISO ERC API, AAIS data feeds. Rate tables loaded into the knowledge graph. State filing status tracking. | Not integrated. Rates are embedded in agent prompts. |
| **Regulatory Filing** | State DOI submissions (SERFF), Lloyd's market filings, EU Solvency II SFCR filings require jurisdiction-specific formats and submission portals. | SERFF API, regulatory portal integrations, XBRL generators. Compliance module feeds data; filing systems handle submission. | Not integrated. No filing output formats. |
| **Accounting / General Ledger** | Double-entry bookkeeping, financial statements (GAAP/IFRS/SAP), and tax reporting are specialized accounting functions. | SAP, Oracle, QuickBooks, or Xero via Foundry Tools connector. Premium/claims journal entries pushed to GL. | Not integrated. Finance module provides computed views but no journal entry generation. |
| **HR / Agent Licensing** | Producer licensing verification, appointment tracking, and continuing education tracking are regulatory requirements managed by external systems. | NIPR API for licensing verification. Sircon/Vertafore for appointment management. | Not integrated. No licensing checks on broker submissions. |
| **External Data Providers** | Credit scores, Motor Vehicle Reports (MVR), CLUE loss history, property data (CoreLogic), and security ratings (SecurityScorecard, BitSight) are third-party data. | REST APIs via Foundry Tools or MCP servers. Data enrichment step in submission workflow consumes these feeds. | Not integrated. Enrichment step designed but not implemented. |
| **Catastrophe Modeling** | RMS, AIR Worldwide, CoreLogic catastrophe models require specialized software and data. The core platform provides exposure data; the cat model returns PMLs. | Batch file exchange or API integration. Exposure aggregation endpoint feeds data to cat models. | Not integrated. No exposure aggregation endpoint. |
| **Policy Document Generation** | Template-based assembly of policy forms, declarations pages, certificates, and endorsement schedules is a specialized document composition problem. | Windward, Docmosis, or Azure-based document generation (ARM templates + Blob output). Policy data feeds templates. | Not integrated. Document endpoint returns placeholders. |

---

## C. Gap Analysis Table

| # | Process | Status | Completeness | Priority | Notes |
|---|---------|--------|-------------|----------|-------|
| 1 | **New Business Intake** | ✅ Implemented | 80% | Medium | Missing: data enrichment service, broader ACORD form support |
| 2 | **Underwriting** | ✅ Implemented | 85% | Medium | Missing: configurable rating tables, rate versioning |
| 3 | **Policy Issuance & Admin** | ✅ Implemented | 80% | High | Missing: document generation, cancel-for-non-payment workflow |
| 4 | **Claims Management** | ✅ Implemented | 80% | High | Missing: subrogation, structured investigation, automated regulatory notification sending |
| 5 | **Billing & Finance** | ⚠️ Partial | 55% | **Critical** | Missing: billing API endpoints, invoice lifecycle, payment collection, installment plans |
| 6 | **Reinsurance** | ✅ Implemented | 85% | Low | Missing: capacity alerts, treaty negotiation workflow |
| 7 | **Renewals** | ✅ Implemented | 85% | Low | Missing: automated scheduling, broker acceptance step |
| 8 | **Compliance & Audit** | ✅ Implemented | 85% | Medium | Missing: FRIA generator, statutory reporting formats |
| 9 | **Reporting & Analytics** | ⚠️ Partial | 65% | Medium | Missing: UW performance metrics, segmented loss ratios, claims analytics |
| — | **Workflow Engine** | ✅ Implemented | 85% | — | 3 workflows (new_business, claims, renewal). Condition gating, confidence thresholds, event publishing. |
| — | **State Machines** | ✅ Implemented | 95% | — | Submission, Policy, Claim transitions + invariant validation. Well-tested. |
| — | **Authority / Escalation** | ✅ Implemented | 90% | — | Bind, quote, reserve, settlement authority. Full escalation queue with approve/reject. |
| — | **RBAC / Auth** | ✅ Implemented | 90% | — | 11 persona roles, navigation access matrix, role-based API guards. |
| — | **Event-Driven Architecture** | ✅ Implemented | 70% | Medium | Domain events published via Service Bus. Subscribers described but few wired (e.g., auto-cession). |

**Weighted platform completeness: ~80%** — The transaction processing core (submission → underwriting → policy → claims) is solid. Subjectivities, auto-cession, bias monitoring, and notification tracking were added in v73. Billing is the largest remaining gap. Reporting and analytics need expansion for operational decision-making.

---

## D. Recommended Roadmap

### Phase 1 — Critical Path (next 4–6 weeks)

These gaps block realistic end-to-end insurance operations.

| # | Item | Type | Effort | Rationale |
|---|------|------|--------|-----------|
| 1 | **Billing API implementation** | Build | Large | Cannot operate without invoicing, payment tracking, and installment management. Schema exists; API + service layer needed. |
| 2 | **Policy document generation** | Integrate | Medium | Integrate a template engine (Docmosis, Windward, or a simple Jinja2 + WeasyPrint pipeline) for declarations pages, certificates, and endorsements. |

> **Completed in v73:** Subjectivities tracking (#47), automatic cession on bind (#55), claims notifications (#48), rating breakdown (#70), bias monitoring engine (#73), knowledge UI (#75).

### Phase 2 — Operational Excellence (weeks 6–12)

These gaps reduce operational efficiency and limit platform credibility.

| # | Item | Type | Effort | Rationale |
|---|------|------|--------|-----------|
| 5 | **Data enrichment service** | Integrate | Medium | Wire SecurityScorecard / BitSight / firmographic APIs via Foundry Tools. Add enrichment step to new_business workflow. |
| 6 | **Configurable rating tables** | Build | Medium | Move rating factors from agent prompts to versioned knowledge graph entries. Enable actuarial teams to update rates without code changes. |
| 7 | **Subrogation module** | Build | Medium | Add subrogation identification on claim close, recovery pursuit tracking, and accounting. New API module. |
| 8 | **UW performance analytics** | Build | Small | Hit ratio, quote-to-bind, time-to-quote, broker performance endpoints from existing submission data. |
| 9 | **Scheduled renewal detection** | Build | Small | Logic App or cron trigger for `identify_renewals()` at 90/60/30 days. Generate renewal records automatically. |

### Phase 3 — Carrier Readiness (weeks 12–20)

These capabilities differentiate a platform from an MVP.

| # | Item | Type | Effort | Rationale |
|---|------|------|--------|-----------|
| 11 | **Statutory reporting** | Build | Large | NAIC Annual Statement, Schedule P, IEE formats. Required for licensed carriers. |
| 12 | **FRIA generator** | Build | Medium | EU AI Act Fundamental Rights Impact Assessment. Required by Aug 2026 for high-risk AI systems. |
| 13 | **Cancel-for-non-payment workflow** | Build | Medium | Notice sequences, grace periods, reinstatement rules. Requires billing module (Phase 1). |
| 14 | **Claims analytics & investigation workflows** | Build | Medium | Structured investigation checklists, adjuster workload balancing, severity trend analysis. |
| 15 | **Event subscriber wiring** | Build | Medium | Connect domain events to downstream services: billing on bind, notifications on claim, reinsurance capacity alerts. |

### Integration Priorities (parallel track)

| # | Integration | When | Rationale |
|---|-------------|------|-----------|
| A | **Payment gateway** (Stripe / bank API) | With Phase 1 billing | Cannot collect premiums without payment processing. |
| B | **Email / notification service** | Phase 2 | Broker correspondence, policy delivery, claims updates. |
| C | **External data enrichment** | Phase 2 | SecurityScorecard, BitSight, firmographics for submission enrichment. |
| D | **Document generation engine** | Phase 1 | Policy documents, declarations, certificates. |
| E | **Accounting / GL connector** | Phase 3 | Journal entries from premium/claims transactions. |
| F | **Rating bureau data feeds** | Phase 3 | ISO/AAIS base rates for multi-LOB expansion beyond cyber. |

---

*This assessment reflects the codebase as of v73 (July 2025). Re-assess after each phase completion.*
