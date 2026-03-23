# OpenInsure Platform Review v2: Honest Assessment & Agent-Actionable Improvements

**Reviewer:** Claude (based on spec documents co-authored with project lead)
**Review Date:** March 23, 2026
**Scope:** GitHub repo (urosstojkic/openinsure @ commit 08d732d), live backend API (Swagger), live dashboard, alignment with architecture & operating model specs
**Purpose:** Identify gaps and provide prioritized, specific improvement tasks for the agent development team

---

## Executive Summary

**What changed since v1 review (March 10):** Substantial progress. The platform went from 35 endpoints to 90+, from 309 tests to 448+, from 11 dashboard views to 24 pages, CI is now green, there's seeded SQL data (1,540+ submissions, 513 policies, 115 claims), ACORD 125/126 XML ingestion, Azure Document Intelligence integration, a knowledge graph with claims precedents and compliance rules, a one-call demo workflow, and security hardening (parameterized SQL, constant-time auth). The dashboard has a proper persona-based login page with named personas matching the operating model spec.

**The honest verdict:**

The platform has made the leap from "scaffolding" to "functional prototype with real data." The API surface is genuinely comprehensive — 22 modules covering every domain in our spec. The dashboard shows real SQL data, the UW workbench displays 20 real submissions with company names, and the persona login maps correctly to the operating model. This is no longer just scaffolding.

**But the central problem from v1 remains unsolved:** The agents are not doing AI reasoning. The `underwriting_agent.py` `process()` method returns hardcoded zeros. The `foundry_client.py` has real Azure AI Foundry SDK integration (proper `azure-ai-projects` Responses API call, OpenTelemetry instrumentation) — the plumbing is there. But the dashboard shows "Agent Decisions Today: No agent activity data yet" and "Agent Status: 0 active." The Foundry agents aren't connected to the actual workflow that produces the 1,540 submissions and 513 policies in the database. The data comes from `seed_data.py`, not from agent processing.

This means the platform currently demonstrates: "we built a comprehensive insurance system that could theoretically be AI-native once the agents are wired in." It does not yet demonstrate: "AI agents actually process insurance submissions."

**Updated score: 7/10 as prototype, 3.5/10 as AI-native platform.** The gap is entirely in the "AI-native" part — everything else has improved significantly.

---

## 1. What Improved Since v1 (Acknowledge the Progress)

### 1.1 Breadth and Depth Expansion ✅

From 35 to 90+ endpoints across 22 Swagger modules: submissions, policies, claims, billing, compliance, knowledge, reinsurance, actuarial, renewals, MGA oversight, finance, products, documents, events, metrics, escalations, workflows, underwriter queue, broker views, agent traces, demo, and health. This is genuinely carrier-grade API surface.

### 1.2 Real Data and Seeding ✅

`seed_data.py` creates 3+ years of operations: 1,540 submissions, 513 policies, 115 claims, producing $24.19M GWP with a 36.9% loss ratio. The UW workbench shows 20 real submissions with realistic company names (DigitalEdge Payments, ClearView Education, Alpine Wealth Management). This makes the platform demo-able and credible.

### 1.3 Dashboard Persona Login ✅

The login page implements the operating model spec correctly: Leadership (CEO, CUO), Underwriting (Senior UW, Analyst), Claims (CCO, Adjuster), Finance & Compliance (CFO, Compliance Officer), Product & Ops (Head of Product, Operations Lead), and External (Broker). Named personas with role descriptions. This is exactly what the spec called for.

### 1.4 CI Pipeline Green ✅

Latest commit shows "success" badge. 448+ tests passing. Ruff, mypy, bandit, pytest all green. This was a critical fix from v1.

### 1.5 New Integrations ✅

- **ACORD 125/126 XML ingestion** — `POST /api/v1/submissions/acord-ingest` parses commercial insurance applications
- **Azure Document Intelligence** — OCR + structured extraction for PDF/image uploads with regex fallback
- **Knowledge graph** — claims precedents, compliance rules (EU AI Act, GDPR, NAIC), coverage definitions
- **One-call demo** — `POST /api/v1/demo/full-workflow` runs the entire lifecycle in ~3ms

### 1.6 Security Hardening ✅

Parameterized SQL queries (SQL injection prevention), constant-time API key comparison (timing attack prevention), production error sanitization (no stack traces to clients), upload size limits. VNet-integrated Container Apps with Azure SQL private endpoint. These are production-appropriate security measures.

### 1.7 Foundry Client Architecture ✅

`foundry_client.py` is properly built: uses `azure-ai-projects` SDK v2, calls agents via the Responses API, falls back gracefully when Foundry is unavailable, includes OpenTelemetry instrumentation for Application Insights tracing, parses JSON from LLM responses with markdown fence stripping, returns consistent response shapes, and is a singleton. This is genuinely production-quality Foundry integration code.

---

## 2. Critical Gaps That Remain

### 2.1 CRITICAL: The Agents Don't Drive the Workflows

**Evidence from the live dashboard:**
- Dashboard main page → "Agent Decisions Today: No agent activity data yet"
- Dashboard main page → "Agent Status: 0 active"
- Dashboard main page → "Recent Activity: Activity will appear as submissions and claims are processed"
- UW Workbench shows 20 submissions all with identical status: "Quote issued — awaiting bind decision"
- No risk scores, no confidence scores, no recommendations visible in the workbench table columns

**Evidence from the code:**
- `underwriting_agent.py` → `process()` returns `{"confidence": 0.0, "ai_mode": "local_fallback", "ai_warning": "AI unavailable — manual underwriting required"}`
- All 5 other domain agents follow the same pattern: local `process()` returns safe defaults
- The docstring is honest: "In production all reasoning is performed by the Foundry-hosted agent. The local `process()` returns safe minimal defaults."
- `foundry_client.py` has real Foundry SDK integration, but the `invoke()` method sends a raw string message — there's no structured prompt engineering that feeds the agent submission data, knowledge graph context, underwriting guidelines, and output schema

**What this means:** The 1,540 submissions and 513 policies in the database were created by `seed_data.py`, not by agent processing. The rating engine calculates premiums deterministically. The triage is likely rule-based. No LLM was involved in any decision in the current database. The "AI-native" label describes the architecture's intention, not its current operation.

**Agent Task — PRIORITY 1 (Must fix before anything else):**
```
GOAL: Make one submission flow through actual LLM reasoning end-to-end.

Step 1: Build structured prompts for each agent capability.
  The foundry_client.invoke() currently takes a plain string message.
  Instead, each agent needs a structured prompt builder that assembles:
  - System prompt with agent role, authority limits, and output schema
  - Submission data (applicant, risk data, coverage request)
  - Retrieved knowledge (underwriting guidelines from knowledge graph)
  - Authority context (who is requesting, what are their limits)
  - Required output format (JSON schema for the response)

  Example for UnderwritingAgent.assess_risk:
  """
  SYSTEM: You are the OpenInsure Underwriting Agent for cyber insurance.
  You assess risk based on the submission data and underwriting guidelines below.
  
  UNDERWRITING GUIDELINES:
  {retrieved from knowledge graph via /api/v1/knowledge/guidelines/cyber}
  
  SUBMISSION DATA:
  {submission.extracted_data + submission.cyber_risk_data as JSON}
  
  RESPOND IN THIS JSON FORMAT ONLY:
  {
    "risk_score": <1-10>,
    "risk_factors": [{"factor": "...", "impact": "positive|negative|neutral", "weight": <0-1>}],
    "recommendation": "quote|decline|refer",
    "confidence": <0.0-1.0>,
    "reasoning": "..."
  }
  """

Step 2: Wire the prompt into the foundry_client.invoke() call.
  Modify each agent's process() to:
  a) Query knowledge graph for relevant guidelines
  b) Build the structured prompt with submission data + guidelines
  c) Call foundry_client.invoke(agent_name, structured_prompt)
  d) Parse the response into typed domain objects
  e) Validate the response (risk_score in range, confidence in range, etc.)
  f) Create a real Decision Record from the LLM's actual reasoning
  g) Route based on confidence: >= 0.7 auto-process, < 0.7 escalate

Step 3: Wire the agent into the API workflow.
  When POST /api/v1/submissions/{id}/triage is called:
  a) Load submission from DB
  b) Call SubmissionAgent with the submission data
  c) If Foundry available: use LLM response
  d) If Foundry unavailable: fall back to deterministic rules (current behavior)
  e) Store the Decision Record in compliance/decisions
  f) Update submission status
  g) Publish event to Event Grid

  Same pattern for /quote, /bind, claims/reserve, etc.

Step 4: Make this visible in the dashboard.
  After Step 3, the dashboard's "Agent Decisions Today" and "Agent Status"
  sections should show real agent activity. The UW Workbench should show
  risk scores and confidence from actual LLM assessments.

ACCEPTANCE CRITERIA:
- POST /api/v1/submissions/{id}/triage calls the Foundry Submission Agent
- The agent's LLM response produces a real risk score and recommendation
- A Decision Record is created with actual reasoning from the LLM
- The dashboard shows the agent decision in "Agent Decisions Today"
- If Foundry is unavailable, deterministic fallback works (no crash)
```

### 2.2 CRITICAL: UW Workbench Lacks Decision-Support Content

The UW Workbench shows a table with: Priority, Applicant (UUID), Applicant Name, LOB, a text status, and Due date. But it's missing the content that makes it an AI-native workbench:

- **No risk score column** — the table has "Risk" and "Conf" headers but shows status text, not scores
- **No confidence score** — the column exists but appears empty
- **No recommendation** — column header exists but shows status text instead of "quote" / "decline" / "refer"
- **No detail panel** — clicking a submission should open a side panel with the agent's full analysis: risk assessment, rating breakdown, comparable accounts, recommended terms, reasoning chain, and approve/modify/decline buttons

**Agent Task — PRIORITY 2:**
```
1. Populate the Risk column with actual risk scores (1-10) from triage
2. Populate the Conf column with confidence scores (0.0-1.0) from the agent
3. Populate the Recommendation column with: "Quote" / "Decline" / "Refer"
4. Color-code rows: green (auto-processed), amber (needs review), red (escalated)
5. Build submission detail panel that opens on row click, showing:
   - Applicant info (name, industry, revenue, employees)
   - Cyber risk data (security posture, MFA, endpoint protection, etc.)
   - Agent risk assessment with factor breakdown
   - Rating calculation breakdown (base rate × factors = premium)
   - Agent recommendation with reasoning chain
   - Comparable accounts (similar risks, how they were priced)
   - Action buttons: Approve Quote / Modify Terms / Decline / Refer
   - Decision Record link (for compliance audit)
6. When user clicks "Approve Quote" or "Decline":
   - Call the appropriate API endpoint
   - Log the human decision as an override (or confirmation) of the agent recommendation
   - Update the submission status and move it out of the queue
```

### 2.3 CRITICAL: Seeded Data Doesn't Reflect Agent Processing

The 1,540 submissions in the database were bulk-inserted by `seed_data.py`. They likely have uniform or random risk scores, lack Decision Records, and don't have the full audit trail that agent-processed submissions would have. This means the compliance dashboard, bias monitoring, and agent performance metrics all show incomplete or misleading data.

**Agent Task — PRIORITY 3:**
```
Option A (recommended): Re-seed with agent-simulated data
  Modify seed_data.py to simulate agent processing for each submission:
  - Generate realistic risk scores based on industry, revenue, security posture
  - Create Decision Records for each triage, quote, and bind decision
  - Populate confidence scores (distribution: 70% above 0.7, 30% below)
  - Create escalation records for low-confidence submissions
  - Generate audit trail entries
  - Make some submissions declined, some referred, some auto-bound
  - Vary statuses: not all "quoted" — some received, triaging, underwriting, bound, declined

Option B: Process existing seeded submissions through agents
  Create a script that iterates through seeded submissions and runs
  them through the actual agent pipeline (with Foundry or deterministic fallback).
  This produces genuine Decision Records and audit trails.
  More realistic but requires agents to be wired first (depends on Priority 1).
```

---

## 3. Significant Gaps

### 3.1 Rating Engine Transparency

The demo workflow produces a premium of $18,617.04 for Quantum Dynamics Corp. But nowhere in the API response or dashboard can you see HOW that number was calculated. For an insurance professional, the rating breakdown is essential: base rate × industry factor × revenue factor × security factor × limit factor × deductible factor = premium.

**Agent Task:**
```
1. Add a rating breakdown to the quote response:
   {
     "premium": 18617.04,
     "rating_breakdown": {
       "base_rate": 0.003,
       "industry_factor": 1.2,
       "revenue_factor": 1.15,
       "security_factor": 0.85,
       "limit_factor": 1.4,
       "deductible_factor": 0.92,
       "territory_factor": 1.0,
       "experience_factor": 1.0,
       "calculated_premium": 18617.04,
       "minimum_premium": 2500,
       "applied_premium": 18617.04
     }
   }
2. Display this breakdown in the UW Workbench detail panel
3. Make each factor traceable to the knowledge graph (which table, which value)
```

### 3.2 State Machine Enforcement Gaps

All 20 submissions in the UW workbench show identical status: "Quote issued — awaiting bind decision." In a real insurance operation, the queue would show a mix: some in triage, some in underwriting, some quoted, some with outstanding subjectivities. The uniformity suggests the seed data doesn't model realistic state distribution, and the API may not enforce proper state transitions.

**Agent Task:**
```
1. Verify state machine enforcement on all entities:
   - Submission: received → triaging → underwriting → quoted → bound|declined|expired
   - Policy: active → endorsed|renewed|cancelled|expired
   - Claim: fnol → investigating → reserved → settling → closed|reopened
2. API should return 422 with clear error for invalid transitions
   (e.g., cannot bind a submission that hasn't been quoted)
3. Reseed data with realistic state distribution:
   - 30% received/triaging (new)
   - 25% underwriting (in review)
   - 20% quoted (awaiting response)
   - 15% bound (converted)
   - 10% declined/expired
```

### 3.3 Workflow Orchestration — The Orchestrator Agent

The orchestrator.py exists and `POST /api/v1/workflows/new-business/{submission_id}` is in the API. But the dashboard's "ProcessWorkflowModal" (mentioned in README) isn't visible in the UW workbench. The multi-step AI workflow — where the user can see each agent's step-by-step reasoning with confidence scores — is the single most impressive feature to demo and it should be front and center.

**Agent Task:**
```
1. Add a "Process with AI" button to each submission in the UW workbench
2. Clicking it calls POST /api/v1/workflows/new-business/{submission_id}
3. Shows a modal/panel with live progress:
   Step 1: Submission Agent → Extracting data... ✓ (confidence: 0.91)
   Step 2: Submission Agent → Triaging... ✓ (risk score: 6, appetite: match)
   Step 3: Underwriting Agent → Assessing risk... ✓ (confidence: 0.78)
   Step 4: Underwriting Agent → Calculating premium... ✓ ($18,617)
   Step 5: Compliance Agent → Checking regulations... ✓ (no issues)
   Result: Quote ready — within auto-authority
4. Each step links to its Decision Record for audit
5. If confidence < 0.7 on any step, show amber flag and "Requires Review"
```

### 3.4 Broker Portal Depth

The broker persona (Thomas Anderson, Marsh & Co) exists in the login page. The API has `/api/v1/broker/submissions`, `/broker/policies`, `/broker/claims`. But the broker portal needs to be the primary external-facing product — it's where business enters the system.

**Agent Task:**
```
1. Broker portal should allow:
   - Upload a new submission (with file attachments)
   - Track submission status with timeline
   - View and download quotes
   - Request bind (click to accept quote terms)
   - View active policies and download documents
   - Report a claim (FNOL form)
   - View claim status
2. Broker should NOT see: internal risk scores, agent confidence,
   underwriting notes, other brokers' data, pricing models
3. Test the flow: Login as broker → submit → switch to CUO →
   see it in workbench → approve → switch back to broker → see quote
```

### 3.5 Compliance Dashboard — Bias Monitoring Needs Real Computation

The compliance module has `POST /api/v1/compliance/bias-report` which should generate actual disparate impact analysis using the four-fifths rule. With 1,540 submissions in the DB, there's enough data to compute real bias metrics: approval rates by industry sector, by company size, by territory, and flag any group where the selection rate is below 80% of the highest group's rate.

**Agent Task:**
```
1. Bias report should compute actual metrics from the SQL data:
   - Approval rate by industry SIC code
   - Approval rate by revenue band
   - Approval rate by territory
   - Approval rate by security maturity score band
2. Apply four-fifths rule: flag any subgroup where rate < 80% of highest
3. Display results in the Compliance workbench with:
   - Summary: "3 potential disparate impact findings"
   - Detail: which groups, what rates, what the gap is
   - Recommendation: "Review underwriting guidelines for healthcare sector"
4. This is a concrete EU AI Act Article 9 deliverable — make it real
```

---

## 4. Moderate Gaps

### 4.1 Dashboard — Empty Dynamic Sections

The main dashboard (CUO view) has three sections that show no data:
- "Agent Decisions Today" → "No agent activity data yet"
- "Agent Status" → "0 active, Agent statuses appear after processing"
- "Recent Activity" → "Activity will appear as submissions and claims are processed"

While the KPI cards (1,615 submissions, 572 policies, 124 claims) show real SQL data, these three empty sections are the first thing someone evaluating the platform notices. They undermine the "AI-native" claim immediately.

**Agent Task:**
```
Option A (quick): Populate from existing data
  - "Agent Decisions Today": query compliance/decisions table, count by type
  - "Agent Status": show configured agents with "ready" status
  - "Recent Activity": query recent submissions, policy binds, claims by timestamp

Option B (better): Wire to actual agent activity
  Depends on Priority 1 being complete. Agent processing creates real activity data.
```

### 4.2 Missing Knowledge Graph UI

The knowledge graph has content (guidelines, precedents, compliance rules) accessible via `/api/v1/knowledge/*` endpoints. But there's no way to browse or edit it from the dashboard. The Product Manager persona needs a knowledge graph management interface.

**Agent Task:**
```
1. Add a "Knowledge" page to the dashboard sidebar
2. Show: underwriting guidelines, rating factors, coverage definitions,
   claims precedents, compliance rules — organized by category
3. Allow Product Manager role to edit guidelines (with version tracking)
4. Show which agents reference which knowledge items
```

### 4.3 Escalations Module Needs Dashboard Wiring

The API has a full escalations module (`/api/v1/escalations/*` with count, list, create, approve, reject). The sidebar shows an "Escalations" link. This needs to be a prominent feature — it's where human-agent collaboration happens.

**Agent Task:**
```
1. Escalations page should show pending items with:
   - Source (which agent escalated)
   - Reason (low confidence, above authority, referral trigger)
   - Priority
   - Assigned to
   - Action buttons (Approve / Reject / Reassign)
2. CUO and Senior UW should see escalations relevant to them
3. Count badge on sidebar: "Escalations (3)" when items pending
```

---

## 5. Prioritized Improvement Roadmap (Updated)

### Week 1: Make Agents Real (Priorities 1-2)
1. **Wire Foundry agents to actual workflows** — structured prompts, knowledge retrieval, LLM calls, Decision Records
2. **Populate dashboard dynamic sections** — agent decisions, activity, status from real data
3. **Build UW Workbench detail panel** — risk assessment, rating breakdown, recommendation, action buttons
4. **Fix submission state distribution** — reseed with realistic status mix, not all "quoted"

### Week 2: Make It Demo-Ready (Priority 3 + 3.3)
5. **ProcessWorkflowModal** — visible step-by-step AI reasoning in the dashboard
6. **Agent-processed seed data** — submissions with Decision Records, audit trails, varied outcomes
7. **Rating breakdown** — transparent premium calculation visible in UW workbench and API
8. **Escalations dashboard** — pending items, approve/reject flow

### Week 3: Make It Usable (Priorities 3.4-3.5)
9. **Broker portal end-to-end** — submit, track, receive quote, request bind, report claim
10. **Bias monitoring computation** — real disparate impact analysis from SQL data
11. **Knowledge graph UI** — browse and edit underwriting guidelines from dashboard
12. **Cross-role workflow test** — broker submits → CUO sees in workbench → approves → broker sees quote

### Week 4: Make It Carrier-Ready
13. **Reinsurance cession on bind** — auto-calculate when policy is bound
14. **Actuarial workbench depth** — real triangle generation from claims data
15. **MGA oversight** — bordereaux validation from the dashbaord
16. **Compliance dashboard** — full EU AI Act Article 11 documentation generation

---

## 6. What's Genuinely Good (Don't Break These)

Before the agent team starts making changes, here's what's working well and should be preserved:

- **Foundry client architecture** — `foundry_client.py` is production-quality. The Responses API integration, OpenTelemetry instrumentation, graceful fallback, and consistent response shape are all correct. Build on this, don't replace it.
- **API design** — 22 modules, clean REST patterns, Swagger documentation. The endpoint naming is intuitive and follows insurance domain conventions.
- **Persona login** — the demo mode with named personas is exactly right for showcasing to insurance executives.
- **Security measures** — parameterized SQL, constant-time auth, VNet integration, private endpoints. Don't regress on these.
- **ACORD ingestion** — having a working ACORD 125/126 parser is a genuine differentiator.
- **Seed data quality** — realistic company names, varied industries, multi-year data.
- **Open source hygiene** — AGENTS.md, CONTRIBUTING.md, SECURITY.md, CI/CD, AGPL license.

---

## 7. Summary Verdict

**The gap between v1 and v2 is enormous.** In two weeks the platform went from scaffolding to a functional prototype with real data, 90+ live API endpoints, 24 dashboard pages, ACORD ingestion, Document Intelligence, and security hardening. The Foundry client code proves the AI integration architecture is sound. The breadth is now genuinely competitive with early-stage commercial platforms.

**But the core claim — "AI-native" — remains the single biggest gap.** The Foundry client can call LLMs. The agents have capabilities defined. The Decision Record schema exists. But the wire between "submission arrives" and "LLM reasons over it and produces a decision" is not connected. The seeded data bypasses the agents entirely.

**The single most important thing the agent team should do:** Take one submission — "DigitalEdge Payments" sitting in the UW workbench — and make it flow through the actual Submission Agent → Underwriting Agent → Compliance Agent pipeline, with a real LLM call via Foundry, producing a genuine Decision Record with actual reasoning, that appears in the dashboard's "Agent Decisions Today" section and in the Compliance audit trail.

When that works for one submission, extending it to all submissions is engineering. Without it, OpenInsure is a very well-built traditional insurance system with "AI" in the README.

The foundation is strong. The plumbing is there. The last mile is the hardest — and the most important.
