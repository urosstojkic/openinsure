# OpenInsure: Operating Model & Organizational Design Specification

## For AI Agent Implementation Teams

**Document Type:** Platform specification — personas, permissions, workflows, authority model
**Version:** 0.2
**Depends on:** openinsure-architecture-spec-v01.md
**Purpose:** Define every human and system actor, what they can see, what they can do, and how human-agent collaboration works across all insurance operations
**Architecture Decision:** Carrier-first design, MGA-deployable as proper subset

---

## 1. The AI-Native Operating Model Shift

### 1.1 Platform Scope: Carrier-First, MGA-Deployable

OpenInsure is designed for insurance carriers as the primary deployment target. The platform's data model, module boundaries, and organizational model accommodate carrier-level complexity from day one: multi-LOB operations, actuarial functions, reinsurance management, delegated authority oversight, statutory reporting, and enterprise-scale organizational hierarchies.

MGAs can deploy the same platform with a reduced module set. Because a carrier's insurance transaction lifecycle (submission → underwriting → policy → claims → billing) is a superset of an MGA's operations, an MGA deployment is architecturally a carrier deployment with certain modules disabled or unused. This means:

- The data schema includes carrier-specific entities (ReinsuranceContract, ActuarialReserve, BusinessUnit, DelegatedAuthority) from the beginning, even if empty in MGA deployments
- The RBAC system supports hierarchical authority structures, used flat by MGAs and hierarchically by carriers
- Carrier-specific personas (Chief Actuary, Reinsurance Manager, MGA Oversight Manager) exist in the platform but are simply not provisioned in MGA deployments
- Configuration profiles (Section 8.2) select the appropriate module set per deployment type

This carrier-first approach avoids the risk of building an MGA platform that requires painful refactoring to support carrier requirements later. The marginal cost of including carrier-capable schema from the start is low; the cost of retrofitting carrier complexity onto an MGA-scoped platform is high.

### 1.2 Traditional vs. AI-Native: Carrier Operating Model

A traditional mid-size P&C carrier with $500M GWP typically employs 300-600 people:

```
Traditional Carrier (~450 people for $500M GWP)
├── CEO (1)
├── Chief Underwriting Officer (1)
│   ├── LOB Heads (3-5) — e.g., Property, Casualty, Cyber, Professional Lines
│   │   ├── Senior Underwriters (3-5 per LOB)
│   │   ├── Underwriters (5-10 per LOB)
│   │   └── UW Assistants / Analysts (3-5 per LOB)
│   └── Underwriting Operations (10-15) — submissions processing, data entry
├── Chief Actuary (1)
│   ├── Reserving Actuaries (3-5)
│   ├── Pricing Actuaries (3-5)
│   └── Actuarial Analysts (5-8)
├── Chief Claims Officer (1)
│   ├── Claims Managers by LOB (3-5)
│   │   ├── Senior Adjusters (3-5 per LOB)
│   │   └── Adjusters (5-15 per LOB)
│   ├── Subrogation / Recovery (3-5)
│   └── Claims Operations (5-10)
├── CFO (1)
│   ├── Controller / Accounting (8-15)
│   ├── Reinsurance Team (3-8)
│   ├── Investment Management (2-5 or outsourced)
│   └── Financial Planning & Analysis (3-5)
├── Chief Risk / Compliance Officer (1)
│   ├── Compliance Team (3-8)
│   ├── Internal Audit (2-5)
│   └── Enterprise Risk (2-4)
├── CTO / CIO (1)
│   ├── IT Operations (15-30)
│   ├── Application Development (10-20)
│   └── Data & Analytics (5-10)
├── Distribution / Marketing (10-20)
├── Delegated Authority Management (3-8) — MGA oversight
├── Legal (3-8)
└── HR / Admin (10-20)
```

An AI-native carrier targets the same $500M GWP with 60-120 people — roughly a 4:1 compression versus traditional, not 4:1 elimination. The humans who remain have fundamentally different jobs:

```
AI-Native Carrier (~90 people for $500M GWP)
├── CEO (1)
├── Chief Underwriting Officer (1)
│   ├── LOB Heads (3-5) — strategy, appetite, exceptions, relationships
│   │   ├── Senior Underwriters (1-3 per LOB) — complex risks, agent oversight
│   │   └── [UW Agents handle intake, triage, standard pricing, renewals, documentation]
│   └── [UW Operations Agents replace manual submissions processing entirely]
├── Chief Actuary (1)
│   ├── Reserving Actuary (1-2) — review agent-produced reserves, set IBNR
│   ├── Pricing Actuary (1-2) — model development, agent rating algorithm oversight
│   └── [Actuarial Agents handle data compilation, triangle generation, routine analysis]
├── Chief Claims Officer (1)
│   ├── Claims Managers (2-3) — complex/litigated claims, fraud, strategy
│   │   ├── Senior Adjusters (2-3) — complex investigations, large settlements
│   │   └── [Claims Agents handle FNOL, routine reserves, simple settlements, correspondence]
│   └── [Subrogation Agent identifies and pursues recovery opportunities]
├── CFO (1)
│   ├── Controller (1) + Accountant (1-2)
│   │   └── [Finance Agents handle reconciliation, reporting, routine journal entries]
│   ├── Reinsurance Manager (1-2)
│   │   └── [Reinsurance Agent handles cession tracking, bordereau generation, recoveries]
│   └── [Investment integration via external managers + data feeds]
├── Chief Risk / Compliance Officer (1)
│   ├── Compliance Lead (1-2)
│   │   └── [Compliance Agents handle monitoring, audit trails, bias analysis, reporting]
│   └── [Internal Audit substantially automated — agent decision sampling + analysis]
├── Head of Product & Data (1)
│   ├── Product Managers (2-3) — knowledge graph, agent tuning, product design
│   └── Platform Engineers (3-5) — system operations, integrations, development
├── Delegated Authority Manager (1-2)
│   └── [MGA Oversight Agent monitors bordereaux, authority utilization, compliance]
├── Distribution Lead (2-4) — broker/agent relationships, market development
└── Legal (1-2) — complex coverage disputes, regulatory matters
```

The pattern: every function that was primarily about processing volume (underwriting operations, claims adjusting for routine claims, accounting reconciliation, data compilation for actuaries) is handled by agents. Every function that requires judgment, relationships, creativity, or regulatory accountability remains human — but the human is working with agent-prepared materials, not raw data.

### 1.3 Traditional vs. AI-Native: MGA Operating Model

An MGA is a proper subset of the carrier operating model. The key differences:

- No actuarial department (carrier provides actuarial oversight; MGA may have consultant)
- No reinsurance management (carrier handles)
- No investment management
- No MGA oversight function (the MGA *is* the delegated entity, not the overseer)
- Lighter regulatory reporting (carrier bears primary regulatory responsibility)
- Simpler organizational hierarchy (flat, single-LOB or few-LOB)

```
AI-Native MGA (~12 people for $50M GWP)
├── CEO / Managing Director (1)
├── Head of Underwriting (1)
│   ├── Senior Underwriter(s) (1-2) — exceptions, complex risks, authority decisions
│   └── [Underwriting Agents handle intake, triage, standard pricing, documentation]
├── Head of Claims (1)
│   └── [Claims Agents handle FNOL, initial reserves, routine settlements]
├── Finance Lead (1)
│   └── [Billing/Finance Agents handle invoicing, reconciliation, bordereaux]
├── Compliance & Legal (1)
│   └── [Compliance Agents handle monitoring, audit trails, reporting]
├── Head of Product & Data (1) — knowledge graph, agent configuration, product rules
├── Distribution Lead (1-2) — broker relationships, market development
├── Operations Lead (1) — platform admin, agent performance, escalation management
└── Platform Engineer (1-2) — maintains and extends OpenInsure deployment
```

The platform accommodates both by using the same codebase with deployment profiles that enable/disable modules and personas.

### 1.4 The Human-Agent Authority Model

Every action in insurance can be classified on two dimensions:

**Complexity:** How much judgment does this require?
- Routine: follows clear rules, deterministic outcome
- Standard: follows guidelines with some interpretation
- Complex: requires expert judgment, multiple factors, ambiguity
- Novel: no precedent, requires creative risk assessment

**Consequence:** How much is at stake if the decision is wrong?
- Low: easily reversible, minimal financial impact
- Medium: moderate financial or compliance impact
- High: significant financial, legal, or regulatory impact
- Critical: catastrophic to the organization

These two dimensions determine the authority model:

| | Low Consequence | Medium Consequence | High Consequence | Critical |
|---|---|---|---|---|
| **Routine** | Agent auto-executes | Agent auto-executes, logs | Agent executes, human notified | Agent prepares, human approves |
| **Standard** | Agent auto-executes | Agent recommends, human confirms | Agent recommends, human approves | Human decides, agent assists |
| **Complex** | Agent recommends, human confirms | Agent recommends, human approves | Human decides, agent assists | Human decides, agent assists, peer review |
| **Novel** | Agent researches, human decides | Human decides, agent assists | Human decides, agent assists, CUO approval | Board/committee decision |

This matrix is configurable per deployment. A startup MGA may give agents broader auto-execute authority; a large carrier with conservative governance may require human approval on most actions. The platform supports both extremes through configuration.

---

## 2. Persona Definitions

Each persona represents a distinct access profile, authority level, and set of agent interactions. These translate directly into Entra ID roles, UI views, and agent behavior configuration.

Personas are tagged as:
- **[CARRIER]** — exists only in carrier deployments
- **[MGA]** — exists only in MGA deployments
- **[BOTH]** — exists in both deployment types
- **[EXTERNAL]** — external party with limited access

### 2.1 Leadership & Strategy Personas

#### PERSONA: Chief Executive Officer (CEO) [BOTH]

**Who they are:** Ultimate authority. In a carrier, sets enterprise strategy. In an MGA, runs the entire operation and often functions as CUO as well.

**What they need:**
- Enterprise dashboard: GWP, loss ratio, combined ratio, growth trends, capacity utilization
- Strategic alerts: material changes in portfolio composition, regulatory developments, carrier relationship status
- Board-ready reporting: agent-generated executive summaries and portfolio reviews
- Authority: can override any decision, can delegate any authority

**Agent interactions:**
- "Show me a board summary of our Q1 performance versus plan"
- "What are our top 5 exposure concentrations and how have they changed this quarter?"
- "Draft talking points for the carrier review meeting on Thursday"

**Entra ID Role:** `openinsure-ceo`
**M365 Surface:** Teams (Insurance Copilot), Dashboard (executive view)
**Authority Level:** Unlimited. Typically delegates operational authority to CUO, CCO, CFO.

---

#### PERSONA: Chief Underwriting Officer (CUO) [BOTH]

**Who they are:** Senior-most underwriting authority. Sets underwriting strategy, defines risk appetite, approves exceptions, manages carrier relationships (at MGA) or LOB strategy (at carrier).

**What they need:**
- Full portfolio visibility (all submissions, policies, claims, financials)
- Authority to approve any underwriting decision (no ceiling)
- Override capability on any agent recommendation with reason logging
- Risk appetite configuration: define and modify underwriting guidelines that agents follow
- Authority delegation: set and modify authority levels for LOB Heads and underwriters
- Product configuration approval (new products, rate changes)
- Carrier reporting dashboards (MGA) or enterprise underwriting performance (carrier)

**What they do day-to-day:**
- Reviews agent-escalated submissions that exceed all other authority levels
- Monitors portfolio-level metrics: loss ratio trends, concentration risk, capacity utilization
- Adjusts underwriting guidelines in the knowledge graph (immediately changes agent behavior)
- Approves new product configurations before deployment
- Reviews quarterly compliance and bias audit reports
- Manages relationships with capacity providers (MGA) or oversees LOB Heads (carrier)

**Agent interactions:**
- Receives escalated submissions with full context package
- "Show me our cyber exposure in healthcare above $5M limits"
- "Tighten our appetite for retail businesses with revenue over $100M — require VP-level review"
- "What percentage of quotes are we losing? Show me decline reasons by broker"

**Entra ID Role:** `openinsure-cuo`
**M365 Surface:** Teams (Insurance Copilot), Outlook (submission notifications), Dashboard (portfolio view)
**Authority Level:** Unlimited underwriting authority. Can configure all underwriting agents.

---

### 2.2 Underwriting Personas

#### PERSONA: LOB Head / VP of Underwriting [CARRIER]

**Who they are:** Manages a line of business (e.g., VP Cyber, VP Property, VP Professional Lines). Only exists in carriers with multiple LOBs. Has P&L responsibility for their line.

**What they need:**
- Full visibility into their LOB: all submissions, policies, claims, performance metrics
- Underwriting authority within their LOB (typically high, e.g., up to $10M limits)
- Authority delegation to underwriters within their LOB
- LOB strategy tools: pricing adequacy analysis, rate change impact modeling, portfolio composition management
- Competitive intelligence: win/loss rates, pricing benchmarks
- Carrier/reinsurer relationship management for their LOB

**What they do day-to-day:**
- Sets LOB-specific underwriting guidelines (within CUO's enterprise appetite)
- Reviews exceptions escalated from their underwriters
- Monitors LOB performance: growth, profitability, reserve adequacy
- Works with actuarial team on pricing models and rate changes
- Manages underwriter workload and performance

**Agent interactions:**
- "Show me our property portfolio loss ratio by territory, excluding cat losses"
- "What's our hit ratio this quarter versus last year? Break it down by broker"
- "Model the impact of a 10% rate increase on our commercial property book"
- "Assign the new cyber submission from [Broker] to [Senior UW] — it's in their specialty"

**Entra ID Role:** `openinsure-lob-head`
**M365 Surface:** Teams, Dashboard (LOB-specific views)
**Authority Level:** Within LOB, up to configured limit. Cross-LOB requires CUO.

---

#### PERSONA: Senior Underwriter [BOTH]

**Who they are:** Experienced underwriter with delegated authority for a defined scope (LOB, limit, territory). Handles complex risks, mentors through knowledge graph refinement, manages broker relationships.

**What they need:**
- Visibility into assigned submissions and portfolio segment
- Underwriting authority within delegated limits (e.g., up to $2M limits for cyber)
- Submission workbench: agent pre-analyzed package, add own assessment, record decision
- Quote issuance within authority
- Renewal management for their book
- Broker communication tools

**What they do day-to-day:**
- Reviews amber-flagged submissions (agent recommends, needs human confirmation)
- Handles complex risks exceeding standard guidelines
- Negotiates terms with brokers (modifying agent-proposed terms for relationship/market dynamics)
- Refines knowledge graph: overrides agent with explanation — feedback trains the system
- Monitors their book performance (loss ratio, retention, premium growth)

**Agent interactions:**
- "What's in my queue? Prioritize by premium size and expiry date"
- Reviews agent's pre-filled workbench with risk summary, comparables, recommended terms, confidence score. Approves, modifies, or overrides.
- "Issue this quote with modifications: increase deductible to $50K, add ransomware sublimit of $1M"
- "Draft a declination letter for SUB-2024-0847, reason: loss history exceeds appetite"

**Entra ID Role:** `openinsure-senior-underwriter`
**M365 Surface:** Teams (Insurance Copilot), Outlook, Dashboard (personal workbench)
**Authority Level:** Configurable per individual — limit, LOB, territory, premium thresholds

---

#### PERSONA: Underwriting Analyst / Junior Underwriter [BOTH]

**Who they are:** Less experienced team member. Limited direct authority. Reviews agent output for quality, handles straightforward renewals, assists senior underwriters.

**What they need:**
- Visibility into assigned submissions (subset of queue)
- Limited authority: renewals within defined parameters; new business requires senior review
- Agent output review tools: check extraction accuracy, flag errors
- Learning interface: see agent reasoning chains to understand underwriting logic

**What they do day-to-day:**
- Reviews agent data extraction accuracy on assigned submissions
- Processes routine renewals where no material changes occurred
- Prepares risk summaries for senior underwriter review on complex accounts
- Flags knowledge graph errors or gaps
- Handles broker queries on existing accounts

**Agent interactions:**
- "Show me the extraction results for SUB-2024-0912. Flag fields with confidence below 85%"
- Renewal: Agent presents renewal package; analyst confirms no material changes; agent processes
- "What's our pricing history with accounts in this SIC code and revenue band?"
- "Escalate to [Senior UW] — loss data is inconsistent between application and loss runs"

**Entra ID Role:** `openinsure-uw-analyst`
**M365 Surface:** Teams, Dashboard (limited workbench)
**Authority Level:** Renewal-only within defined parameters. New business requires co-sign.

---

### 2.3 Actuarial Personas

#### PERSONA: Chief Actuary / Head of Actuarial [CARRIER]

**Who they are:** Responsible for reserve adequacy, pricing model oversight, capital adequacy analysis, and regulatory actuarial reporting. Reports to CEO or CFO. Required by regulation in most jurisdictions for licensed carriers.

**What they need:**
- Full access to all claims, policy, and financial data
- Reserve analysis tools: loss development triangles, IBNR calculations, reserve adequacy testing
- Pricing model management: rate adequacy analysis, filing support, competitive benchmarking
- Capital modeling integration: Solvency II internal model data (EU) or RBC analysis (US)
- Actuarial opinion preparation support
- Catastrophe modeling outputs and accumulation analysis

**What they do day-to-day:**
- Reviews agent-generated loss development triangles and IBNR estimates; applies judgment to select ultimate losses
- Approves or adjusts actuarial reserve recommendations
- Oversees pricing models that feed into agent rating algorithms
- Prepares actuarial opinions for statutory reporting
- Advises CUO on appetite and pricing adequacy by segment
- Reviews catastrophe model outputs for accumulation management

**Agent interactions:**
- "Generate loss development triangles for our cyber book, accident years 2022-2025, as-of December 2025"
- "Show me reserve adequacy by LOB. Flag any segments where agent-booked reserves deviate more than 15% from actuarial indication"
- "What's the implied loss ratio at our current rate level for commercial property in Texas?"
- "Compile the data package for the Q4 actuarial reserve review — I need paid, incurred, case reserves, and IBNR by accident year and LOB"
- "Run a rate adequacy test on our cyber portfolio using the latest 24 months of loss emergence"

**Entra ID Role:** `openinsure-chief-actuary`
**M365 Surface:** Teams, Dashboard (actuarial workbench), Excel (model integration)
**Authority Level:** Reserve-setting authority. Pricing model approval authority. Cannot bind policies or settle claims. Advisory to CUO on underwriting.

---

#### PERSONA: Reserving / Pricing Actuary [CARRIER]

**Who they are:** Actuaries working under Chief Actuary direction. Reserving actuaries focus on loss reserve adequacy; pricing actuaries focus on rate development and filing support.

**What they need:**
- Claims and policy data access for their assigned LOBs
- Actuarial modeling tools and agent-generated data compilations
- Triangle generation and manipulation tools
- Rate filing preparation support

**Agent interactions:**
- "Pull all closed cyber claims from 2023, categorized by cause of loss. Include paid amounts and closure lag"
- "Generate a Bornhuetter-Ferguson IBNR estimate for our property book using the selections I uploaded"
- "Compare our current filed rates to loss cost indications by state for commercial auto"

**Entra ID Role:** `openinsure-actuary`
**M365 Surface:** Teams, Dashboard (actuarial views), Excel
**Authority Level:** Can set individual reserve recommendations subject to Chief Actuary approval. Cannot modify policies or claims.

---

### 2.4 Claims Personas

#### PERSONA: Chief Claims Officer (CCO) / Claims Manager [BOTH]

**Who they are:** Senior claims authority. At a carrier, manages claims department across LOBs. At an MGA, may be a single person managing all claims. Sets claims philosophy, manages reserve adequacy, approves large settlements, handles litigated claims.

**What they need:**
- Full claims portfolio visibility
- Settlement authority (configurable ceiling; above requires CUO/carrier approval)
- Reserve adequacy dashboard (works with actuarial at carrier)
- Litigation tracking and management
- Carrier reporting (MGA) or enterprise claims reporting (carrier)
- Fraud detection oversight
- Vendor management (defense counsel, forensics, restoration)

**What they do day-to-day:**
- Reviews agent-escalated claims (complex, high-value, litigated, fraud-flagged)
- Approves settlements above adjuster authority
- Monitors reserve adequacy across portfolio
- Manages vendor relationships
- Reviews claims agent performance (cycle time, accuracy, leakage)
- At carrier: coordinates with actuarial on reserve reviews

**Agent interactions:**
- "Show all open claims with reserves above $100K. Flag any with reserves unchanged for 60+ days"
- Agent provides claim timeline, coverage analysis, comparable settlement data
- Settlement authorization: agent recommends amount with reasoning; CCO approves or adjusts
- "Show fraud indicators for CLM-2024-0156. What triggered the flag?"

**Entra ID Role:** `openinsure-claims-manager`
**M365 Surface:** Teams, Outlook (claim notifications), Dashboard (claims portfolio)
**Authority Level:** Configurable settlement ceiling. Can configure claims agent behavior.

---

#### PERSONA: Claims Adjuster [BOTH]

**Who they are:** Handles individual claims from investigation through settlement. May be in-house or contracted (TPA).

**What they need:**
- Access to assigned claims only (not full portfolio)
- Settlement authority within defined limits (e.g., up to $25K)
- Investigation tools: document management, vendor coordination, timeline tracking
- Coverage analysis support from agents
- Reserve adjustment capability within guidelines

**Agent interactions:**
- Claim assignment: agent presents pre-analyzed claim package
- "Pull all documents for CLM-2024-0203. Summarize key coverage issues"
- "Update reserve to $75K" (within authority) or "Recommend reserve increase to $150K — escalate to CCO"
- "Prepare settlement release for $22,000 to [Claimant]" (within authority)

**Entra ID Role:** `openinsure-claims-adjuster`
**M365 Surface:** Teams, Dashboard (assigned claims view)
**Authority Level:** Per-claim settlement limit. Reserve adjustment within band.

---

### 2.5 Finance & Reinsurance Personas

#### PERSONA: CFO / Finance Director [BOTH]

**Who they are:** At carrier, oversees accounting, reinsurance, investment, and financial reporting. At MGA, manages premium accounting, commissions, and carrier financial reporting.

**What they need:**
- Full financial data visibility
- Statutory financial reporting tools (carrier)
- Bordereaux generation and delivery (MGA)
- Cash flow management and forecasting
- Financial close process management

**Entra ID Role:** `openinsure-cfo`
**M365 Surface:** Teams, Dashboard (financial overview), Excel
**Authority Level:** Financial reporting and configuration. No underwriting or claims authority.

---

#### PERSONA: Finance / Accounting Lead [BOTH]

**Who they are:** Manages premium accounting, commission reconciliation, regulatory financial reporting, and cash flow operations.

**What they need:**
- Full financial data visibility (premium, payments, commissions, reserves)
- Billing configuration (payment plans, agency vs. direct bill)
- Commission schedule management
- Bordereaux generation and carrier reporting (MGA) or statutory reporting support (carrier)
- Bank reconciliation support

**Agent interactions:**
- "Generate the monthly bordereaux for [Carrier] — premium, claims, and loss ratio"
- "Show unmatched payments for the last 30 days"
- "Calculate commissions for Q1 and prepare distribution report"
- "Prepare the statutory annual filing data for [jurisdiction]" (carrier)

**Entra ID Role:** `openinsure-finance`
**M365 Surface:** Teams, Excel, Dashboard (financial overview)
**Authority Level:** Financial reporting and billing configuration. No underwriting or claims authority.

---

#### PERSONA: Reinsurance Manager [CARRIER]

**Who they are:** Manages the carrier's reinsurance program: treaty placement, facultative submissions, cession tracking, recovery collection, and reinsurer relationships. At smaller carriers, may be part of the CFO's team; at larger carriers, a dedicated function.

**What they need:**
- Reinsurance treaty management: terms, limits, retentions, reinstatements, expiry dates
- Cession tracking: which policies cede to which treaties, cession amounts, running totals
- Facultative placement: submission of individual risks to reinsurers
- Recovery management: calculating and collecting reinsurance recoveries on claims
- Bordereaux generation for reinsurers (premium and claims)
- Treaty utilization dashboards: capacity remaining, reinstatement status
- Catastrophe accumulation vs. treaty capacity

**What they do day-to-day:**
- Monitors automatic cessions generated by agents against treaty terms
- Handles facultative placements for risks outside treaty scope
- Manages treaty renewals and renegotiations with reinsurers
- Tracks and collects reinsurance recoveries on paid claims
- Produces reinsurance reporting for quarterly/annual reviews
- Coordinates with actuarial on ceded reserves

**Agent interactions:**
- "Show treaty utilization across all property treaties. Flag any within 80% of capacity"
- "Generate the quarterly premium bordereau for [Reinsurer] on Treaty XYZ-2025"
- "Calculate the reinsurance recovery on CLM-2024-0089 under our excess-of-loss treaty"
- "This risk exceeds our net retention. Prepare a facultative submission package for [Reinsurer Panel]"
- "What's our aggregate cat exposure versus treaty capacity by peril zone?"

**Entra ID Role:** `openinsure-reinsurance-manager`
**M365 Surface:** Teams, Dashboard (reinsurance views)
**Authority Level:** Reinsurance operations. Can trigger cession calculations and recovery requests. Cannot bind policies or settle claims directly.

---

### 2.6 Compliance & Risk Personas

#### PERSONA: Chief Risk / Compliance Officer [BOTH]

**Who they are:** Responsible for regulatory compliance, AI governance, audit management, enterprise risk management, and reporting to regulators. At MGA, often combined with legal.

**What they need:**
- Full audit trail access (every agent decision, every human override)
- EU AI Act compliance dashboard (system inventory, risk classifications, conformity status)
- Bias monitoring reports (automated + ad-hoc)
- Regulatory change tracking
- Rate filing status and documentation
- Market conduct exam preparation tools
- Ability to halt or restrict agent operations if compliance issue detected
- Enterprise risk register (carrier)
- Solvency II / ORSA reporting support (carrier, EU)

**What they do day-to-day:**
- Reviews automated bias monitoring reports; investigates flags
- Maintains AI system inventory and risk classifications per EU AI Act
- Prepares regulatory filings and compliance documentation
- Conducts or oversees internal audits of agent decision quality
- Monitors regulatory changes and assesses operational impact
- Reviews and approves knowledge graph changes affecting compliance logic
- At carrier: manages enterprise risk register, ORSA reporting

**Agent interactions:**
- "Show all overridden underwriting decisions this month. Categorize override reasons"
- "Run disparate impact analysis on our cyber quotes by industry sector and company size"
- "Generate the EU AI Act Article 11 technical documentation for our underwriting system"
- "What regulatory changes in the last 30 days affect our cyber product in Germany?"
- "Suspend auto-bind on all new business until I release the hold"

**Entra ID Role:** `openinsure-compliance`
**M365 Surface:** Teams, Dashboard (compliance views), Purview integration
**Authority Level:** Can suspend agent auto-execution. Cannot underwrite or settle claims. Full audit read access.

---

### 2.7 Delegated Authority Personas

#### PERSONA: Delegated Authority Manager / MGA Oversight [CARRIER]

**Who they are:** Manages the carrier's relationships with MGAs, coverholders, and other delegated authority partners. Monitors their performance, ensures compliance with binding authority agreements, audits their underwriting decisions, and manages capacity allocation. This function is growing in importance — 43% of top 100 US P&C carriers have at least one MGA relationship.

**What they need:**
- MGA performance dashboards: premium volume, loss ratio, combined ratio per MGA
- Binding authority utilization tracking: what has each MGA written vs. their authority limit?
- Bordereaux processing: ingest and validate MGA-submitted bordereaux
- Underwriting audit: sample and review MGA underwriting decisions for guideline compliance
- Claims oversight: review MGA-handled claims for compliance with claims authority
- Compliance monitoring: ensure MGAs maintain required licenses, E&O coverage, regulatory filings
- Authority management: grant, modify, suspend, or revoke MGA binding authority

**What they do day-to-day:**
- Reviews MGA bordereaux (agent pre-validates, human reviews exceptions)
- Monitors MGA performance metrics against plan and authority terms
- Conducts periodic underwriting audits (agent samples and flags anomalies)
- Manages MGA onboarding and authority renewal processes
- Investigates MGA compliance issues or performance deterioration
- Reports to CUO and board on delegated authority portfolio

**Agent interactions:**
- "Show me performance summary for all active MGAs. Flag any with loss ratio above 65%"
- "Audit the last 50 submissions bound by [MGA Name]. Flag any outside their authority parameters"
- "Compare [MGA]'s actual vs. authorized premium by month for the current treaty year"
- "[MGA] submitted their Q4 bordereau. Validate it against policy records and flag discrepancies"
- "Generate the annual delegated authority review package for [MGA Name]"

**Entra ID Role:** `openinsure-da-manager`
**M365 Surface:** Teams, Dashboard (DA oversight views)
**Authority Level:** Can suspend or restrict MGA binding authority. Read access to all MGA-originated business. Cannot directly underwrite or settle claims.

---

### 2.8 Product & Technology Personas

#### PERSONA: Product Manager / Head of Product & Data [BOTH]

**Who they are:** Owns product design, knowledge graph content, agent configuration, and data strategy. Bridge between insurance expertise and AI system behavior.

**What they need:**
- Knowledge graph authoring and editing tools
- Product definition management (create, modify, version products)
- Rating algorithm configuration
- Agent behavior tuning (confidence thresholds, escalation triggers, model selection)
- A/B testing capabilities (compare agent performance under different configurations)
- Data quality monitoring

**Agent interactions:**
- Product creation via conversational interface
- "Add new underwriting guideline: for healthcare accounts, require security questionnaire"
- "The underwriting agent is escalating 40% of submissions. Show distribution by trigger type. Adjust thresholds"
- "What percentage of SecurityScorecard enrichments return null? Alert me if above 10%"

**Entra ID Role:** `openinsure-product-manager`
**M365 Surface:** Teams, Foundry portal, Dashboard (product analytics)
**Authority Level:** Full knowledge graph and agent configuration. No direct underwriting or claims authority.

---

#### PERSONA: Platform Administrator [BOTH]

**Who they are:** Manages the OpenInsure deployment. Infrastructure, agent deployment, user provisioning, system health. In small MGA, may be Operations Lead or contractor.

**What they need:**
- Full system configuration access
- Agent deployment and version management
- User/role provisioning and RBAC management
- System health monitoring and alerting
- Integration configuration (connectors, data providers)
- Audit log access (system-level)

**What they should NOT have:**
- Underwriting authority
- Claims settlement authority
- Ability to modify audit trails or decision records

**Entra ID Role:** `openinsure-platform-admin`
**M365 Surface:** Admin dashboard, Foundry portal, M365 Admin Center
**Authority Level:** Full platform, zero insurance operations

---

#### PERSONA: Operations Lead [BOTH]

**Who they are:** Manages day-to-day platform operations, agent performance, exception queue management, service levels.

**What they need:**
- Real-time operational dashboard (volumes, processing times, queue depths, SLAs)
- Exception queue management (stuck items, agent errors, integration failures)
- Agent performance metrics
- Workflow monitoring and bottleneck identification

**Entra ID Role:** `openinsure-operations`
**M365 Surface:** Teams, Dashboard (operations view)
**Authority Level:** Operational monitoring and exception resolution. Can restart failed workflows. No insurance decision authority.

---

### 2.9 External Personas

#### PERSONA: Broker / Producing Agent [EXTERNAL, BOTH]

**Who they are:** External distribution partner who submits business, receives quotes, manages client relationships.

**What they need (via portal or API):**
- Submission upload (documents, structured data, or both)
- Submission status tracking
- Quote retrieval and comparison
- Bind request submission
- Policy document download
- Certificate of insurance requests
- Endorsement requests
- Claim reporting (FNOL on behalf of insured)
- Account overview (their book of business)
- Commission statements

**What they should NOT see:**
- Internal underwriting notes, agent confidence scores, internal risk assessments
- Other brokers' submissions or accounts
- Pricing models, rating factors, guidelines
- Internal portfolio data

**Interaction model:** Email (agents process inbound automatically), Portal (self-service web), API (programmatic for high-volume brokers). Agent responses to brokers use market-appropriate language, not internal jargon.

**Entra ID Role:** `openinsure-broker` (B2B guest access)
**Surface:** Broker Portal, email, API
**Authority Level:** Submit and request. No decision authority.

---

#### PERSONA: MGA / Coverholder [EXTERNAL, CARRIER]

**Who they are:** The delegated authority partner. Submits bordereaux, requests authority changes, refers risks exceeding their authority, reports claims. This is the carrier-side view of an MGA — the MGA may be running their own OpenInsure instance, or may use their own systems.

**What they need:**
- Bordereaux submission interface (upload premium, claims, loss data)
- Referral submission (risks exceeding their authority, routed to carrier underwriting)
- Authority documentation (current binding authority agreement, guidelines, appetite)
- Claims reporting above their authority threshold
- Performance dashboards (their own book, as shared with the carrier)
- Certificate and document access for their business

**What they should NOT see:**
- Carrier's full portfolio beyond their own production
- Other MGAs' data
- Carrier's internal underwriting guidelines outside their authority scope
- Carrier's reinsurance arrangements
- Carrier's financial data

**Entra ID Role:** `openinsure-mga-external` (B2B guest access)
**Surface:** MGA Portal, API (bordereaux submission), email (referrals)
**Authority Level:** Submit bordereaux, submit referrals, report claims within authority. No access to carrier operations.

---

#### PERSONA: Policyholder / Insured [EXTERNAL, BOTH]

**Who they are:** The end customer. Interaction typically mediated by broker. Direct access is optional and limited.

**What they need (if direct access enabled):**
- Policy document access
- Certificate of insurance requests (auto-generated)
- Claim reporting (FNOL)
- Claim status tracking
- Payment / billing information
- Contact information updates

**Entra ID Role:** `openinsure-policyholder` (optional, B2C guest access)
**Surface:** Policyholder portal, claims chatbot
**Authority Level:** View own policies. Report claims. Request certificates.

---

#### PERSONA: Reinsurer [EXTERNAL, CARRIER]

**Who they are:** Provides reinsurance capacity to the carrier. Receives cession data, bordereaux, and claims reporting. May need to approve facultative placements.

**What they need:**
- Cession and premium bordereaux for their treaties
- Claims bordereaux and large loss notifications
- Facultative submission review and approval workflow
- Portfolio analytics for their participation (read-only)
- Treaty utilization reporting

**Entra ID Role:** `openinsure-reinsurer` (B2B guest access, read-only + facultative workflow)
**Surface:** Reinsurer Portal, API (data feeds), email (automated reports)
**Authority Level:** Approve/decline facultative submissions. Read-only on their ceded business.

---

#### PERSONA: Regulator / Auditor [EXTERNAL, BOTH]

**Who they are:** State insurance departments, BaFin, FCA, or appointed external auditors.

**What they need:**
- Read-only access to specific data scopes defined by exam
- Decision audit trails with full reasoning chains
- EU AI Act technical documentation
- Bias audit reports
- Rate filing documentation

**Interaction model:** Time-limited, scope-limited access provisioned by Compliance Officer. Access automatically expires.

**Entra ID Role:** `openinsure-auditor` (scoped, time-limited)
**Surface:** Audit Portal (read-only), data export tools
**Authority Level:** Read-only within defined scope and time window.

---

#### PERSONA: Third-Party Service Provider [EXTERNAL, BOTH]

**Who they are:** External vendors — loss adjusters, defense counsel, forensic investigators, restoration companies, data enrichment providers.

**Entra ID Role:** `openinsure-vendor` (scoped per assignment)
**Surface:** Vendor Portal, API
**Authority Level:** Scoped to assigned cases only. Upload documents and update status.

---

## 3. Role-Based Access Control (RBAC) Matrix

### 3.1 Data Access Matrix

Legend: **F** = Full Read/Write, **R** = Read only, **O** = Own/Assigned only, **S** = Summary/Aggregated, **C** = Config, **—** = No Access, **P** = Propose (requires approval)

| Data Domain | Platform Admin | CEO | CUO | LOB Head | Sr UW | UW Analyst | Chief Actuary | Actuary | CCO | Adjuster | CFO | Finance | RI Mgr | Compliance | DA Mgr | Product Mgr |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Submissions | C | S | F | Own LOB | Own Queue | Own Queue | R | R (own LOB) | R | — | S | S | — | R | MGA's | R |
| Policies | C | S | F | Own LOB | Own Book | Own Book | R | R (own LOB) | R | Assigned | R | R | Ceded | R | MGA's | R |
| Claims | C | S | R | Own LOB | R (own) | — | R | R (own LOB) | F | Assigned | S | S | Ceded | R | MGA's | R |
| Reserves (Actuarial) | C | S | R | R (own LOB) | — | — | F | Own LOB | R | — | R | S | Ceded | R | — | R |
| Reinsurance | C | S | R | R (own LOB) | — | — | R | — | — | — | R | S | F | R | — | R |
| Financial Data | C | S | S | — | — | — | R | — | — | — | F | F | S | R | MGA's | S |
| Audit Trails | System | — | — | — | — | — | — | — | — | — | — | — | — | F | R (MGA's) | — |
| Knowledge Graph | C | — | F | Edit (LOB) | P | P | P (reserve) | — | — | — | — | — | — | Approve | — | F |
| Agent Config | F | — | R | — | — | — | — | — | — | — | — | — | — | Override | — | F |
| Bias Reports | — | S | R | R (LOB) | — | — | R | — | — | — | — | — | — | F | R | R |
| MGA Oversight | — | S | R | — | — | — | — | — | — | — | — | — | — | R | F | — |
| System Config | F | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — |

### 3.2 Action Authority Matrix

| Action | Agent Auto | UW Analyst | Sr UW | LOB Head | CUO | Adjuster | CCO | Chief Actuary | RI Mgr | Compliance | DA Mgr |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Extract submission data | Yes | — | — | — | — | — | — | — | — | — | — |
| Triage submission | Yes | — | — | — | — | — | — | — | — | — | — |
| Quote (within auto-auth) | Yes | — | — | — | — | — | — | — | — | — | — |
| Quote (above auto-auth) | Recommend | Co-sign | Approve | Approve | Approve | — | — | — | — | — | — |
| Bind (within authority) | Yes* | Renewal only | Within limit | LOB limit | Unlimited | — | — | — | — | — | — |
| Decline submission | Yes** | — | Own book | LOB | Unlimited | — | — | — | — | — | — |
| Endorse policy | Yes*** | Minor | Full | Full | Full | — | — | — | — | — | — |
| Cancel policy | Recommend | — | Approve | Approve | Approve | — | — | — | — | — | — |
| Report claim (FNOL) | Yes | — | — | — | — | — | — | — | — | — | — |
| Set initial reserve | Yes | — | — | — | — | Adjust | Approve | Review | — | — | — |
| Set actuarial reserve | — | — | — | — | — | — | — | Approve | — | — | — |
| Settle claim | — | — | — | — | — | Within limit | Approve | — | — | — | — |
| Process payment | Yes**** | — | — | — | — | — | — | — | — | — | — |
| Calculate cession | Yes | — | — | — | — | — | — | — | Approve | — | — |
| Place facultative RI | — | — | — | — | — | — | — | — | Approve | — | — |
| Collect RI recovery | Recommend | — | — | — | — | — | — | — | Approve | — | — |
| Modify knowledge graph | — | P | P | P | Approve | — | — | P | — | Approve | — |
| Suspend agents | — | — | — | — | Yes | — | — | — | — | Yes | — |
| Modify agent config | — | — | — | — | R | — | — | — | — | Override | — |
| Suspend MGA authority | — | — | — | — | Yes | — | — | — | — | — | Approve |
| Audit MGA book | — | — | — | — | — | — | — | — | — | — | Trigger |
| Generate bordereaux | Yes | — | — | — | — | — | — | — | Yes | — | Yes |
| File statutory report | Prepare | — | — | — | — | — | — | Certify | — | Approve | — |

\* Auto-bind: within configured limits, subjectivities met, premium confirmed, no referral triggers.
\** Auto-decline: clear out-of-appetite only. Borderline requires human.
\*** Auto-endorsement: administrative changes only. Coverage changes require human.
\**** Auto-payment: scheduled installments on confirmed plans only.

---

## 4. Workflow Specifications by Business Process

### 4.1 New Business Submission Workflow [BOTH]

```
TRIGGER: Submission received (email / portal / API)
│
├─ STEP 1: Intake (Agent: auto)
│  Action: Document classification, data extraction, validation
│  Duration: 2-5 minutes
│  Human involvement: None
│  Output: Structured submission record
│
├─ STEP 2: Triage (Agent: auto)
│  Action: Appetite check, priority score, enrichment
│  Duration: 1-3 minutes
│  Human involvement: None
│  Decision:
│    ├─ CLEAR DECLINE → Agent sends declination (Sr UW notified)
│    ├─ CLEAR APPETITE → Step 3
│    └─ BORDERLINE → Route to Sr UW or LOB Head queue
│
├─ STEP 3: Pricing & Terms (Agent: auto for standard, human for complex)
│  Action: Run rating, generate terms, comparable analysis
│  Duration: 1-5 minutes
│  Decision:
│    ├─ WITHIN AUTO-AUTHORITY → Step 4
│    ├─ ABOVE AUTO but within Sr UW → Route to Sr UW
│    ├─ ABOVE Sr UW but within LOB Head [CARRIER] → Route to LOB Head
│    └─ REFERRAL TRIGGER → Route to CUO with referral package
│
├─ STEP 4: Quote Issuance
│  Action: Generate quote document, send to broker
│
├─ STEP 5: Quote Follow-Up (Agent: auto)
│  Action: Track status, reminders at configured intervals
│
├─ STEP 6: Bind Request (Agent + Human)
│  Action: Verify bind requirements (signed app, payment, subjectivities)
│  Decision:
│    ├─ ALL MET + WITHIN AUTHORITY → Auto-bind
│    ├─ ALL MET + ABOVE AUTHORITY → Route to authority holder
│    └─ REQUIREMENTS NOT MET → Notify broker of outstanding items
│
├─ STEP 7: Policy Issuance (Agent: auto)
│  Action: Create policy, generate documents, trigger billing
│  CARRIER ADDITION: Trigger cession calculation against applicable treaties
│
├─ STEP 8: Cession Processing [CARRIER] (Agent: auto, RI Mgr reviews)
│  Action: Calculate cession per treaty terms, update treaty utilization
│  If outside treaty scope: flag for facultative placement
│
└─ STEP 9: Compliance Logging (Agent: auto, background)
   Action: Record all decisions in audit trail
```

### 4.2 Claims Workflow [BOTH]

```
TRIGGER: Claim reported (phone / email / portal / agent FNOL)
│
├─ STEP 1: FNOL Intake (Agent: auto)
│  Duration: 5-10 minutes
│  Output: Structured FNOL record
│
├─ STEP 2: Coverage Verification (Agent: auto)
│  Duration: 1-2 minutes
│  Decision:
│    ├─ COVERAGE CONFIRMED → Continue
│    ├─ COVERAGE QUESTIONABLE → CCO review
│    └─ NO COVERAGE → Generate denial letter (CCO approval required)
│
├─ STEP 3: Triage & Assignment (Agent: auto)
│  Decision:
│    ├─ LOW SEVERITY + NO FRAUD → Auto-assign adjuster
│    ├─ MEDIUM → Experienced adjuster
│    ├─ HIGH → Senior adjuster + notify CCO
│    ├─ FRAUD FLAGGED → CCO + fraud analysis
│    └─ LITIGATION POTENTIAL → CCO + flag for counsel
│
├─ STEP 4: Initial Reserve (Agent: auto, human review for large)
│  Authority:
│    ├─ Below $25K → Agent sets
│    ├─ $25K-$100K → Agent recommends, adjuster confirms
│    └─ Above $100K → Agent recommends, CCO approves
│  CARRIER ADDITION: Notify actuarial if above bulk reserve threshold
│
├─ STEP 5: Investigation (Adjuster-led, agent-assisted)
│
├─ STEP 6: Reserve Updates (Ongoing)
│  Agent monitors: flag unchanged reserves on active claims
│  CARRIER ADDITION: Actuarial reserve review integration at quarter-end
│
├─ STEP 7: Settlement
│  Authority chain: Adjuster → CCO → CUO → Carrier board (if applicable)
│
├─ STEP 8: Reinsurance Recovery [CARRIER]
│  Action: Calculate reinsurance recoveries on settled/paid claims
│  RI Agent: identifies applicable treaties, calculates recovery amount
│  RI Manager: reviews and approves recovery billing to reinsurer
│
├─ STEP 9: Payment (Agent: auto after approval)
│  Finance approval for payments above threshold
│
└─ STEP 10: Closure
   Action: Final reserve, closing report, update records
   CARRIER ADDITION: Large loss reporting to reinsurer as per treaty terms
   CARRIER ADDITION: Actuarial notification for reserve release/adjustment
```

### 4.3 Renewal Workflow [BOTH]

```
TRIGGER: Policy approaching renewal (90/60/30 day markers)
│
├─ DAY -90: Renewal Notice (Agent: auto)
│  Action: Identify renewing policies, pull updated data, flag changes
│  Output: Renewal list to Sr UW / LOB Head with change flags
│
├─ DAY -60: Renewal Analysis (Agent + UW review)
│  Agent auto-processes: No-change renewals within authority
│  Human review: Material changes, adverse loss development, market shifts
│  CARRIER ADDITION: Actuarial re-pricing input for rate-change segments
│
├─ DAY -30: Renewal Quote
│  Agent auto-issues or human-approved based on authority
│
├─ RENEWAL DATE: Bind or Expire
│
└─ POST-RENEWAL: Cession update [CARRIER], compliance logging
```

### 4.4 Reinsurance Cession Workflow [CARRIER ONLY]

```
TRIGGER: Policy bound or endorsed
│
├─ STEP 1: Treaty Matching (Agent: auto)
│  Action: Identify applicable treaties based on LOB, territory, limit, risk type
│  Match each policy to its cession structure (quota share, excess-of-loss, surplus)
│
├─ STEP 2: Cession Calculation (Agent: auto)
│  Action: Calculate ceded premium per treaty terms
│  Update running treaty utilization
│
├─ STEP 3: Validation (Agent: auto, RI Manager reviews exceptions)
│  Decision:
│    ├─ STANDARD CESSION → Auto-process, log
│    ├─ TREATY CAPACITY NEAR LIMIT → Alert RI Manager
│    ├─ OUTSIDE ALL TREATIES → Flag for facultative placement
│    └─ ANOMALOUS → Route to RI Manager for manual review
│
├─ STEP 4: Facultative Placement (if needed) (RI Manager-led)
│  Action: RI Manager prepares and submits fac placement
│  Agent assists: generates submission package, contacts reinsurer panel
│  Reinsurer responds through portal or email
│
├─ STEP 5: Bordereaux Generation (Agent: auto, periodic)
│  Action: Generate premium and claims bordereaux per reinsurer, per treaty
│  Frequency: Monthly/quarterly per treaty terms
│  RI Manager: reviews before delivery
│
└─ STEP 6: Recovery Processing (on claims)
   Trigger: Claim payment exceeds retention
   Agent calculates recovery amount per treaty
   RI Manager approves billing to reinsurer
```

### 4.5 Actuarial Reserve Review Workflow [CARRIER ONLY]

```
TRIGGER: Quarterly (or as configured)
│
├─ STEP 1: Data Compilation (Agent: auto)
│  Action: Compile loss development data by LOB, accident year
│  Generate triangles: paid, incurred, case reserves, claim counts
│  Pull policy exposure data for rate adequacy analysis
│  Duration: Minutes (vs. days/weeks traditionally)
│
├─ STEP 2: Automated Analysis (Agent: auto)
│  Action: Run standard actuarial methods (chain ladder, BF, frequency-severity)
│  Produce initial IBNR estimates with ranges
│  Flag segments with significant development or volatility
│  Compare agent-booked case reserves to actuarial indications
│
├─ STEP 3: Actuarial Review (Chief Actuary / Actuary)
│  Action: Review agent-generated analysis
│  Apply judgment: select methods, weight estimates, adjust for known trends
│  Record selections and reasoning (audit trail)
│
├─ STEP 4: Reserve Recommendation
│  Chief Actuary: produces carried reserve recommendation
│  Presented to CFO and CUO for discussion
│  Board or audit committee review if material changes
│
├─ STEP 5: Reserve Booking (Finance: executes)
│  Action: Book actuarial reserve adjustments in financial records
│  Agent: generates journal entries, updates statutory reports
│
└─ STEP 6: Documentation (Agent: auto + Actuary)
   Action: Generate actuarial memorandum documenting analysis and selections
   Chief Actuary: reviews and signs
   Compliance: archives for regulatory record
```

### 4.6 MGA Oversight Workflow [CARRIER ONLY]

```
TRIGGER: MGA bordereaux received (monthly/quarterly) + continuous monitoring
│
├─ STEP 1: Bordereaux Ingestion (Agent: auto)
│  Action: Parse MGA-submitted bordereaux (premium, claims, policy data)
│  Validate against expected formats, reconcile to running totals
│  Flag discrepancies (missing policies, premium mismatches, authority breaches)
│
├─ STEP 2: Authority Compliance Check (Agent: auto)
│  Action: Verify every bound policy is within MGA's granted authority
│  Check: LOB, territory, limit, premium, risk class, industry exclusions
│  Decision:
│    ├─ ALL COMPLIANT → Log, continue monitoring
│    ├─ MINOR BREACH → Alert DA Manager
│    └─ MATERIAL BREACH → Alert DA Manager + CUO, flag for investigation
│
├─ STEP 3: Performance Monitoring (Agent: auto, continuous)
│  Metrics tracked: loss ratio, premium vs plan, hit ratio, average premium,
│                    expense ratio, claims frequency, reserve adequacy
│  Agent: compares to benchmarks and prior periods
│  Alerts DA Manager when metrics breach configured thresholds
│
├─ STEP 4: Underwriting Audit (Agent: auto sampling + DA Manager review)
│  Action: Randomly sample N% of MGA-bound policies
│  Agent reviews: guideline compliance, pricing accuracy, documentation quality
│  Flags anomalies for DA Manager review
│  DA Manager: investigates flagged items, documents findings
│
├─ STEP 5: Reporting (Agent: auto)
│  Generate MGA performance scorecards
│  Produce annual delegated authority review packages
│  Feed into carrier's aggregate reporting
│
└─ STEP 6: Authority Management (DA Manager decision)
   Based on review findings:
   ├─ SATISFACTORY → Renew authority, potentially expand
   ├─ CONCERNS → Restrict authority, increase monitoring frequency
   └─ MATERIAL ISSUES → Suspend authority, escalate to CUO/legal
```

### 4.7 Statutory Reporting Workflow [CARRIER ONLY]

```
TRIGGER: Regulatory filing deadlines (quarterly, annual per jurisdiction)
│
├─ STEP 1: Data Compilation (Agent: auto)
│  Action: Aggregate policy, claims, financial data per regulatory requirements
│  Map internal data to statutory reporting formats
│  Cross-check against general ledger
│
├─ STEP 2: Report Generation (Agent: auto)
│  Action: Populate statutory reporting templates
│  Generate supporting schedules
│  Produce variance analysis vs. prior period
│
├─ STEP 3: Review Chain
│  Finance Lead: reviews financial accuracy
│  Chief Actuary: certifies actuarial components (Schedule P, reserve opinions)
│  Compliance Officer: reviews regulatory compliance
│  CFO: final review and sign-off
│
├─ STEP 4: Filing (Agent: auto or manual)
│  Action: Submit to regulatory systems (SERFF, BaFin portal, EIOPA)
│  Track confirmation and filing status
│
└─ STEP 5: Archive (Agent: auto)
   Store all filed reports with audit trail
   Maintain for regulatory retention period
```

---

## 5. Agent-Human Collaboration Patterns

### 5.1 Pattern: Agent Prepares, Human Decides

Used for: Complex underwriting, large claims, actuarial selections, authority exceptions.

Agent does all preparation (data gathering, analysis, research, recommendation). Human reviews decision-ready package and makes the call.

**UI requirement:** Decision workbench with agent recommendation, confidence score, reasoning chain, comparables, and approve/modify/decline with mandatory reason field.

### 5.2 Pattern: Agent Executes, Human Monitors

Used for: Routine processing within auto-authority, cession calculations, scheduled payments, renewal processing.

Agent executes autonomously. Human sees summary in monitoring dashboard. Can intervene but typically does not.

**UI requirement:** Real-time dashboard with drill-down. Configurable alerts for anomalies.

### 5.3 Pattern: Agent Assists, Human Leads

Used for: Novel risks, broker negotiations, actuarial judgment, reinsurance placement, board presentations.

Human drives the process. Agent provides real-time research, data, and suggestions.

**UI requirement:** Side panel or chat responding to queries while human works. "What's the loss history for this industry sector?"

### 5.4 Pattern: Agent Alerts, Human Responds

Used for: Compliance monitoring, fraud detection, SLA tracking, MGA authority breaches, reserve staleness, catastrophe accumulation.

Agent continuously monitors. Alerts human when thresholds breached.

**UI requirement:** Notification system with severity levels, routing rules, acknowledge/resolve workflow.

### 5.5 Pattern: Agent Compiles, Human Certifies [CARRIER]

Used for: Statutory filings, actuarial opinions, board reports, regulatory submissions.

Agent compiles and formats data, generates draft documents. Designated human reviews, certifies accuracy, and authorizes submission. Required by regulation — certain filings need a named human signatory.

**UI requirement:** Document review interface with certification workflow, digital signature, and submission tracking.

---

## 6. Dashboard Specifications by Role

### 6.1 CEO / Executive Dashboard [BOTH]

**Sections:**
- Enterprise KPIs: GWP, net written premium, loss ratio, combined ratio, ROE
- Growth: premium trajectory vs. plan, new business vs. renewals
- Portfolio health: top concentrations, worst-performing segments
- Strategic alerts: regulatory changes, carrier relationship status, market shifts
- Agent impact: processing efficiency gains, human intervention rate, cost per policy

### 6.2 CUO Dashboard [BOTH]

**Sections:**
- Portfolio summary: all submissions, policies, claims, financials
- Exposure map: geographic concentration, limit accumulation by peril
- Capacity utilization: written vs. authorized (by carrier at MGA, by LOB at carrier)
- Pipeline: open submissions by stage
- Agent performance: auto-bind rate, escalation rate, processing time
- Compliance alerts: active holds, bias flags

### 6.3 LOB Head Dashboard [CARRIER]

**Sections:**
- LOB performance: premium, loss ratio, combined ratio, growth rate
- Pricing adequacy: current rate level vs. loss cost indication
- Underwriter performance: per-underwriter metrics (volume, hit ratio, loss ratio)
- Competitive position: win/loss analysis, pricing benchmarks
- Pipeline: LOB-specific submissions and quotes

### 6.4 Underwriter Workbench [BOTH]

**Sections:**
- My queue: submissions sorted by priority, with agent recommendation status
- Submission detail: agent's full pre-analysis package when selected
- Decision panel: approve / modify / decline with required fields
- My book: written policies, renewal schedule, loss ratio
- Broker activity: submission volumes and bind rates by broker

### 6.5 Actuarial Workbench [CARRIER]

**Sections:**
- Reserve summary: carried vs. indicated by LOB and accident year
- Loss development triangles: interactive, selectable methods
- IBNR analysis: agent-generated estimates with ranges
- Rate adequacy: current vs. indicated by segment
- Data quality: completeness, consistency, freshness of underlying claims data

### 6.6 Claims Dashboard [BOTH]

**Sections:**
- Open claims inventory: by status, severity, age, reserve
- Agent-flagged items: fraud indicators, coverage questions, reserve staleness
- Settlement queue: claims ready for decision
- Loss development: payment trends, closure rates
- Vendor management: outstanding assignments, SLA tracking
- Reinsurance recoveries: outstanding and collected [CARRIER]

### 6.7 Reinsurance Dashboard [CARRIER]

**Sections:**
- Treaty summary: all active treaties with capacity, utilization, expiry
- Cession activity: recent cessions, running totals, premium vs. plan
- Recovery tracking: outstanding recoveries, aging, collection rates
- Catastrophe accumulation: exposure vs. treaty capacity by zone
- Facultative pipeline: open placements, pending responses

### 6.8 MGA Oversight Dashboard [CARRIER]

**Sections:**
- MGA scorecard: performance summary for each MGA (premium, loss ratio, compliance)
- Authority utilization: written vs. authorized by MGA
- Audit findings: recent samples, flagged items, resolution status
- Bordereaux status: received, validated, exceptions pending
- Trend analysis: MGA performance over time, benchmarked against plan

### 6.9 Compliance Dashboard [BOTH]

**Sections:**
- AI system inventory: all active agents, risk classification (EU AI Act)
- Decision audit: random sample of agent decisions for quality review
- Bias monitoring: automated results, flags, trends
- Regulatory tracker: deadlines, pending filings, changes
- Override log: human overrides with reasons
- MGA compliance: license status, E&O currency, filing compliance [CARRIER]

### 6.10 Operations Dashboard [BOTH]

**Sections:**
- Throughput: submissions, quotes, binds (today / week / month)
- SLA tracking: processing times by stage vs. target
- Agent health: error rates, model latency, integration failures
- Queue depths by stage
- Exception queue: failed or stuck workflows

### 6.11 Finance Dashboard [BOTH]

**Sections:**
- Premium: written, earned, unearned by period
- Claims: paid, reserved, incurred by period
- Cash flow: collections, disbursements, projections
- Commissions: accrued, paid, outstanding
- Reconciliation: unmatched items, aging
- Statutory reporting status [CARRIER]

### 6.12 Broker Portal [EXTERNAL, BOTH]

**Sections:**
- My submissions: status tracking with timeline
- My quotes: active quotes, expiry dates
- My policies: active policies, renewals
- My claims: open claims with status
- Documents: policies, certificates, invoices
- Commissions: statements, payment history

---

## 7. Escalation Matrix

| Trigger | First Escalation | Second Escalation | Emergency |
|---|---|---|---|
| Submission outside appetite (close) | Senior Underwriter | LOB Head [CARRIER] / CUO | — |
| Quote above auto-authority | Authority holder per matrix | LOB Head / CUO | — |
| Bind with unmet subjectivities | Senior Underwriter | CUO | — |
| Claim with fraud indicators | CCO | CUO + Compliance | — |
| Claim above reserve authority | CCO | CUO | Carrier board (if applicable) |
| Claim above settlement authority | CCO | CUO | Carrier board |
| Coverage dispute | CCO | Compliance + Legal | — |
| Reinsurance treaty near capacity | RI Manager | CFO + CUO | — |
| Cession calculation anomaly | RI Manager | CFO | — |
| Bias flag from monitoring | Compliance Officer | CUO | Board |
| Agent error rate spike | Operations Lead | Product Manager | Platform Admin |
| Integration failure | Operations Lead | Platform Admin | — |
| Regulatory change impacting ops | Compliance Officer | CUO | Board |
| Data breach / security incident | Platform Admin | Compliance | CEO + Board |
| Agent anomalous outputs | Operations Lead | Product Manager | Compliance (can halt) |
| MGA authority breach | DA Manager | CUO | Compliance + Legal |
| MGA performance deterioration | DA Manager | CUO | — |
| MGA bordereaux discrepancy | DA Manager | Finance + Compliance | — |
| Reserve adequacy concern | Chief Actuary | CFO + CUO | Board/Audit Committee |
| Statutory filing deadline risk | Compliance | CFO | CEO |
| Catastrophe accumulation breach | RI Manager + CUO | CFO | Board |

---

## 8. Configuration Requirements

### 8.1 Per-Deployment Configurable Parameters

**Deployment Type Selection:**
```json
{
  "deploymentType": "carrier",
  "enabledModules": {
    "underwriting": true,
    "policyAdmin": true,
    "claims": true,
    "billing": true,
    "compliance": true,
    "actuarial": true,
    "reinsurance": true,
    "mgaOversight": true,
    "statutoryReporting": true,
    "investmentIntegration": false
  },
  "organizationalStructure": {
    "multiLOB": true,
    "linesOfBusiness": ["cyber", "property", "professional_liability"],
    "territories": ["US", "EU_DACH", "UK"],
    "businessUnits": [
      {"id": "bu-cyber", "name": "Cyber Division", "lob": ["cyber"]},
      {"id": "bu-prop", "name": "Property Division", "lob": ["property"]}
    ]
  }
}
```

**MGA deployment uses the same schema with reduced modules:**
```json
{
  "deploymentType": "mga",
  "enabledModules": {
    "underwriting": true,
    "policyAdmin": true,
    "claims": true,
    "billing": true,
    "compliance": true,
    "actuarial": false,
    "reinsurance": false,
    "mgaOversight": false,
    "statutoryReporting": false,
    "investmentIntegration": false
  },
  "organizationalStructure": {
    "multiLOB": false,
    "linesOfBusiness": ["cyber"],
    "territories": ["US_excl_NY_CA"],
    "businessUnits": []
  },
  "carrierRelationship": {
    "carrierId": "carrier-xyz",
    "bindingAuthorityAgreement": "ref-to-document",
    "authorityLimits": {
      "maxSingleRiskLimit": 5000000,
      "maxAggregateGWP": 50000000
    },
    "reportingRequirements": {
      "bordereaux": "monthly",
      "largeLossThreshold": 100000,
      "referralRequired": ["excess_layer", "limit_above_5M"]
    }
  }
}
```

**Authority Configuration:**
```json
{
  "autoBindAuthority": {
    "maxPremium": 25000,
    "maxLimit": 1000000,
    "excludedRiskClasses": ["excess_layer", "manuscript_policy"],
    "requiresSubjectivitiesMet": true,
    "requiresPremiumPayment": true
  },
  "roles": {
    "senior_underwriter_1": {
      "maxBindLimit": 2000000,
      "maxPremium": 100000,
      "linesOfBusiness": ["cyber"],
      "territories": ["US_all_states", "EU_DACH"]
    },
    "lob_head_cyber": {
      "maxBindLimit": 10000000,
      "maxPremium": 500000,
      "linesOfBusiness": ["cyber"],
      "territories": ["all"]
    },
    "cuo": {
      "maxBindLimit": null,
      "maxPremium": null,
      "linesOfBusiness": ["all"],
      "territories": ["all"]
    }
  },
  "claimsAuthority": {
    "adjuster_default": {"maxSettlement": 25000, "maxReserve": 100000},
    "cco": {"maxSettlement": 500000, "maxReserve": null},
    "cuo": {"maxSettlement": null, "maxReserve": null}
  },
  "reinsuranceAuthority": {
    "ri_manager": {
      "maxFacultativePlacement": 5000000,
      "canModifyTreatyTerms": false
    }
  }
}
```

**Agent Behavior Configuration:**
```json
{
  "submissionTriage": {
    "autoDeclineEnabled": true,
    "autoDeclineReasons": ["excluded_territory", "excluded_industry", "below_minimum_premium"],
    "escalationConfidenceThreshold": 0.75,
    "maxAutoProcessingPremium": 50000
  },
  "claimsTriage": {
    "fraudCheckEnabled": true,
    "fraudAlertThreshold": 0.65,
    "autoReserveMaxAmount": 25000,
    "largeLossReportingThreshold": 100000
  },
  "reinsurance": {
    "autoCessionEnabled": true,
    "capacityAlertThreshold": 0.80,
    "facReferralTriggers": ["outside_treaty_scope", "above_treaty_limit"]
  },
  "actuarial": {
    "reserveReviewFrequency": "quarterly",
    "autoTriangleGeneration": true,
    "reserveDeviationAlertThreshold": 0.15
  },
  "mgaOversight": {
    "bordereauxValidationAutomatic": true,
    "auditSamplePercentage": 5,
    "performanceAlertThresholds": {
      "lossRatio": 0.65,
      "authorityUtilization": 0.90
    }
  },
  "communication": {
    "autoDeclinationLetterEnabled": false,
    "quoteFollowUpDays": [7, 14, 21],
    "renewalNoticesDaysBefore": [90, 60, 30]
  }
}
```

**Compliance Configuration:**
```json
{
  "euAiAct": {
    "enabled": true,
    "highRiskSystemClassification": true,
    "decisionRecordRetentionYears": 10,
    "biasMonitoringFrequency": "monthly",
    "protectedAttributes": ["industry", "geography", "company_size"],
    "disparateImpactThreshold": 0.80
  },
  "statutoryReporting": {
    "enabled": true,
    "jurisdictions": ["DE_BaFin", "US_NAIC"],
    "filingCalendar": [
      {"filing": "annual_statement", "deadline": "March 1", "jurisdiction": "US_NAIC"},
      {"filing": "solvency_report", "deadline": "April 30", "jurisdiction": "DE_BaFin"}
    ]
  },
  "auditTrailRetentionYears": 7
}
```

### 8.2 Deployment Profiles

Pre-built configuration profiles:

**Profile: Mid-Size P&C Carrier (Primary Target)**
- All modules enabled including actuarial, reinsurance, MGA oversight, statutory reporting
- Multi-LOB organizational structure with LOB Head personas
- Full authority hierarchy (agent → analyst → Sr UW → LOB Head → CUO)
- Comprehensive compliance (multi-jurisdiction, EU AI Act, Solvency II)
- Carrier portal for reinsurer access
- MGA oversight dashboards
- Investment integration hooks (data feeds, not portfolio management)

**Profile: Specialty Carrier / Mono-Line**
- All carrier modules, single LOB
- Simpler hierarchy (no LOB Head layer — Sr UW reports to CUO directly)
- Focused compliance (fewer jurisdictions)
- Potentially no MGA oversight (if direct-writing only)

**Profile: Established MGA**
- Core modules only (no actuarial, reinsurance, MGA oversight, statutory)
- Moderate auto-bind authority
- Full broker portal
- Carrier reporting (bordereaux, referrals)
- Multi-jurisdiction compliance

**Profile: Startup MGA**
- Core modules, single LOB
- Broad auto-bind (fewer humans in loop)
- Minimal hierarchy (CUO + 1-2 underwriters + claims)
- Simple compliance (single jurisdiction)

**Profile: Lloyd's Coverholder**
- Core modules + enhanced compliance
- Lloyd's-specific reporting (bordereaux per syndicate)
- Restricted auto-bind (coverholder agreements require human oversight)
- Carrier portal with real-time syndicate oversight
- Strict audit trail for delegated authority compliance

---

## 9. Implementation Priority for Agents

### Phase 1 — Foundation (Weeks 1-4)

**Priority 1: Core RBAC and Deployment Configuration**
- Entra ID role definitions for all personas (carrier and MGA)
- Module enable/disable based on deployment type
- Data access scoping per role
- Authority configuration engine
- Authentication for all surfaces (web, Teams, portal)

**Priority 2: Submission-to-Quote Workflow**
- Submission intake agent with extraction
- Triage agent with appetite checking
- Underwriter workbench (CUO, LOB Head, Sr UW personas)
- Quote generation and issuance
- Authority management and escalation routing

### Phase 2 — Core Operations (Weeks 5-8)

**Priority 3: Policy Administration**
- Bind workflow with authority checking
- Policy document generation
- Endorsement processing
- Renewal identification and processing

**Priority 4: Claims Workflow**
- FNOL intake agent
- Coverage verification
- Reserve setting with authority chain
- Claims dashboard (CCO persona)
- Adjuster workbench

**Priority 5: Broker Portal**
- Submission upload and tracking
- Quote retrieval and documents
- Policy and claims views
- Commission statements

### Phase 3 — Carrier-Specific (Weeks 9-14)

**Priority 6: Reinsurance Module**
- Treaty management data model
- Auto-cession calculation on bind
- Treaty utilization tracking
- Bordereaux generation for reinsurers
- Recovery calculation on claims
- Reinsurer portal (read-only + fac workflow)
- RI Manager dashboard

**Priority 7: Actuarial Module**
- Loss development triangle generation
- IBNR estimation (standard methods)
- Reserve adequacy analysis
- Rate adequacy tools
- Actuarial workbench and review workflow
- Integration with reserve booking in finance

**Priority 8: MGA Oversight Module**
- Bordereaux ingestion and validation
- Authority compliance checking
- Performance monitoring dashboards
- Underwriting audit sampling
- DA Manager workbench
- MGA external portal

**Priority 9: Statutory Reporting**
- Regulatory filing data compilation
- Report generation per jurisdiction
- Review and certification workflow
- Filing submission tracking

### Phase 4 — Integration & Polish (Weeks 13-16)

**Priority 10: Compliance and Audit**
- Decision record logging (running from Phase 1, formalized here)
- Compliance dashboard
- Bias monitoring
- EU AI Act documentation generation
- Auditor portal with scoped access

**Priority 11: M365 Integration**
- Copilot Studio topic configuration for all personas
- M365 Copilot publishing
- Teams integration
- Outlook integration for submission intake
- Excel integration for actuarial and finance workflows

**Priority 12: Finance**
- Billing engine and payment processing
- Commission calculation
- Carrier bordereaux generation (MGA deployments)
- General ledger integration hooks
- Cash flow reporting

---

## Appendix: Persona Quick Reference

| Persona | Tag | Entra ID Role | Primary Surface | Authority |
|---|---|---|---|---|
| CEO | BOTH | openinsure-ceo | Teams, Executive Dashboard | Unlimited, delegates |
| CUO | BOTH | openinsure-cuo | Teams, Portfolio Dashboard | Unlimited underwriting |
| LOB Head | CARRIER | openinsure-lob-head | Teams, LOB Dashboard | Within LOB limits |
| Senior Underwriter | BOTH | openinsure-senior-underwriter | Teams, UW Workbench | Delegated limits |
| UW Analyst | BOTH | openinsure-uw-analyst | Teams, Workbench (limited) | Renewals, limited |
| Chief Actuary | CARRIER | openinsure-chief-actuary | Teams, Actuarial Workbench | Reserve authority |
| Actuary | CARRIER | openinsure-actuary | Teams, Actuarial Views | LOB reserves (subject to CA) |
| CCO / Claims Mgr | BOTH | openinsure-claims-manager | Teams, Claims Dashboard | Settlement ceiling |
| Claims Adjuster | BOTH | openinsure-claims-adjuster | Teams, Claims View | Per-claim limit |
| CFO | BOTH | openinsure-cfo | Teams, Financial Dashboard | Financial operations |
| Finance Lead | BOTH | openinsure-finance | Teams, Excel, Dashboard | Financial reporting |
| Reinsurance Mgr | CARRIER | openinsure-reinsurance-manager | Teams, RI Dashboard | RI operations |
| Compliance Officer | BOTH | openinsure-compliance | Teams, Compliance Dashboard | Can suspend agents |
| DA Manager | CARRIER | openinsure-da-manager | Teams, MGA Oversight Dashboard | Suspend MGA authority |
| Product Manager | BOTH | openinsure-product-manager | Teams, Foundry, Dashboard | Agent configuration |
| Platform Admin | BOTH | openinsure-platform-admin | Admin Dashboard, Foundry | Full platform, zero insurance |
| Operations Lead | BOTH | openinsure-operations | Teams, Ops Dashboard | Operational restart |
| Broker | EXTERNAL | openinsure-broker | Broker Portal, Email, API | Submit and request |
| MGA (external) | CARRIER-EXT | openinsure-mga-external | MGA Portal, API | Within authority |
| Policyholder | EXTERNAL | openinsure-policyholder | Policyholder Portal | View + report |
| Reinsurer | CARRIER-EXT | openinsure-reinsurer | Reinsurer Portal, API | Fac approval |
| Regulator/Auditor | EXTERNAL | openinsure-auditor | Audit Portal | Time-limited read |
| Vendor | EXTERNAL | openinsure-vendor | Vendor Portal | Assigned cases |
