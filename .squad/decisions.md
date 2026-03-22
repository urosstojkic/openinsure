# Decisions

> Team decisions that all agents must respect. Managed by Scribe.

---

## Active Directives

### D-001: Foundry-First Agent Architecture
**By:** Insurance Agent
**What:** All AI agents are hosted in Microsoft Foundry using GPT-5.2. Local Python agent classes (`InsuranceAgent` subclasses) serve as fallback only. The workflow engine calls Foundry via `foundry_client.invoke()` for every decision — triage, underwriting, claims assessment, compliance audit. No local stubs in production.
**Why:** Foundry provides managed hosting, versioning, and observability for AI agents. Running agents locally hides execution from audit trails and violates EU AI Act traceability requirements. The fallback path exists only for local development and CI.

### D-002: Fail-Closed Condition Evaluation
**By:** Security Agent
**What:** All AI safety logic defaults to rejection on uncertainty. If an agent's confidence score is below threshold, or if the authority engine cannot determine limits, the system denies the action and escalates. The `AuthorityDecision` enum enforces this: `AUTO_EXECUTE` only when within proven limits, otherwise `RECOMMEND`, `REQUIRE_APPROVAL`, or `ESCALATE`.
**Why:** Insurance is a regulated domain. A false approval (paying an invalid claim, binding an unpriced risk) is catastrophically worse than a false rejection. Fail-closed ensures humans review edge cases.

### D-003: EU AI Act Compliance by Design
**By:** Insurance Agent
**What:** Every AI agent action produces an immutable `DecisionRecord` (Art. 12 Record-Keeping, Art. 13 Transparency, Art. 14 Human Oversight). Records capture `decision_id`, `agent_id`, `model_used`, `input_summary`, `reasoning`, `confidence`, `fairness_metrics`, `human_oversight`, and `execution_time_ms`. The `bias_monitor` enforces the 4/5ths rule on protected characteristics.
**Why:** EU AI Act applies to high-risk AI systems in insurance. Retroactive compliance is impossible — records must be generated at decision time. This is a legal requirement for EU-market deployments.

### D-004: Azure SQL with Private Endpoint
**By:** Infra Agent
**What:** All production data lives in Azure SQL Database accessed via private endpoint within a VNet. No public access. Connection uses Entra ID managed identity with UTF-16-LE access token packing (`DatabaseAdapter`). The `storage_mode` config switch selects between `"azure"` (SQL) and `"memory"` (InMemory) implementations via the repository factory.
**Why:** Insurance data includes PII, PHI, and financial records. Public database endpoints are unacceptable for SOC 2 and GDPR compliance. Private endpoints ensure traffic never traverses the public internet.

### D-005: State Machine Enforcement on All Entity Transitions
**By:** Backend Agent
**What:** Submission, Policy, and Claim entities have explicit state machines with validated transitions. All state changes go through `validate_submission_transition()`, `validate_policy_transition()`, or `validate_claim_transition()` at the domain layer. Invalid transitions raise `InvalidTransitionError`. Invariant checkers (`validate_*_invariants()`) enforce domain rules at each state.
**Why:** Insurance entity lifecycle is strictly regulated. A policy cannot go from "cancelled" to "active" without a reinstatement workflow. Enforcing at the domain layer (not API layer) prevents all bypass paths.

### D-006: RBAC with 23 Entra ID Roles
**By:** Security Agent
**What:** The platform defines 23 roles in `Role(StrEnum)` mapped to Entra ID app roles (`openinsure-*` prefix). Roles are deployment-scoped: 7 roles are CARRIER-only (LOB_HEAD, CHIEF_ACTUARY, ACTUARY, REINSURANCE_MANAGER, DA_MANAGER, MGA_EXTERNAL, REINSURER). Data access uses a 6-level model: Full (F), Read (R), Own (O), Summary (S), Config (C), Propose (P), None (-). All `/api/v1/*` endpoints require `get_current_user` dependency.
**Why:** Insurance platforms serve multiple persona types (underwriters, brokers, adjusters, actuaries) with fundamentally different data access needs. A broker must never see another broker's submissions. Role-based filtering is enforced at the repository layer, not just the UI.

### D-007: Template Deployment Model
**By:** Infra Agent
**What:** OpenInsure deploys as a single-tenant template into each customer's own Azure subscription. Not a multi-tenant SaaS. Each deployment gets its own Azure SQL, Container Apps, Foundry project, and Entra ID tenant. Deployment via `scripts/deploy.ps1` which builds on ACR (server-side) and deploys to Container Apps with auto-incrementing version tags.
**Why:** Insurance carriers and MGAs require data sovereignty — their data must live in their own Azure tenant under their own compliance boundary. Multi-tenant would require cross-tenant data isolation which adds complexity without business benefit for enterprise insurance.

### D-008: Real Data Only — No Mocking in Production
**By:** QA Agent
**What:** All dashboard pages query real Azure SQL data. No hardcoded sample data, no mock API responses in production builds. The 3-year seed script generates realistic interconnected data (1,200 submissions, 420 policies, 85 claims) for demos. Pre-deploy validation via `scripts/smoke_test.py` (15 checks) confirms real data flows end-to-end.
**Why:** Insurance dashboards with fake data are worthless for demos and dangerous for trust. Every chart, KPI, and table must reflect actual database state. Mocked data hides integration bugs and gives false confidence.

---

## Governance

- All meaningful changes require team consensus
- New decisions are written to `.squad/decisions/inbox/{agent-name}-{slug}.md` — Scribe merges them here
- Keep history focused on work, decisions focused on direction
