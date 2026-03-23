# OpenInsure Process Flows

> End-to-end workflow documentation for the OpenInsure platform.
> Covers agent architecture, insurance processes, role-based access, integration architecture, and escalation rules.

---

## Table of Contents

- [Agent Architecture](#agent-architecture)
  - [Agent Overview](#agent-overview)
  - [Agent Authority Limits](#agent-authority-limits)
  - [Agent Execution Model](#agent-execution-model)
- [New Business Workflow](#new-business-workflow)
- [Claims Workflow](#claims-workflow)
- [Renewal Workflow](#renewal-workflow)
- [Escalation Framework](#escalation-framework)
- [Role-Based Access Control](#role-based-access-control)
  - [Navigation Access Matrix](#navigation-access-matrix)
  - [Authority Matrix](#authority-matrix)
- [Integration Architecture](#integration-architecture)

---

## Agent Architecture

### Agent Overview

OpenInsure uses eight AI agents deployed on Microsoft Foundry (GPT-5.1), orchestrated by a workflow engine. Every agent decision produces an immutable `DecisionRecord` for EU AI Act compliance.

```mermaid
graph TB
    subgraph "User Interfaces"
        D[React Dashboard<br/>25 pages]
        BP[Broker Portal]
        M365[M365 Copilot / Teams]
    end

    subgraph "Backend — FastAPI"
        API[REST API<br/>118 endpoints]
        WE[Workflow Engine]
        FC[Foundry Client]
    end

    subgraph "Microsoft Foundry — GPT-5.1"
        O[openinsure-orchestrator<br/>Workflow coordination]
        S[openinsure-submission<br/>Intake & triage]
        U[openinsure-underwriting<br/>Risk & pricing]
        P[openinsure-policy<br/>Bind & servicing]
        C[openinsure-claims<br/>FNOL & reserves]
        CO[openinsure-compliance<br/>EU AI Act audit]
        DOC[openinsure-document<br/>Document intelligence]
        K[openinsure-knowledge<br/>Knowledge graph queries]
    end

    subgraph "Data Layer"
        SQL[(Azure SQL<br/>26 tables)]
        Cosmos[(Cosmos DB<br/>Knowledge Graph)]
        Blob[Blob Storage<br/>Documents]
        Search[AI Search<br/>Hybrid Index]
    end

    D & BP & M365 --> API
    API --> WE
    WE --> FC
    FC --> O & S & U & P & C & CO & DOC & K
    API --> SQL
    K --> Cosmos
    DOC --> Blob
    DOC --> Search

    style O fill:#e74c3c,color:#fff
    style S fill:#3498db,color:#fff
    style U fill:#2ecc71,color:#fff
    style P fill:#9b59b6,color:#fff
    style C fill:#e67e22,color:#fff
    style CO fill:#1abc9c,color:#fff
    style DOC fill:#f39c12,color:#fff
    style K fill:#34495e,color:#fff
```

### Agent Authority Limits

Each agent has a configured authority limit. Actions above this threshold trigger escalation to a human approver.

| Agent | Authority Limit | Auto-Execute | Escalation Threshold | Key Capabilities |
|-------|----------------|--------------|---------------------|------------------|
| **Submission Agent** | $0 (recommend only) | No | 0.7 confidence | Intake, classify documents, extract data, validate, triage |
| **Underwriting Agent** | $1,000,000 | Yes (within limit) | 0.7 confidence | Risk assessment, pricing, terms generation, authority check, quote |
| **Claims Agent** | $250,000 | Yes (within limit) | 0.7 confidence | FNOL intake, coverage verification, reserves, triage, investigation support |
| **Policy Agent** | $5,000,000 | Yes (within limit) | 0.7 confidence | Bind, endorse, renew, cancel |
| **Compliance Agent** | $0 (audit only) | No | 0.7 confidence | Compliance check, audit report, bias monitoring, EU AI Act documentation |
| **Document Agent** | $0 (no authority) | No | 0.7 confidence | Classify, extract, generate documents |
| **Knowledge Agent** | — | — | — | Guidelines, knowledge queries, regulatory rules, product definitions |
| **Orchestrator** | — | — | — | Coordinate multi-agent workflows |

> **Escalation trigger:** When any agent's confidence score falls below **0.7**, the workflow is escalated to a human for review.

### Agent Execution Model

```mermaid
flowchart TD
    A[Workflow Engine<br/>receives task] --> B{Foundry<br/>available?}
    B -->|Yes| C[Invoke Foundry Agent<br/>via Agents API]
    B -->|No| D[Execute Local Fallback<br/>conservative defaults]
    C --> E[Wrap Response]
    D --> E
    E --> F[Create DecisionRecord<br/>EU AI Act Art. 12]
    F --> G{Confidence<br/>≥ 0.7?}
    G -->|Yes| H{Within authority<br/>limit?}
    G -->|No| I[Escalate to Human]
    H -->|Yes| J[Auto-execute]
    H -->|No| I
    J --> K[Publish Domain Event<br/>via Service Bus]
    I --> L[Queue in Escalation<br/>await approval]
```

**Local Fallback Behavior:** When Foundry is unavailable, agents return conservative defaults:
- Submission Agent: `ai_mode: "local_fallback"`, manual triage required
- Underwriting Agent: `requires_referral: true`, all-zero pricing
- Claims Agent: `is_covered: false`, unknown severity
- Compliance Agent: `compliant: false`, manual review required

---

## New Business Workflow

### End-to-End Sequence

```mermaid
sequenceDiagram
    participant Broker
    participant Portal as React Dashboard
    participant API as FastAPI Backend
    participant WE as Workflow Engine
    participant Sub as openinsure-submission
    participant Doc as openinsure-document
    participant Know as openinsure-knowledge
    participant UW as openinsure-underwriting
    participant Pol as openinsure-policy
    participant Comp as openinsure-compliance
    participant SQL as Azure SQL
    participant Blob as Blob Storage
    participant Graph as Cosmos DB Graph

    Note over Broker,SQL: Phase 1 — Submission Intake
    Broker->>Portal: Submit application via portal
    Portal->>API: POST /api/v1/submissions
    API->>SQL: INSERT submission (status: received)
    API->>Blob: Store uploaded documents

    Note over WE,SQL: Phase 2 — Document Processing
    API->>WE: Start new_business_workflow
    WE->>Sub: intake(submission_data)
    Sub-->>WE: submission_id, registered
    WE->>Doc: classify_documents(documents)
    Doc-->>WE: document_type, confidence per doc
    WE->>Doc: extract_data(classified_documents)
    Doc-->>WE: structured extracted_data
    WE->>SQL: UPDATE submission.extracted_data

    Note over WE,SQL: Phase 3 — Triage
    WE->>Sub: triage(extracted_data, lob)
    Sub-->>WE: appetite_match, risk_score, priority
    WE->>SQL: UPDATE submission (status: triaging → underwriting)

    alt Appetite = No
        WE->>SQL: UPDATE submission (status: declined)
        WE-->>Portal: Decline notification
        Portal-->>Broker: Submission declined
    end

    Note over WE,SQL: Phase 4 — Underwriting
    WE->>Know: get_guidelines(lob)
    Know->>Graph: Query appetite rules, rating factors
    Graph-->>Know: Guidelines, exclusions, factors
    Know-->>WE: Underwriting guidelines
    WE->>UW: assess_risk(extracted_data, lob)
    UW-->>WE: risk_score, risk_factors
    WE->>UW: price_submission(risk_assessment, lob)
    UW-->>WE: recommended_premium, rate_used
    WE->>UW: generate_terms(risk, pricing)
    UW-->>WE: limits, deductibles, premium
    WE->>UW: check_authority(terms)

    alt Within Auto-Bind Authority
        UW-->>WE: within_limit: true
    else Above Authority
        UW-->>WE: requires_referral: true
        WE->>SQL: INSERT escalation_queue
        Note over Portal: Senior UW reviews & approves
    end

    WE->>SQL: UPDATE submission (status: quoted, quoted_premium)
    WE-->>Portal: Quote ready
    Portal-->>Broker: Quote presented

    Note over WE,SQL: Phase 5 — Bind
    Broker->>Portal: Accept quote
    Portal->>API: POST /api/v1/submissions/{id}/process
    WE->>Pol: bind(submission, terms)
    Pol-->>WE: policy_number, status: active
    WE->>SQL: INSERT policy + coverages
    WE->>SQL: UPDATE submission (status: bound)
    WE->>SQL: INSERT billing_account + invoices

    Note over WE,SQL: Phase 6 — Compliance Audit
    WE->>Comp: check_compliance(all_decision_records)
    Comp-->>WE: compliant: true/false, findings
    WE->>SQL: INSERT decision_records (all agent decisions)
    WE->>SQL: INSERT audit_events
    WE-->>Portal: Workflow complete
    Portal-->>Broker: Policy documents available
```

### Step-by-Step Detail

| Step | Agent | Action | Data Stored | User Sees |
|------|-------|--------|-------------|-----------|
| 1. Submit | — | Broker submits via portal or API | `submissions` row (status: `received`), documents in Blob | Confirmation with submission number |
| 2. Classify docs | Document Agent | Classify each uploaded document | `submission_documents` rows with type & confidence | Document types listed |
| 3. Extract data | Document Agent | Extract structured data from documents | `submissions.extracted_data` updated | Extracted fields shown |
| 4. Triage | Submission Agent | Evaluate appetite, score risk, set priority | `submissions.triage_result`, status → `triaging` | Risk score, appetite match |
| 5. Guidelines | Knowledge Agent | Fetch UW guidelines from knowledge graph | — (in-memory) | — |
| 6. Risk assessment | Underwriting Agent | Multi-factor risk assessment | — (in workflow context) | Risk factors displayed |
| 7. Pricing | Underwriting Agent | Calculate premium (base rate $1.50/$1K revenue) | `submissions.quoted_premium` | Premium breakdown |
| 8. Terms | Underwriting Agent | Generate coverage limits & deductibles | — (in workflow context) | Coverage details |
| 9. Authority check | Underwriting Agent | Verify within auto-bind authority | Escalation if above limit | Referral notice (if needed) |
| 10. Quote | — | Status updated to `quoted` | Status → `quoted` | Quote document ready |
| 11. Bind | Policy Agent | Create policy from bound submission | `policies` + `policy_coverages` rows | Policy number issued |
| 12. Billing | — | Create billing account & invoices | `billing_accounts` + `invoices` rows | Invoice details |
| 13. Compliance | Compliance Agent | Audit all decision records | `decision_records` rows | Compliance status |

### Underwriting Authority Levels

| Level | Max Premium | Max Aggregate Limit | Max Risk Score | Conditions |
|-------|-----------|---------------------|---------------|------------|
| **Auto-bind** (agent) | $25,000 | $2,000,000 | ≤ 5 | No referral triggers |
| **Junior Underwriter** | $100,000 | $5,000,000 | ≤ 7 | Max 1 referral trigger |
| **Senior Underwriter** | $250,000 | $10,000,000 | ≤ 9 | Requires Sr UW sign-off |
| **Committee** | $500,000+ | Unlimited | Any | Committee approval required |

### Referral Triggers

1. Risk score ≥ 8 → Senior UW review
2. Any cyber claim in past 3 years → Request incident report
3. Prior ransomware payment → May require sublimit
4. Revenue > $25M → Capacity review
5. Not PCI DSS compliant (handles card data) → Decline or remediate
6. No MFA for remote access → Decline unless MFA within 60 days
7. Handles PHI → Healthcare specialist review
8. International operations → Territory & regulatory review

---

## Claims Workflow

### End-to-End Sequence

```mermaid
sequenceDiagram
    participant Claimant
    participant Portal as React Dashboard
    participant API as FastAPI Backend
    participant WE as Workflow Engine
    participant Cl as openinsure-claims
    participant Comp as openinsure-compliance
    participant SQL as Azure SQL

    Note over Claimant,SQL: Phase 1 — First Notice of Loss
    Claimant->>Portal: Report claim
    Portal->>API: POST /api/v1/claims
    API->>SQL: INSERT claim (status: fnol)
    API->>WE: Start claims_workflow

    Note over WE,SQL: Phase 2 — Assessment
    WE->>Cl: intake_fnol(claim_report)
    Cl-->>WE: structured_fnol, claim_number
    WE->>Cl: verify_coverage(fnol, policy)
    Cl-->>WE: is_covered, coverage issues

    alt Not Covered
        WE->>SQL: UPDATE claim (status: denied)
        WE-->>Portal: Coverage denial
        Portal-->>Claimant: Claim denied with reason
    end

    Note over WE,SQL: Phase 3 — Reserving
    WE->>Cl: set_reserves(fnol, coverage_result)
    Cl-->>WE: severity_tier, indemnity_reserve, expense_reserve
    WE->>SQL: INSERT claim_reserves
    WE->>SQL: UPDATE claim (status: reserved)

    Note over WE,SQL: Phase 4 — Triage & Routing
    WE->>Cl: triage_claim(fnol, coverage, reserves)
    Cl-->>WE: severity, fraud_score, routing

    alt Fraud Score > 0.7
        WE->>SQL: Flag for fraud investigation
        Note over Portal: CCO + Compliance review
    end

    alt Severity = complex or catastrophe
        WE->>SQL: Escalate to CCO
    end

    alt Routing = auto_process
        WE->>SQL: UPDATE claim (status: settling)
    else Routing = manual_review
        WE->>SQL: Assign to adjuster
        WE->>SQL: UPDATE claim (status: investigating)
    else Routing = cco_review
        WE->>SQL: Escalate to CCO
    end

    Note over WE,SQL: Phase 5 — Investigation (if required)
    WE->>Cl: support_investigation(claim_id)
    Cl-->>WE: investigation_support, document_analysis

    Note over WE,SQL: Phase 6 — Settlement
    Portal->>API: Adjuster approves settlement
    API->>SQL: INSERT claim_payments
    API->>SQL: UPDATE claim (status: closed)

    Note over WE,SQL: Phase 7 — Compliance
    WE->>Comp: check_compliance(decision_records)
    Comp-->>WE: compliant, findings
    WE->>SQL: INSERT decision_records
    WE->>SQL: INSERT audit_events
```

### Severity Tiers & Routing

| Severity | Description | Reserve Range | Routing | Authority |
|----------|-------------|--------------|---------|-----------|
| **Simple** | Straightforward, clear coverage | <$25,000 | Auto-process | Claims Agent |
| **Moderate** | Multiple factors, some ambiguity | $25K–$100K | Adjuster review | Adjuster ($25K limit) |
| **Complex** | Coverage disputes, large exposure | $100K–$500K | CCO review | CCO ($500K limit) |
| **Catastrophe** | Systemic event, multiple claims | >$500K | CCO + CUO | Board approval |

### Fraud Detection Indicators

The Claims Agent evaluates these red flags and produces a fraud score (0.0–1.0):
- Recent policy inception (< 90 days before loss)
- Late reporting (> 30 days after loss)
- Revenue/employee mismatch with claimed damage
- Frequent claims history
- Inconsistent loss descriptions
- Known fraud patterns (ransomware payment demands matching known schemes)

> **Threshold:** Fraud score > 0.7 triggers mandatory CCO + Compliance review.

---

## Renewal Workflow

### End-to-End Sequence

```mermaid
sequenceDiagram
    participant System as Renewal Detection
    participant WE as Workflow Engine
    participant UW as openinsure-underwriting
    participant Pol as openinsure-policy
    participant Comp as openinsure-compliance
    participant SQL as Azure SQL
    participant Portal as React Dashboard
    participant Broker

    Note over System,SQL: Phase 1 — Detection (90/60/30-day flags)
    System->>SQL: Query policies expiring in 90 days
    SQL-->>System: Expiring policies list
    System->>SQL: INSERT renewal_records (status: pending)

    Note over WE,SQL: Phase 2 — Terms Generation
    WE->>UW: assess_renewal(policy, claims_history)
    UW-->>WE: renewal_premium, rate_change_pct, recommendation
    WE->>SQL: UPDATE renewal_record (status: terms_generated)

    Note over WE,SQL: Phase 3 — Compliance Check
    WE->>Comp: check_compliance(decision_records)
    Comp-->>WE: compliant, findings

    Note over Portal,Broker: Phase 4 — Offer
    WE->>SQL: UPDATE renewal_record (status: offered)
    Portal-->>Broker: Renewal terms presented

    alt Broker Accepts
        Broker->>Portal: Accept renewal
        Portal->>WE: Process acceptance
        WE->>Pol: renew(policy, renewal_terms)
        Pol-->>WE: new_policy_number
        WE->>SQL: INSERT new policy
        WE->>SQL: UPDATE renewal_record (status: accepted)
        WE->>SQL: UPDATE original policy (status: expired)
    else Broker Declines
        Broker->>Portal: Decline renewal
        WE->>SQL: UPDATE renewal_record (status: declined)
    else No Response
        System->>SQL: UPDATE renewal_record (status: lapsed)
    end
```

### Renewal Pricing Logic

The renewal factor is calculated based on the expiring policy's claims experience:

```mermaid
flowchart LR
    A[Expiring Policy] --> B{Claims History}
    B -->|No claims| C[0.95× — 5% discount]
    B -->|1 claim or < $25K| D[1.05× — 5% increase]
    B -->|1-2 claims or $25K-$100K| E[1.10× — 10% increase]
    B -->|2+ claims or $100K-$500K| F[1.20× — 20% increase]
    B -->|3+ claims or > $500K| G[1.35× — 35% increase]
    C & D & E & F & G --> H[Renewal Premium =<br/>Expiring Premium × Factor]
```

---

## Escalation Framework

### Escalation Triggers

```mermaid
flowchart TD
    A[Agent Decision] --> B{Check Escalation<br/>Conditions}

    B -->|Confidence < 0.7| C[Low Confidence<br/>Escalation]
    B -->|Above authority limit| D[Authority<br/>Escalation]
    B -->|Fraud indicators| E[Fraud<br/>Escalation]
    B -->|Bias flag detected| F[Compliance<br/>Escalation]
    B -->|Reinsurance capacity > 80%| G[Capacity<br/>Escalation]
    B -->|All checks pass| H[Auto-Execute]

    C --> I[Queue for Human Review]
    D --> I
    E --> J[CCO + Compliance]
    F --> K[Compliance → CUO → Board]
    G --> L[RI Manager → CFO + CUO]
```

### Escalation Matrix

| Trigger | First Escalation | Second Escalation | Emergency |
|---------|-----------------|-------------------|-----------|
| Submission outside appetite | Senior UW | LOB Head / CUO | — |
| Quote above auto-authority | Authority holder | LOB Head / CUO | — |
| Claim with fraud indicators | CCO | CUO + Compliance | — |
| Claim above settlement authority | CCO | CUO | Board (if applicable) |
| Reinsurance treaty near 80% capacity | RI Manager | CFO + CUO | — |
| Bias flag detected (disparate impact < 0.80) | Compliance | CUO | Board |
| MGA authority breach | DA Manager | CUO | Compliance + Legal |
| Reserve adequacy concern | Chief Actuary | CFO + CUO | Board / Audit Committee |
| Agent confidence < 0.7 | Responsible human role | Next authority level | — |

### Human-Agent Authority Matrix

| Complexity | Low Consequence | Medium Consequence | High Consequence | Critical |
|------------|----------------|-------------------|-----------------|----------|
| **Routine** | Agent auto-executes | Agent auto-executes, logs | Agent executes, human notified | Agent prepares, human approves |
| **Standard** | Agent auto-executes | Agent recommends, human confirms | Agent recommends, human approves | Human decides, agent assists |
| **Complex** | Agent recommends, human confirms | Agent recommends, human approves | Human decides, agent assists | Human decides, agent assists, peer review |
| **Novel** | Agent researches, human decides | Human decides, agent assists | Human decides, agent assists, CUO approval | Board/committee decision |

---

## Role-Based Access Control

### Navigation Access Matrix

Configured in `dashboard/src/context/AuthContext.tsx` via the `NAV_ACCESS` object.

| Route | CEO | CUO | Sr UW | UW Analyst | CCO | Adjuster | CFO | Compliance | Product Mgr | Operations | Broker |
|-------|:---:|:---:|:-----:|:----------:|:---:|:--------:|:---:|:----------:|:-----------:|:----------:|:------:|
| `/` Dashboard | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| `/submissions` | — | ✅ | ✅ | ✅ | — | — | — | — | ✅ | ✅ | — |
| `/policies` | — | ✅ | ✅ | ✅ | ✅ | — | ✅ | ✅ | — | — | — |
| `/claims` | — | ✅ | — | — | ✅ | ✅ | — | ✅ | — | — | — |
| `/decisions` | ✅ | ✅ | — | — | — | — | — | ✅ | ✅ | — | — |
| `/escalations` | ✅ | ✅ | ✅ | — | ✅ | ✅ | ✅ | — | — | — | — |
| `/compliance` | ✅ | ✅ | — | — | — | — | — | ✅ | — | — | — |
| `/finance` | ✅ | — | — | — | — | — | ✅ | — | — | ✅ | — |
| `/workbench/underwriting` | — | ✅ | ✅ | ✅ | — | — | — | — | — | — | — |
| `/workbench/claims` | — | — | — | — | ✅ | ✅ | — | — | — | — | — |
| `/workbench/compliance` | — | — | — | — | — | — | — | ✅ | — | — | — |
| `/workbench/reinsurance` | — | ✅ | — | — | — | — | ✅ | — | — | — | — |
| `/workbench/actuarial` | ✅ | ✅ | — | — | — | — | ✅ | — | ✅ | — | — |
| `/executive` | ✅ | ✅ | — | — | — | — | ✅ | — | — | — | — |
| `/portal/broker` | — | — | — | — | — | — | — | — | — | — | ✅ |

### Default Landing Pages

| Role | Default Route | Landing Page |
|------|--------------|--------------|
| CEO — Alexandra Reed | `/executive` | Executive Dashboard |
| CUO — Sarah Chen | `/` | Main Dashboard |
| Senior UW — James Wright | `/workbench/underwriting` | Underwriter Workbench |
| UW Analyst — Maria Lopez | `/workbench/underwriting` | Underwriter Workbench |
| CCO — David Park | `/workbench/claims` | Claims Workbench |
| Adjuster — Lisa Martinez | `/workbench/claims` | Claims Workbench |
| CFO — Michael Torres | `/executive` | Executive Dashboard |
| Compliance — Anna Kowalski | `/workbench/compliance` | Compliance Workbench |
| Product Mgr — Robert Chen | `/` | Main Dashboard |
| Operations — Emily Davis | `/finance` | Finance Dashboard |
| Broker — Thomas Anderson | `/portal/broker` | Broker Portal |

### Authority Matrix

| Role | Bind Authority | Settlement Authority | Reserve Authority | Key Actions |
|------|---------------|---------------------|-------------------|-------------|
| **CEO** | Unlimited | Unlimited | Unlimited | Strategic decisions, override any escalation |
| **CUO** | Unlimited (all LOBs) | — | — | Approve all underwriting, suspend agents |
| **Senior UW** | Up to $2M limits | — | — | Bind within authority, approve referrals |
| **UW Analyst** | Renewals only, co-sign new | — | — | Process renewals, assist new business |
| **CCO** | — | Up to $500K | Unlimited | Approve settlements, manage adjusters |
| **Adjuster** | — | Up to $25K | Up to $250K | Process simple claims, set reserves |
| **CFO** | — | — | — | Financial reporting, no operational authority |
| **Compliance** | — | — | — | Full audit access, can suspend agents |
| **Product Mgr** | — | — | — | Configure agents, manage knowledge graph |
| **Operations** | — | — | — | System monitoring, operational metrics |
| **Broker** | — | — | — | Submit applications, view own policies/claims |

---

## Integration Architecture

### System Overview

```mermaid
graph TB
    subgraph "User Layer"
        D[React Dashboard<br/>Vite + TypeScript]
        M365[M365 Copilot<br/>Teams Integration]
    end

    subgraph "Application Layer"
        API[FastAPI Backend<br/>Python 3.12+<br/>118 REST Endpoints]
        WE[Workflow Engine<br/>Multi-Agent Orchestration]
        MCP[MCP Server<br/>Tool Interface]
    end

    subgraph "AI Layer — Microsoft Foundry"
        F1[openinsure-orchestrator]
        F2[openinsure-submission]
        F3[openinsure-underwriting]
        F4[openinsure-policy]
        F5[openinsure-claims]
        F6[openinsure-compliance]
        F7[openinsure-document]
        F8[openinsure-knowledge]
    end

    subgraph "Data Layer — Azure"
        SQL[(Azure SQL<br/>Transactional Data<br/>26 tables)]
        Cosmos[(Cosmos DB — Gremlin<br/>Knowledge Graph)]
        CosmosNS[(Cosmos DB — NoSQL<br/>Semi-structured Docs)]
        Blob[Azure Blob Storage<br/>Document Storage]
        Search[Azure AI Search<br/>Hybrid Vector + Keyword]
    end

    subgraph "Event Layer — Azure"
        SB[Service Bus<br/>Pub/Sub Topics]
        EG[Event Grid<br/>Domain Events]
    end

    subgraph "Security & Monitoring"
        KV[Key Vault<br/>Secrets]
        Entra[Entra ID<br/>Authentication]
        AI_Mon[Application Insights<br/>OpenTelemetry]
        DocInt[Document Intelligence<br/>OCR + Extraction]
    end

    D --> API
    M365 --> MCP --> API
    API --> WE
    WE --> F1 & F2 & F3 & F4 & F5 & F6 & F7 & F8
    API --> SQL
    F8 --> Cosmos
    F7 --> Blob & DocInt
    API --> CosmosNS
    API --> Search
    API --> SB
    API --> EG
    API -.-> KV
    API -.-> Entra
    API -.-> AI_Mon

    style SQL fill:#4a9eff,color:#fff
    style Cosmos fill:#4a9eff,color:#fff
    style CosmosNS fill:#4a9eff,color:#fff
    style Blob fill:#4a9eff,color:#fff
    style Search fill:#4a9eff,color:#fff
    style SB fill:#2ecc71,color:#fff
    style EG fill:#2ecc71,color:#fff
    style KV fill:#e74c3c,color:#fff
    style Entra fill:#e74c3c,color:#fff
```

### Data Flow by Service

| Azure Service | Purpose | Data Stored | Access Pattern |
|--------------|---------|-------------|----------------|
| **Azure SQL** | Transactional data | All 26 tables — parties, submissions, policies, claims, billing, reinsurance, actuarial, compliance | Async pyodbc, Entra-only auth, private endpoint, connection pooling (5 connections) |
| **Cosmos DB (Gremlin)** | Knowledge graph | Underwriting guidelines, product definitions, rating factors, regulatory rules, compliance mappings | Graph traversal via Gremlin, used by Knowledge Agent |
| **Cosmos DB (NoSQL)** | Semi-structured docs | Knowledge base documents | Document queries |
| **Blob Storage** | Document storage | Submission documents, policy certificates, claim evidence, quote documents | Upload/download via managed identity, private endpoint |
| **AI Search** | Full-text & semantic search | Indexed documents, decision history, compliance audit logs | Hybrid vector + keyword search |
| **Service Bus** | Event messaging | Domain events (pub/sub) | Async publish to topics |
| **Event Grid** | Event routing | Domain events → functions, logic apps, webhooks | Event-driven triggers |
| **Document Intelligence** | Document processing | — (processes documents in-place) | OCR + structured extraction from ACORD forms, loss runs, financial statements |
| **Application Insights** | Telemetry | Traces, metrics, logs | OpenTelemetry instrumentation, structured logging via structlog |
| **Key Vault** | Secrets management | API keys, connection strings | Referenced at runtime, never hardcoded |
| **Entra ID** | Identity & access | User identities, managed identities, RBAC assignments | DefaultAzureCredential for all service-to-service auth |

### Domain Events (Service Bus Topics)

```mermaid
graph LR
    subgraph "Publishers"
        S[Submission Service]
        P[Policy Service]
        C[Claims Service]
        W[Workflow Engine]
    end

    subgraph "Service Bus Topics"
        T1[submission.received]
        T2[submission.triaged]
        T3[submission.quoted]
        T4[submission.bound]
        T5[policy.bound]
        T6[policy.renewed]
        T7[policy.cancelled]
        T8[claim.reported]
        T9[claim.reserved]
        T10[claim.settled]
        T11[claim.closed]
    end

    subgraph "Subscribers"
        WE[Workflow Engine]
        BI[Billing Service]
        RI[Reinsurance Service]
        AU[Audit Service]
        NT[Notification Service]
    end

    S --> T1 & T2 & T3 & T4
    P --> T5 & T6 & T7
    C --> T8 & T9 & T10 & T11
    T1 & T2 & T3 & T4 --> WE & AU
    T5 --> BI & RI & AU & NT
    T6 --> BI & AU & NT
    T7 --> BI & AU & NT
    T8 & T9 & T10 & T11 --> AU & NT
    T9 --> RI
```

### Infrastructure as Code

All Azure resources are deployed via Bicep templates in `infra/`:

```
infra/
├── main.bicep              # Root deployment (resource group scope)
└── modules/
    ├── monitoring.bicep     # App Insights + Log Analytics
    ├── storage.bicep        # Blob Storage (private endpoint)
    ├── cosmos.bicep          # Cosmos DB Gremlin (knowledge graph)
    ├── sql.bicep            # Azure SQL (Entra-only, VNet, private endpoint)
    ├── search.bicep         # AI Search (hybrid vector + keyword)
    ├── servicebus.bicep     # Service Bus namespace
    ├── eventgrid.bicep      # Event Grid topic
    └── identity.bicep       # RBAC role assignments (least privilege)
```

**Security model:**
- User-assigned managed identity for all service-to-service communication
- No hardcoded credentials — all via `DefaultAzureCredential`
- Private endpoints for SQL, Cosmos DB, Blob Storage, and AI Search
- Entra ID-only admin for Azure SQL (no SQL auth)
- Least-privilege RBAC assignments per service

### API Structure

All API endpoints are prefixed with `/api/v1/` and organized into 21 route modules:

| Module | Prefix | Endpoints | Description |
|--------|--------|-----------|-------------|
| `health` | `/health` | 1 | Health check |
| `submissions` | `/api/v1/submissions` | 4 | CRUD + process submissions |
| `policies` | `/api/v1/policies` | 3 | CRUD policies |
| `claims` | `/api/v1/claims` | 4 | CRUD + process claims |
| `renewals` | `/api/v1/renewals` | — | Renewal management |
| `billing` | `/api/v1/billing` | — | Billing accounts & invoices |
| `finance` | `/api/v1/finance` | 4 | Summary, cashflow, commissions, reconciliation |
| `products` | `/api/v1/products` | — | Product definitions |
| `knowledge` | `/api/v1/knowledge` | — | Knowledge graph queries |
| `compliance` | `/api/v1/compliance` | 3 | Decisions, audit trail, system inventory |
| `documents` | `/api/v1/documents` | — | Document management |
| `reinsurance` | `/api/v1/reinsurance` | 3 | Treaties, cessions, recoveries |
| `actuarial` | `/api/v1/actuarial` | — | Reserves, loss triangles, rate adequacy |
| `mga` | `/api/v1/mga` | 4 | MGA authorities, bordereaux, performance |
| `events` | `/api/v1/events` | — | Domain event stream |
| `metrics` | `/api/v1/metrics` | 1 | Dashboard summary metrics |
| `escalations` | `/api/v1/escalations` | — | Escalation queue management |
| `workflows` | `/api/v1/workflows` | — | Workflow execution tracking |
| `agent-traces` | `/api/v1/agent-traces` | — | Agent decision traces |
| `underwriter` | `/api/v1/underwriter` | — | UW workbench operations |
| `broker` | `/api/v1/broker` | — | Broker portal API |
| `demo` | `/api/v1/demo` | 1 | Full end-to-end demo workflow |
