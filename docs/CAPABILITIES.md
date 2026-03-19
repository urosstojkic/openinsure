# OpenInsure Platform — Functional Capabilities

## Overview

OpenInsure is an open-source, AI-native core insurance platform that fundamentally reimagines how insurance operations work. Built on the Microsoft AI stack (Azure AI Foundry + Azure), it replaces the traditional human-driven, screen-by-screen workflow with an **agent-first architecture** where AI agents handle routine insurance operations end-to-end — from submission intake through underwriting, policy issuance, claims management, and compliance — while humans retain oversight and authority over exceptions, complex decisions, and strategic direction.

Unlike legacy platforms that bolt AI onto existing workflows, or closed-source AI-native competitors, OpenInsure is designed from the ground up so that every insurance process is an agent-callable operation. It is open source (AGPL-3.0), model-agnostic (1,900+ models via Azure AI Foundry), and EU AI Act compliant by design.

OpenInsure targets **Managing General Agents (MGAs)**, **InsurTech startups**, and **small specialty carriers** looking for a modern core system that can process a cyber insurance submission from receipt to bindable quote in under 15 minutes — compared to the industry standard of 2–5 business days.

---

## Platform at a Glance

| Capability | Status | Description |
|---|---|---|
| **Submission Intake** | ✅ Live | Multi-channel intake (email, API, portal, broker) with AI data extraction and automated triage |
| **Underwriting & Pricing** | ✅ Live | AI risk assessment, configurable rating engine, authority management, comparable analysis |
| **Policy Administration** | ✅ Live | Full lifecycle: Quote → Bind → Issue → Endorse → Renew → Cancel |
| **Claims Management** | ✅ Live | FNOL through settlement with severity triage, reserving, fraud detection |
| **Billing & Payments** | ✅ Live | Invoicing, installment plans, commission tracking, agency and direct billing |
| **Compliance (EU AI Act)** | ✅ Live | Immutable decision records, bias monitoring, complete audit trail |
| **Multi-Agent Orchestration** | ✅ Live | End-to-end automated workflows coordinating 8 specialized agents |
| **Role-Based Dashboards** | ✅ Live | 11 role-specific views including workbenches and executive dashboard |
| **Broker Portal** | ✅ Live | External self-service for submissions, quotes, and binding |
| **Knowledge Base** | ✅ Live | Product definitions, underwriting guidelines, regulatory requirements |
| **Cyber Insurance Product** | ✅ Live | Complete SMB Cyber Liability product with 5 coverages |
| **Reinsurance** | ✅ Live | Treaty management, cession calculation, recovery tracking |
| **Actuarial** | ✅ Live | Loss triangles, IBNR estimation, reserve adequacy |
| **MGA Oversight** | ✅ Live | Delegated authority monitoring, bordereaux, performance scoring |
| **Renewal Workflow** | ✅ Live | Automated renewal identification and term generation |
| **Finance Dashboard** | ✅ Live | Premium/claims analytics, cash flow, commissions |
| **Microsoft Foundry AI Pipeline** | ✅ Live | 6 deployed agents with ProcessWorkflowModal visualization, confidence scores, Foundry-first AI judgment |
| **Squad Development Agents** | ✅ Live | 7 specialized development agents with persistent knowledge |
| **3-Year Operations Data** | ✅ Live | 1,384 submissions, 483 policies, 109 claims in Azure SQL |
| **Additional LOBs** | 🔄 Planned | Property, General Liability, Tech E&O |

---

## Insurance Operations

### Submission Intake & Triage

**What it does:** Receives insurance applications through any channel — email with attachments, API integration, the broker portal, or direct entry — and automatically processes them into structured, actionable submissions ready for underwriting.

**How it works:**

1. **Receipt & Classification** — The Submission Agent receives the incoming application and classifies the submission by line of business, urgency, and completeness. Documents are categorized (ACORD forms, loss runs, financial statements, supplemental questionnaires).

2. **Data Extraction** — The Document Agent extracts structured data from submitted documents: applicant details, revenue figures, employee counts, coverage requests, loss history, and cyber-specific risk factors (security controls, prior incidents, industry classification).

3. **Appetite Matching** — The Submission Agent checks the extracted data against the underwriting appetite: Is this within target revenue ($50M cap)? Is the industry acceptable? Does the company meet minimum security control requirements? Applications outside appetite are flagged immediately.

4. **Risk Scoring & Prioritization** — Each submission receives an initial risk score (1–5) based on extracted data, enabling underwriters to focus on the most promising opportunities first. Priority factors include completeness of application, alignment with target profile, and premium potential.

5. **Assignment & Routing** — The Submission Agent assigns the triaged submission to the appropriate underwriter based on authority level, workload, and specialization, or routes directly to automated quoting if within auto-bind parameters.

**Human Oversight Points:**
- Submissions outside risk appetite are flagged for human review before declining
- Incomplete applications are held for follow-up rather than auto-rejected
- High-priority or unusual submissions are routed to senior underwriters

**Processing Time:** Target of **under 15 minutes** from receipt to triaged and ready for underwriting, compared to the industry standard of **2–5 business days** for manual intake.

**Channels Supported:**
| Channel | Description |
|---------|-------------|
| Email | Attachments parsed and extracted automatically |
| API | Direct system-to-system integration |
| Portal | Broker self-service with guided entry |
| Broker | Agent-assisted submission via broker portal |

---

### Underwriting & Pricing

**What it does:** Evaluates the risk profile of each submission, generates a premium quote based on configurable rating factors, and determines whether the quote can be auto-approved or requires human review based on authority levels.

**Risk Assessment Methodology:**

The Underwriting Agent evaluates each submission across multiple dimensions:

1. **Cyber-Specific Risk Scoring** — Assigns a risk score (1–10) based on:
   - Security maturity assessment (most heavily weighted at 30%)
   - Industry classification and inherent cyber risk (20% weight)
   - Revenue and company size (25% weight for revenue, 10% for employees)
   - Prior incident history (15% weight)

2. **Security Control Verification** — Evaluates required controls by tier:
   - **Tier 1 (All applicants):** Multi-factor authentication, endpoint detection & response, regular backups, patch management, email filtering
   - **Tier 2 (Revenue > $5M or > 50 employees):** SIEM/MDR, incident response plan, security awareness training, privileged access management
   - **Tier 3 (Revenue > $25M or PII/PHI > 100K records):** Penetration testing, network segmentation, zero-trust architecture, vendor risk management

3. **Referral Trigger Evaluation** — Eight conditions that require human review:
   - Risk score ≥ 8
   - Any cyber claim in past 3 years
   - Prior ransom payment history
   - Revenue exceeding $25M
   - PCI-DSS non-compliance
   - No MFA deployed
   - Healthcare PHI handling
   - International operations

**Rating Engine:**

The configurable rating engine calculates premiums using:
- **Base rate:** $1.50 per $1,000 of annual revenue
- **Industry multipliers:** Low-risk (0.80×), Standard (1.00×), Elevated (1.40×), High-risk (1.80×)
- **Security maturity adjustments:** Better security posture reduces premium
- **Premium bounds:** Minimum $2,500 — Maximum $500,000

**Industry Risk Classifications:**
| Risk Tier | Industries | Multiplier |
|-----------|-----------|------------|
| Low Risk | Retail, Construction, Agriculture | 0.80× |
| Standard | Technology, Professional Services, Manufacturing | 1.00× |
| Elevated | Healthcare, Education, Communications | 1.40× |
| High Risk | Financial Services, Insurance, Government | 1.80× |

**Authority Management:**

Not all quotes require human approval. The authority model determines who can approve what:

| Authority Level | Max Premium | Max Aggregate | Max Risk Score | Referral Triggers |
|----------------|-------------|---------------|----------------|-------------------|
| **Auto-Bind** | $25,000 | $2,000,000 | ≤ 5 | None allowed |
| **Underwriter Level 1** | $100,000 | $5,000,000 | ≤ 7 | ≤ 1 trigger |
| **Underwriter Level 2** | $250,000 | $10,000,000 | ≤ 9 | Multiple allowed |
| **Underwriting Committee** | $500,000 | $10,000,000 | Any | Full committee review |

**Comparable Analysis:** The Underwriting Agent references historical data and industry benchmarks to provide context for each quote, ensuring pricing consistency and identifying outliers.

---

### Policy Administration

**What it does:** Manages the complete lifecycle of an insurance policy from initial quote through binding, issuance, mid-term changes, renewal, and cancellation.

**Policy Lifecycle:**

```
Quote → Bind → Issue → [Active Policy] → Endorse / Renew / Cancel / Expire
```

| Stage | What Happens | Agent Involvement |
|-------|-------------|-------------------|
| **Quote** | Premium calculated, terms generated, coverage options presented | Underwriting Agent generates; Policy Agent structures |
| **Bind** | Applicant accepts terms, coverage begins, policy number assigned | Policy Agent validates authority, creates binding |
| **Issue** | Policy documents generated, delivered to insured and broker | Policy Agent triggers document generation |
| **Endorse** | Mid-term changes: add/remove coverage, change limits, update information | Policy Agent calculates pro-rata premium adjustment |
| **Renew** | Pre-expiration review, updated rating, renewal offer generated | Underwriting Agent re-assesses; Policy Agent generates renewal |
| **Cancel** | Policy terminated early with pro-rata or short-rate return premium | Policy Agent calculates return premium, triggers billing adjustment |

**Document Generation:** Policies, endorsements, certificates of insurance, and cancellation notices are generated automatically based on standardized templates.

**Automated Renewal Processing:** The system identifies policies approaching expiration, triggers re-underwriting assessment, and generates renewal offers — allowing underwriters to focus on exceptions rather than routine renewals.

---

### Claims Management

**What it does:** Handles the entire claims process from First Notice of Loss (FNOL) through investigation, reserving, settlement, and closure — with AI-assisted triage, fraud detection, and reserve estimation.

**Claims Lifecycle:**

```
FNOL → Investigating → Reserved → Settling → Closed
                                            ↗ Reopened
                                  → Denied
```

**1. First Notice of Loss (FNOL)**
- Claims can be reported through any channel (phone, email, API, portal)
- The Claims Agent extracts structured data from the claim report: loss date, loss type, cause of loss, affected parties, initial damage estimate
- Claim number assigned, acknowledgment sent

**2. Coverage Verification**
- The Claims Agent checks the reported loss against the active policy
- Verifies: Is the policy in force? Is the loss type covered? Do any exclusions apply?
- Identifies applicable coverages and sub-limits

**3. Severity Triage**

The Claims Agent assigns a severity tier that drives handling, reserving, and routing:

| Severity | Description | Indemnity Reserve | Expense Reserve |
|----------|-------------|-------------------|-----------------|
| **Simple** | Straightforward, small-value claims | $25,000 | $10,000 |
| **Moderate** | Some complexity, moderate exposure | $100,000 | $35,000 |
| **Complex** | Multi-party, high value, or legal involvement | $500,000 | $150,000 |
| **Catastrophe** | Major event, policy limits in play | $2,000,000 | $500,000 |

**Cyber Loss Type Severity Baselines:**
| Loss Type | Base Severity (1–10) |
|-----------|---------------------|
| Data Breach | 7.5 |
| Ransomware | 8.0 |
| Social Engineering | 5.5 |
| System Failure | 4.0 |
| Unauthorized Access | 6.5 |
| Denial of Service | 5.0 |

**4. Fraud Detection**

The Claims Agent evaluates six fraud indicators, each with a weighted score:

| Indicator | Weight | Trigger |
|-----------|--------|---------|
| Recent policy inception | 0.15 | Policy bound < 90 days before claim |
| Prior claims frequency | 0.20 | Multiple claims within 12 months |
| Late reporting | 0.10 | Reported > 30 days after loss |
| Inconsistent description | 0.20 | Narrative doesn't match evidence |
| High initial demand | 0.15 | Demand approaches policy limits |
| Immediate litigation | 0.20 | Attorney involvement before investigation |

Claims with elevated fraud scores are flagged for Special Investigation Unit (SIU) review.

**5. Reserving**
- Initial reserves set automatically based on severity tier and comparable claims
- Reserve accuracy improves as investigation progresses
- All reserve changes tracked with confidence scores and reasoning

**6. Settlement & Closure**
- Payments processed against reserves
- Authority chain enforced (adjusters have settlement limits)
- Closure requires documented reason and final accounting
- Claims can be reopened if new information emerges

---

### Billing & Payments

**What it does:** Manages all financial transactions related to insurance policies — premium billing, payment processing, installment plans, commission calculations, and invoice generation.

**Billing Plans Available:**

| Plan | Description | Payment Schedule |
|------|-------------|-----------------|
| **Full Pay** | 100% premium upfront | Single payment at binding |
| **Quarterly** | 4 equal installments | Payments every 3 months |
| **Monthly** | 12 equal installments | Payments every month |
| **Agency Bill** | Billed through the broker | Broker collects, remits net of commission |
| **Direct Bill** | Billed directly to insured | Insured pays carrier directly |

**Invoice Lifecycle:**

```
Draft → Issued → Paid / Overdue / Cancelled / Void
```

**Commission Tracking:**
- Broker commissions calculated as percentage of premium
- Commission amounts associated with specific policies
- Paid/unpaid status tracked with payment dates
- Supports bordereaux-style reporting

**Key Billing Features:**
- Automatic installment schedule generation at policy binding
- Balance tracking: `Balance Due = Total Premium - Sum(Paid Amounts)`
- Invoice generation with itemized line items
- Overdue payment detection and follow-up triggers
- Pro-rata adjustments for mid-term endorsements and cancellations

---

### Reinsurance Management [Carrier]

**What it does:** Manages the full reinsurance lifecycle — from treaty setup through automatic cession on policy bind and recovery calculation on claim payments — giving carriers real-time visibility into ceded risk and capacity utilization.

**Treaty Types Supported:**

| Type | Description |
|------|-------------|
| **Quota Share** | Fixed percentage of every policy ceded to reinsurer |
| **Excess-of-Loss** | Reinsurer covers losses above a retention threshold |
| **Surplus** | Cession of amounts exceeding the carrier's net line |
| **Facultative** | Individual risk placement for large or unusual exposures |

**Key Capabilities:**

- **Treaty Lifecycle Management** — Create, activate, and expire treaties with defined terms, limits, and retention levels
- **Automatic Cession Calculation** — When a policy is bound, cessions are calculated automatically based on active treaties
- **Capacity Utilization Tracking** — Real-time monitoring of treaty utilization with configurable alerts at 80% and 95% thresholds
- **Recovery Calculation** — When claims are paid, reinsurance recoveries are calculated automatically against applicable treaties
- **Bordereau Generation** — Produce premium and claims bordereaux for reporting to reinsurers
- **Reinsurance Dashboard** — Treaty summary view with utilization bars, cession history, and recovery tracking

---

### Actuarial Analytics [Carrier]

**What it does:** Provides actuarial analysis tools for reserving, loss development, and rate adequacy — enabling actuaries to assess reserve sufficiency and pricing accuracy using data from the platform's claims and policy records.

**Key Capabilities:**

- **Loss Development Triangle Generation** — Builds incurred loss development triangles from claims data, organized by accident year and development period
- **IBNR Estimation** — Calculates Incurred But Not Reported reserves using the chain-ladder (link ratio) method with age-to-age factors
- **Reserve Adequacy Analysis** — Compares carried reserves against indicated reserves by line of business and accident year, flagging under- or over-reserved positions
- **Rate Adequacy Testing** — Compares current premium rates against actuarially indicated rates, highlighting lines where pricing may be insufficient
- **Actuarial Workbench** — Interactive dashboard with development triangles, IBNR charts, and reserve adequacy visualizations

**Methodology:**
- Chain-ladder method with weighted age-to-age factors
- Tail factor application for immature accident years
- Results segmented by line of business and accident year

---

### MGA Oversight [Carrier]

**What it does:** Enables carriers to monitor and manage Managing General Agents operating under delegated authority — tracking authority utilization, validating bordereaux submissions, and scoring MGA performance.

**Key Capabilities:**

- **Delegated Authority Management** — Define and monitor authority grants with premium limits, coverage restrictions, and territory constraints
- **Bordereaux Ingestion & Validation** — Receive and validate premium and claims bordereaux from MGAs, flagging data quality issues
- **Authority Utilization Tracking** — Real-time monitoring of how much of each MGA's granted authority has been used
- **Performance Scoring** — Composite scoring based on loss ratio, premium volume, compliance, and data quality
- **Audit Trail** — Complete history of authority changes, bordereaux submissions, and compliance events
- **MGA Oversight Dashboard** — Scorecards with performance metrics, utilization gauges, and compliance status for each MGA

---

### Renewal Management

**What it does:** Identifies policies approaching expiration and automates the renewal workflow — from early identification through term generation to renewal processing.

**Key Capabilities:**

- **90/60/30-Day Renewal Identification** — Automatically surfaces policies at 90, 60, and 30 days before expiration, categorized by urgency
- **Automated Renewal Term Generation** — Generates renewal terms based on current policy, updated risk assessment, and rate changes
- **Renewal Processing** — Supports both auto-renewal (for low-risk, no-change renewals) and manual review workflows
- **Renewal Queue** — Prioritized view of upcoming renewals with days-to-expiry, premium, and recommended action

---

### Financial Reporting

**What it does:** Provides financial analytics and reporting across the insurance portfolio — covering premium flows, claims costs, cash management, and commission reconciliation.

**Key Capabilities:**

- **Premium Analytics** — Written, earned, and unearned premium tracking with period-over-period trends
- **Claims Analytics** — Paid losses, outstanding reserves, and incurred losses with loss ratio calculation
- **Cash Flow Management** — Net cash position tracking, premium collections vs. claims payments, forecasting
- **Commission Tracking & Reconciliation** — Broker commission calculation, payment status, and reconciliation reporting
- **Finance Dashboard** — Consolidated financial summary with KPI cards, trend charts, and drill-down capability

---

### The Agents

OpenInsure deploys **8 specialized AI agents**, each responsible for a distinct insurance function. These agents are hosted on **Azure AI Foundry Agent Service** and operate as a coordinated team, not isolated tools.

| Agent | Role | Key Capabilities |
|-------|------|-----------------|
| **Submission Agent** | Intake specialist | Receives applications, classifies documents, extracts data, scores and prioritizes, assigns to underwriters |
| **Underwriting Agent** | Risk assessor & pricer | Evaluates risk, checks security controls, calculates premiums, generates quotes, manages authority levels |
| **Policy Agent** | Policy lifecycle manager | Binds policies, issues documents, processes endorsements, manages renewals, handles cancellations |
| **Claims Agent** | Claims handler | Processes FNOL, verifies coverage, triages severity, detects fraud indicators, sets reserves, manages settlements |
| **Compliance Agent** | Regulatory guardian | Audits every decision, validates decision records, monitors for bias, checks regulatory requirements |
| **Document Agent** | Document processor | Classifies documents (ACORD, loss runs, financial statements), extracts structured data via OCR, generates metadata |
| **Knowledge Agent** | Information retrieval | Queries the knowledge base for underwriting rules, product definitions, regulatory requirements, and comparable data |
| **Orchestrator** | Workflow coordinator | Coordinates multi-step workflows, routes tasks between agents, collects decision records, manages escalations |

### How Multi-Agent Workflows Operate

**Example: New Business Submission to Binding**

Here is what happens when a broker submits a cyber insurance application:

1. **Orchestrator** receives the submission request and initiates the "new_business" workflow

2. **Submission Agent** takes over:
   - Classifies the incoming documents (ACORD application, loss runs, supplemental questionnaire)
   - Extracts applicant data: company name, revenue ($8M), employees (45), industry (professional services)
   - Extracts cyber-specific data: MFA deployed ✅, EDR in place ✅, backups ✅, no prior incidents
   - Assigns priority: 2/5 (strong fit for appetite)
   - Logs a Decision Record for the triage

3. **Knowledge Agent** is consulted:
   - Retrieves the Cyber SMB product definition
   - Pulls underwriting guidelines for professional services
   - Identifies applicable security control requirements (Tier 2)

4. **Underwriting Agent** assesses the risk:
   - Risk score: 4/10 (low risk — good security posture, no claims history)
   - Industry multiplier: 1.00× (standard for professional services)
   - Calculates premium: ~$12,000 for $1M limit package
   - Checks authority: Premium $12K < $25K auto-bind threshold, risk score 4 ≤ 5, no referral triggers
   - **Result: Auto-bind eligible** — no human review needed
   - Logs Decision Record with full reasoning chain

5. **Policy Agent** binds the policy:
   - Creates policy with 5 coverages and agreed terms
   - Generates policy number
   - Triggers document generation
   - Logs Decision Record

6. **Compliance Agent** audits the workflow:
   - Validates all Decision Records from steps 2–5
   - Checks for bias indicators
   - Confirms audit trail completeness
   - Logs compliance check Decision Record

7. **Orchestrator** returns the complete `WorkflowResult` with all Decision Records

**Total elapsed time: ~3 minutes** vs. industry standard of 2–5 business days.

### Human-Agent Authority Model

Not every decision is made automatically. OpenInsure uses a **complexity × consequence matrix** to determine when agents can act autonomously and when human oversight is required:

| Scenario | Agent Action | Human Action |
|----------|-------------|-------------|
| Low-risk submission within appetite, premium < $25K | Agent auto-binds | None required (auditable after the fact) |
| Medium risk, premium $25K–$100K | Agent generates quote with recommendation | Underwriter reviews and approves/modifies |
| High risk or referral triggers present | Agent prepares analysis and flags concerns | Senior underwriter or committee decides |
| Confidence score < 70% on any decision | Agent escalates with reasoning | Human makes the decision with agent's analysis |
| Claim with elevated fraud score | Agent flags indicators | SIU investigates before proceeding |
| Compliance issue detected | Agent blocks action | Compliance officer reviews and resolves |

**Key Principle:** Agents handle the routine so humans can focus on what requires judgment, experience, and relationship management.

---

## Compliance & Governance

### EU AI Act Compliance by Design

OpenInsure is built to comply with the **EU AI Act** from day one, not as an afterthought. The platform implements requirements from several key articles:

**Article 9 — Risk Management:**
- Continuous bias monitoring using the 4/5ths (80%) rule for disparate impact detection
- Systematic risk assessment of all AI-driven decisions
- Documented risk mitigation measures

**Article 12 — Record-Keeping:**
- Every AI agent decision produces an **immutable Decision Record** containing:
  - Decision ID, timestamp, agent ID, agent version
  - Model used and model version
  - Decision type and confidence score
  - Input summary (anonymized for privacy)
  - Full reasoning chain (chain-of-thought)
  - Data sources consulted
  - Knowledge base queries executed
  - Fairness metrics (disparate impact data)
  - Human oversight: whether it was required, why, and whether the human overrode the AI
  - Execution time

**Article 14 — Human Oversight:**
- Human oversight built into every critical decision point
- Authority levels that enforce human review above thresholds
- Override capability: humans can always override AI recommendations
- Override tracking: when a human overrides an AI decision, the override and its reasoning are logged

### Bias Monitoring

The Compliance Agent continuously monitors AI decisions for discriminatory patterns:

- **Method:** 4/5ths (80%) Rule — calculates the favorable-outcome rate for each demographic group and compares to the reference group
- **Threshold:** If any group's favorable rate is less than 80% of the reference group rate, a disparate impact flag is raised
- **Output:** Bias Reports with flagged metrics, observed vs. expected rates, and recommended corrective actions
- **Frequency:** Available on-demand via the Compliance Workbench and the `POST /api/v1/compliance/bias-report` endpoint

### Audit Trail

An append-only, immutable event log captures every significant action in the system:

- **Who:** User ID or Agent ID that performed the action
- **What:** The specific action taken (create, update, approve, decline, escalate)
- **On What:** The resource affected (submission, policy, claim, billing account)
- **When:** UTC timestamp
- **Correlation:** Links related events across a workflow via correlation IDs

This audit trail satisfies not only EU AI Act requirements but also standard insurance regulatory audit expectations.

---

## Role-Based Access

### User Roles

OpenInsure supports **11 active dashboard roles** (from a total of 19 platform roles that include carrier-specific and external roles):

| Role | Default View | Key Responsibilities |
|------|-------------|---------------------|
| **CEO** | Executive Dashboard | Portfolio overview, KPI monitoring, strategic decisions |
| **CUO** (Chief Underwriting Officer) | Main Dashboard | Underwriting oversight, authority management, portfolio quality |
| **Senior Underwriter** | Underwriting Workbench | Complex risk assessment, referral review, quote approval |
| **Underwriting Analyst** | Underwriting Workbench | Submission analysis, data gathering, preliminary assessment |
| **Claims Manager** | Claims Workbench | Claims oversight, reserve approval, settlement authority |
| **Claims Adjuster** | Claims Workbench | Claim investigation, evidence gathering, payment processing |
| **CFO** | Executive Dashboard | Financial oversight, premium tracking, loss ratios |
| **Compliance Officer** | Compliance Workbench | AI decision audit, bias review, regulatory reporting |
| **Product Manager** | Main Dashboard | Product configuration, coverage management, pricing strategy |
| **Operations** | Main Dashboard | System health, workflow monitoring, SLA tracking |
| **Broker** (External) | Broker Portal | Submit applications, view quotes, bind policies |

### Authority Delegation Model

Authority is delegated based on role and can be configured per deployment:

- **Auto-Bind Authority:** Low-risk, low-value transactions processed without human approval
- **Individual Authority:** Each role has defined limits for what they can approve independently
- **Escalation Paths:** When a decision exceeds an individual's authority, it escalates to the next level
- **Committee Authority:** Highest-value or highest-complexity decisions require committee approval

### Carrier vs. MGA Deployment Modes

OpenInsure can be deployed in two modes with different role availability:

| Mode | Available Roles | Key Difference |
|------|----------------|----------------|
| **Carrier** | All 19 roles | Includes actuarial, reinsurance, delegated authority management |
| **MGA** | 12 roles | Focused on underwriting, claims, and operations within delegated authority |

---

## Dashboard & User Experience

### Role-Specific Views

Each user sees a tailored interface based on their role. The dashboard is a React + TypeScript application with role-aware navigation, data filtering, and action permissions.

#### Executive Dashboard
**Available to:** CEO, CUO, CFO

The executive view provides a high-level overview of the business:
- **Key Performance Indicators:** Gross Written Premium, Loss Ratio, Combined Ratio, Policy Count
- **Premium Trends:** Monthly and quarterly premium volume with growth indicators
- **Portfolio Health:** Distribution by line of business, geography, and risk tier
- **Agent Impact Metrics:** How much work AI agents are handling vs. humans, processing time improvements
- **Claims Overview:** Open claims count, total reserves, average time-to-close

#### Underwriting Workbench
**Available to:** CUO, Senior Underwriter, UW Analyst

The underwriting workbench is where underwriters spend most of their time:
- **Submission Queue:** Prioritized list of submissions awaiting review, sorted by risk score and age
- **Agent Analysis Panel:** For each submission, the AI's risk assessment with full reasoning chain, confidence scores, and comparable analysis
- **Decision Panel:** Accept, modify, or decline with structured reasoning fields
- **Authority Indicators:** Clear visual showing whether a decision is within the user's authority or requires escalation
- **Knowledge Context:** Relevant underwriting guidelines, product rules, and regulatory requirements surfaced automatically

#### Claims Workbench
**Available to:** Claims Manager, Claims Adjuster

Purpose-built for efficient claims handling:
- **Claims Queue:** Active claims sorted by severity, age, and next-action-due
- **Claim Detail View:** Complete claim information with timeline of events, documents, and communications
- **Reserve Management:** View and adjust reserves with confidence indicators from the Claims Agent
- **Fraud Indicators:** Visual flagging of suspicious patterns detected by the Claims Agent
- **Payment Processing:** Record payments, track against reserves, manage settlement workflow
- **Timeline View:** Chronological history of all actions, decisions, and communications on a claim

#### Compliance Workbench
**Available to:** Compliance Officer, CUO, CEO

The compliance view provides regulatory oversight:
- **AI System Inventory:** Complete registry of all AI models in use, their versions, and purposes (EU AI Act requirement)
- **Decision Record Browser:** Search and review any AI decision with full reasoning chain
- **Bias Monitoring Dashboard:** Current and historical bias metrics with 4/5ths rule status
- **Audit Trail Viewer:** Searchable, filterable log of all system actions
- **Regulatory Reports:** Generate on-demand compliance reports

#### Broker Portal
**Available to:** Broker (external role)

A self-service interface for brokers with strict data isolation:
- **Submit Applications:** Guided submission flow with real-time validation
- **Track Submissions:** View status of submitted applications
- **Review Quotes:** See generated quotes with coverage details and pricing
- **Bind Policies:** Accept quotes and trigger binding within authority
- **View Policies:** Access policy details, documents, and endorsements for their clients
- **No Internal Data Exposed:** Brokers see only their own clients and submissions

#### Additional Views
- **Submissions List & Detail:** Browse, search, and manage all submissions with status tracking
- **Policies List & Detail:** Policy portfolio view with filtering by status, line of business, expiration date
- **Claims List & Detail:** Claims register with severity and status indicators
- **Agent Decisions View:** Browse all AI decision records with reasoning and confidence scores
- **New Submission / New Policy / New Claim Forms:** Structured data entry with validation

---

## Microsoft Foundry AI Pipeline

### Foundry-First Architecture

OpenInsure follows a **Foundry-first principle**: all AI judgment flows through Microsoft Foundry agents. Local fallback logic exists only for resilience — Foundry is the authoritative decision engine.

### Deployed Agents

| Agent | Role | Key Outputs |
|-------|------|-------------|
| **Submission Agent** | Intake, classification, extraction, triage | Risk score, priority assignment, appetite match |
| **Underwriting Agent** | Risk assessment, pricing, authority check | Quote, bind/decline recommendation, confidence score |
| **Policy Agent** | Bind, issue, endorse, renew, cancel | Policy lifecycle actions, decision records |
| **Claims Agent** | FNOL, coverage verification, reserving, fraud detection | Severity triage, reserve setting, fraud flags |
| **Compliance Agent** | Decision audit, bias analysis, regulatory checking | Pass/fail, bias alerts, audit entries |
| **Orchestrator** | Multi-step workflow coordination | Workflow routing, escalation, decision record collection |

### ProcessWorkflowModal

The dashboard includes a **ProcessWorkflowModal** component that visualizes the Foundry AI pipeline in real time:

- **Step-by-step AI reasoning:** Each agent's contribution is shown as a discrete step with inputs, outputs, and rationale
- **Confidence scores:** Every decision displays its confidence level, with automatic escalation below 0.7
- **Pipeline progression:** Visual progress through the multi-agent workflow (e.g., Submission → Underwriting → Policy)
- **Decision records:** Each step produces an immutable EU AI Act–compliant decision record

Process buttons on the Submissions and Claims pages trigger Foundry pipelines and open the modal to show real-time agent reasoning.

### Squad Development Agents

OpenInsure is developed with the assistance of **7 specialized Squad agents** that maintain persistent knowledge of the codebase, architecture, and domain:

- Agents cover backend, frontend, infrastructure, testing, documentation, compliance, and orchestration
- Each agent retains context across sessions for consistent, high-quality contributions

---

## Deployment

### Production Environment

OpenInsure can be deployed to any Azure subscription. See [Deployment Guide](deployment/azure-setup.md) for instructions.

After deployment, your instance will be available at:

| Component | URL |
|-----------|-----|
| **Dashboard** | `https://<your-dashboard>.azurecontainerapps.io` |
| **Backend API** | `https://<your-backend>.azurecontainerapps.io` |
| **API Documentation (Swagger)** | `https://<your-backend>.azurecontainerapps.io/docs` |
| **AI Foundry Agents** | [Microsoft Foundry portal](https://ai.azure.com) — your configured project |

### Azure Infrastructure

The platform runs on **13+ Azure resources**, all defined as Infrastructure-as-Code using Bicep:

| Resource | Service | Purpose |
|----------|---------|---------|
| Container Apps | Azure Container Apps | Hosts backend API and dashboard containers |
| SQL Database | Azure SQL | Transactional data — 1,384 submissions, 483 policies, 109 claims (3+ years of operations) |
| Cosmos DB | Azure Cosmos DB (NoSQL) | Knowledge graph, decision records |
| AI Search | Azure AI Search | Hybrid vector + keyword search for knowledge retrieval |
| Blob Storage | Azure Storage | Document storage (policies, claims evidence, applications) |
| Service Bus | Azure Service Bus | Event-driven workflow messaging (FIFO queues) |
| Event Grid | Azure Event Grid | Event routing and webhook delivery |
| AI Foundry | Azure AI Foundry | Agent hosting, model access (GPT-5.1, 1,900+ models) |
| Log Analytics | Azure Monitor | Observability, diagnostics, performance monitoring |
| Application Insights | Azure Monitor | Application performance monitoring |
| Managed Identity | Azure Managed Identity | Passwordless service-to-service authentication |
| Key Vault | Azure Key Vault | Secrets management (no hardcoded credentials) |
| Entra ID | Microsoft Entra ID | Identity and access management |

### Security Model

- **Zero passwords:** All service-to-service communication uses Managed Identity
- **Entra-only authentication:** Azure SQL configured for Entra-only login (no SQL auth)
- **TLS 1.2+** for all connections
- **Key Vault** for any secrets that cannot use Managed Identity
- **Network isolation:** Virtual network with private endpoints in production

### Infrastructure-as-Code

All infrastructure is defined in **Bicep templates** under `infra/`, enabling:
- Repeatable deployments across environments (dev, staging, production)
- Version-controlled infrastructure changes
- Automated provisioning via `az deployment group create`

---

## Cyber Insurance — Phase 1 Line of Business

### Product: Cyber Liability for Small & Medium Business

**Product Code:** CYBER-SMB-001
**Target Market:** US small and medium businesses with annual revenue under $50M
**Territories:** All US states (NY and CA require additional filings)

### Coverages

OpenInsure's cyber product includes five coverages that can be individually configured:

| Coverage | Code | Description | Default Limit | Limit Range | Default Deductible |
|----------|------|-------------|---------------|-------------|-------------------|
| **First-Party Breach Response** | BREACH-RESP | Costs of responding to a data breach: forensics, notification, credit monitoring, PR | $1,000,000 | $100K–$5M | $10,000 |
| **Third-Party Liability** | THIRD-PARTY | Claims from affected third parties: lawsuits, settlements, judgments | $1,000,000 | $250K–$10M | $25,000 |
| **Regulatory Defense & Penalties** | REG-DEFENSE | Costs of regulatory investigations, defense, and assessed penalties | $500,000 | $100K–$2M | $10,000 |
| **Business Interruption** | BUS-INTERRUPT | Lost income and extra expenses during system recovery | $500,000 | $50K–$2M | $25,000 |
| **Ransomware & Extortion** | RANSOMWARE | Ransom payments (where legal), negotiation costs, recovery expenses | $500,000 | $100K–$2M | $10,000 |

### Rating Factors

Premium is calculated based on five weighted factors:

| Factor | Weight | Description |
|--------|--------|-------------|
| **Security Maturity Score** | 30% | Overall security posture assessment (most important factor) |
| **Annual Revenue** | 25% | Company revenue as a proxy for exposure |
| **Industry (SIC Code)** | 20% | Industry-specific cyber risk level |
| **Prior Incidents** | 15% | Claims and incident history |
| **Employee Count** | 10% | Number of employees as a risk indicator |

**Base Rate:** $1.50 per $1,000 of annual revenue
**Premium Range:** $2,500 minimum — $500,000 maximum

### Exclusions

Four standard exclusions apply to all cyber policies:

1. **War & State-Sponsored Attacks** — Acts of war, terrorism, or nation-state cyber operations
2. **Known Unpatched Vulnerabilities** — Losses from vulnerabilities left unpatched 90+ days after notification
3. **Insider Fraud** — Deliberate fraudulent acts by directors and officers
4. **Infrastructure Failures** — Failures of internet backbone, power grid, or telecommunications infrastructure

### Declined Risks

The following classes are outside appetite and will be auto-declined:
- Cryptocurrency exchanges
- Adult content platforms
- Critical infrastructure operators
- Online gambling operations

---

## Roadmap

### Completed (Phases 1–4)

- ✅ Core domain model: Party, Submission, Policy, Claim, Product, Billing
- ✅ Complete REST API with 35+ endpoints
- ✅ 8 AI agents with decision record logging
- ✅ Azure infrastructure (9 Bicep modules)
- ✅ Knowledge base: cyber product definition, underwriting guidelines, regulatory requirements
- ✅ EU AI Act compliance: decision records, audit trail, bias monitoring
- ✅ Role-based access control with 19 platform roles
- ✅ React dashboard with 11 role-specific views
- ✅ Broker portal for external self-service
- ✅ Multi-agent orchestration workflows
- ✅ Cyber Liability SMB product (CYBER-SMB-001)
- ✅ MCP Server interface for AI tool integration
- ✅ CI/CD pipeline: lint, type check, security scan, 375 tests, build
- ✅ Reinsurance management (treaty lifecycle, cession, recovery, bordereau)
- ✅ Actuarial analytics (loss triangles, IBNR, reserve adequacy, rate adequacy)
- ✅ MGA oversight (delegated authority, bordereaux, performance scoring)
- ✅ Renewal workflow (90/60/30-day identification, automated term generation)
- ✅ Financial reporting (premium/claims analytics, cash flow, commissions)

### In Progress

- 🔄 Document intelligence with OCR extraction
- 🔄 M365 Copilot publishing for Teams integration

### Planned (Phase 5+)

- 📋 **Additional Lines of Business:** Property, General Liability, Technology E&O
- 📋 **Portfolio Analytics:** Concentration risk alerts, geographic exposure mapping, limit adequacy
- 📋 **Advanced Document Processing:** Vector embeddings for document similarity and retrieval
- 📋 **M365 Copilot Native App:** Insurance operations directly within Microsoft Teams
- 📋 **Policyholder Self-Service Portal:** Claims reporting, document access, payment management
- 📋 **Integration Hub:** ACORD messaging, third-party data providers, payment gateways

---

## API Quick Reference

### Endpoints Summary

| Module | Endpoints | Description |
|--------|-----------|-------------|
| **Submissions** | 8 endpoints | Create, list, get, update, triage, quote, bind, upload documents |
| **Policies** | 8 endpoints | Create, list, get, update, endorse, renew, cancel, list documents |
| **Claims** | 8 endpoints | Create (FNOL), list, get, update, set reserves, record payment, close, reopen |
| **Products** | 6 endpoints | Create, list, get, update, rate submission, list coverages |
| **Billing** | 5 endpoints | Create account, get account, record payment, list invoices, issue invoice |
| **Compliance** | 5 endpoints | List decisions, get decision, audit trail, bias report, system inventory |
| **Health** | 3 endpoints | Root, health check, readiness probe |

**API Documentation:** Available at `/docs` (Swagger UI) and `/redoc` (ReDoc) on any running instance.

**Authentication:** All API endpoints (except health checks) require authentication via API key with role-based authorization.

---

## Technology Summary

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Backend** | Python 3.12+ / FastAPI / Pydantic v2 | API server with strong typing and validation |
| **AI Platform** | Azure AI Foundry (Agent Service, Models) | Agent hosting, model access (GPT-5.1 + 1,900 models) |
| **Dashboard** | React 18 + TypeScript + Vite | Role-based web interface |
| **Database** | Azure SQL + Azure Cosmos DB | Transactional data + knowledge graph / decision records |
| **Search** | Azure AI Search | Hybrid vector + keyword search |
| **Storage** | Azure Blob Storage | Document and file storage |
| **Events** | Azure Service Bus + Event Grid | Async messaging and event routing |
| **Identity** | Microsoft Entra ID | Authentication and authorization |
| **IaC** | Bicep | Infrastructure-as-Code |
| **CI/CD** | GitHub Actions | Automated testing, scanning, and deployment |
| **License** | AGPL-3.0 | Open source with copyleft |

---

*This document describes OpenInsure v0.4.0. For technical architecture details, see [Architecture Overview](architecture/overview.md). For API specifications, see [API Documentation](api/). For deployment instructions, see [Azure Setup](deployment/azure-setup.md).*
