# OpenInsure

**AI-Native Open Source Core Insurance Platform**

[![CI](https://github.com/urosstojkic/openinsure/actions/workflows/ci.yml/badge.svg)](https://github.com/urosstojkic/openinsure/actions/workflows/ci.yml)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](https://opensource.org/licenses/AGPL-3.0)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)

> Every module — underwriting, policy administration, claims, billing, compliance — is designed from the ground up to be operated by, and through, AI agents.

📖 **[Full Functional Capabilities →](docs/CAPABILITIES.md)** — Comprehensive description of everything the platform does, written for insurance executives and product managers.

## What Is This?

OpenInsure is an open-source, AI-native core insurance platform built on the Microsoft AI stack (Azure AI Foundry + Azure). It is **not** a traditional core system with AI bolted on — AI is the primary interface and execution engine, with human oversight on exceptions.

**Traditional system:** Human opens screen → fills forms → clicks buttons → reviews output
**OpenInsure:** Agent receives submission → extracts data → assesses risk → generates quote → binds within authority → escalates exceptions to humans

**What's live today:**
- ✅ 8 AI agents (Submission, Underwriting, Policy, Claims, Compliance, Document, Knowledge, Orchestrator) deployed on Azure AI Foundry
- ✅ Microsoft Foundry AI pipeline with ProcessWorkflowModal visualization (step-by-step AI reasoning with confidence scores)
- ✅ 90+ REST API endpoints across 21 modules — submissions, policies, claims, billing, compliance, knowledge, reinsurance, actuarial, MGA oversight, renewals, finance, and demo
- ✅ React dashboard with 22 pages including role-specific workbenches (Executive, Underwriting, Claims, Compliance, Broker Portal, Reinsurance, Actuarial, MGA Oversight, Renewals, Finance)
- ✅ Azure SQL with 3+ years of operations data: 1,384 submissions, 483 policies, 109 claims
- ✅ Carrier-grade modules: reinsurance management, actuarial analytics, MGA oversight, renewal workflow, finance dashboard
- ✅ ACORD 125/126 XML ingestion — parse commercial insurance applications and feed into submission pipeline
- ✅ Azure Document Intelligence integration — OCR + structured extraction from uploaded PDF/image insurance documents
- ✅ Knowledge graph with claims precedents, compliance rules (EU AI Act, GDPR, NAIC), and coverage definitions
- ✅ One-call demo: `POST /api/v1/demo/full-workflow` runs the entire lifecycle (submission → triage → quote → bind → claim → reserve) in ~3ms
- ✅ Cyber Liability SMB product with 5 coverages and configurable rating engine
- ✅ EU AI Act compliance: immutable decision records, bias monitoring (4/5ths rule), audit trail
- ✅ Security hardened: parameterized SQL queries, constant-time auth, production error sanitization, upload size limits
- ✅ Role-based access control with 19 platform roles and authority delegation
- ✅ Azure infrastructure: 13+ resources defined as Bicep IaC
- ✅ 445+ tests with comprehensive E2E lifecycle coverage

### Why OpenInsure?

> *Company names anonymized. OpenInsure's positioning is based on publicly available information about market participants as of early 2026.*

| | Legacy Core System A | AI-Native Platform A | AI-Native Platform B | **OpenInsure** |
|---|---|---|---|---|
| **Architecture** | Traditional + AI bolt-on | AI-native (closed) | AI-native (closed) | **AI-native (open)** |
| **License** | Proprietary | Proprietary | Proprietary | **AGPL-3.0** |
| **Model Strategy** | Vendor-locked | Custom dsLM | Closed | **Model-agnostic (1,900+ models)** |
| **Platform** | Java on-prem | Custom | Custom | **Microsoft Foundry + Azure** |
| **Compliance** | Manual | Partial | Partial | **EU AI Act by design** |

### Target Users

- **MGAs** (Managing General Agents) needing a modern core system
- **InsurTech startups** building on proven insurance domain models  
- **Small specialty carriers** replacing legacy systems
- **Developers** building insurance applications with AI agents

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    M365 Copilot / Teams                      │
│         (User-facing agent surface for insurance ops)        │
├─────────────────────────────────────────────────────────────┤
│              React Dashboard (11 role-specific views)        │
│   Executive │ UW Workbench │ Claims │ Compliance │ Broker   │
├─────────────────────────────────────────────────────────────┤
│                 Azure AI Foundry                             │
│  ┌──────────────┬──────────────┬───────────────────────┐    │
│  │ Agent Service │   AI Search  │   Foundry Models      │    │
│  │ 8 Agents:     │ (Knowledge   │  (GPT-5.1, Claude,   │    │
│  │ Submission,   │  retrieval,  │   Phi, Mistral —      │    │
│  │ Underwriting, │  hybrid      │   1,900+ models)      │    │
│  │ Policy,Claims,│  vector +    │                       │    │
│  │ Compliance,   │  keyword)    │                       │    │
│  │ Document,     │              │                       │    │
│  │ Knowledge,    │              │                       │    │
│  │ Orchestrator  │              │                       │    │
│  └──────────────┴──────────────┴───────────────────────┘    │
├─────────────────────────────────────────────────────────────┤
│              FastAPI Backend (Python 3.12+)                  │
│  Submissions │ Underwriting │ Policies │ Claims │ Billing   │
├─────────────────────────────────────────────────────────────┤
│              Azure Infrastructure                            │
│  Azure SQL │ Cosmos DB │ AI Search │ Blob Storage │ Events  │
│  Service Bus │ Event Grid │ Key Vault │ Entra ID           │
└─────────────────────────────────────────────────────────────┘
```

### Core Modules

| Module | Description | Agent |
|--------|-------------|-------|
| **Submission Intake** | Receive, classify, extract, validate, triage | Submission Agent |
| **Underwriting** | Risk assessment, pricing, terms, authority management | Underwriting Agent |
| **Policy Admin** | Quote → bind → endorse → renew → cancel lifecycle | Policy Agent |
| **Claims** | FNOL → investigate → reserve → settle → close | Claims Agent |
| **Billing** | Premiums, payments, commissions, installment plans | — |
| **Compliance** | EU AI Act, audit trail, bias monitoring, regulatory | Compliance Agent |
| **Reinsurance** | Treaties, cessions, recoveries, bordereaux (carrier) | — |
| **Actuarial** | Reserves, loss triangles, IBNR, rate adequacy (carrier) | — |
| **MGA Oversight** | Authority limits, performance, bordereaux (carrier) | — |
| **Renewals** | 90/60/30-day flagging, AI-powered renewal pricing | — |
| **Knowledge Graph** | UW guidelines, claims precedents, compliance rules | Knowledge Agent |
| **Document Intelligence** | OCR, classification, structured extraction | Document Agent |

### Design Principles

1. **Agents-first, screens-second** — Every process is an agent-callable API
2. **Model-agnostic AI** — 1,900+ models via Foundry Model Router
3. **Knowledge graph over model weights** — Durable intelligence in structured knowledge
4. **ACORD-aligned, not ACORD-dependent** — Modern JSON/REST with ACORD mapping
5. **Regulatory compliance as architecture** — EU AI Act compliant by design
6. **Microsoft ecosystem integration** — M365 Copilot, Teams, Entra ID

## Foundry Agents

OpenInsure deploys **8 specialized AI agents** on Azure AI Foundry Agent Service:

| Agent | Responsibility | Key Decisions |
|-------|---------------|---------------|
| **Submission Agent** | Intake, classification, extraction, triage, appetite matching | Submission triage, priority assignment |
| **Underwriting Agent** | Risk assessment, cyber scoring, premium calculation, authority check | Quote generation, bind/decline recommendation |
| **Policy Agent** | Bind, issue, endorse, renew, cancel | Policy lifecycle actions |
| **Claims Agent** | FNOL intake, coverage verification, reserving, fraud detection | Severity triage, reserve setting, fraud flagging |
| **Compliance Agent** | Decision audit, bias analysis, regulatory checking | Compliance pass/fail, bias alerts |
| **Document Agent** | Document classification (ACORD, loss runs, financials), OCR extraction | Document type, extracted data |
| **Knowledge Agent** | Underwriting rules, product definitions, regulatory requirement retrieval | Knowledge query results |
| **Orchestrator** | Multi-step workflow coordination, decision record collection | Workflow routing, escalation |

Every agent decision produces an immutable **Decision Record** (EU AI Act Art. 12) with reasoning chain, confidence score, and fairness metrics. Agents with confidence < 0.7 automatically escalate to human oversight.

Agents are visible in the [Azure AI Foundry portal](https://ai.azure.com) under your configured project.

## Role-Based Access

OpenInsure supports **11 dashboard roles** with role-specific views and authority levels:

| Role | Default View | Key Capabilities |
|------|-------------|-----------------|
| CEO | Executive Dashboard | Portfolio KPIs, trends, agent impact metrics |
| CUO | Main Dashboard | Underwriting oversight, authority management |
| Senior Underwriter | Underwriting Workbench | Complex risk review, quote approval |
| UW Analyst | Underwriting Workbench | Submission analysis, preliminary assessment |
| Claims Manager | Claims Workbench | Claims oversight, reserve approval, settlement authority |
| Claims Adjuster | Claims Workbench | Investigation, evidence gathering, payments |
| CFO | Executive Dashboard | Financial oversight, premium tracking, loss ratios |
| Compliance Officer | Compliance Workbench | AI decision audit, bias monitoring, regulatory reporting |
| Product Manager | Main Dashboard | Product configuration, pricing strategy |
| Operations | Main Dashboard | System health, workflow monitoring |
| Broker (External) | Broker Portal | Self-service submission, quotes, binding — no internal data exposed |

**Authority delegation:** Auto-bind for premiums < $25K and risk score ≤ 5; escalation to UW Level 1/2 or Committee based on premium, risk, and referral triggers. Supports both **Carrier** (19 roles) and **MGA** (12 roles) deployment modes.

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 18+ (for dashboard)
- Azure subscription (for production; works locally with in-memory stores)
- Azure CLI (`az`) and Bicep CLI

### Local Development

```bash
# Clone the repository
git clone https://github.com/urosstojkic/openinsure.git
cd openinsure

# Install backend dependencies
pip install -e ".[dev]"

# Run the backend API server
uvicorn openinsure.main:app --reload --port 8000

# In a second terminal — run the dashboard
cd dashboard
npm install
npm run dev

# First-time setup: seed 3 years of operations data (1,200 submissions, 420 policies, 85 claims)
python scripts/seed_data.py

# Run tests
pytest tests/ -v --cov=src/openinsure

# Lint and format
ruff check src/ tests/ && ruff format src/ tests/

# Type check
mypy src/openinsure/
```

### Deployment

OpenInsure can be deployed to any Azure subscription. See [Deployment Guide](docs/deployment/azure-setup.md) for instructions.

After deployment, your instance will be available at:
- **Dashboard:** `https://<your-dashboard>.azurecontainerapps.io`
- **Backend API:** `https://<your-backend>.azurecontainerapps.io`
- **Swagger UI:** `https://<your-backend>.azurecontainerapps.io/docs`
- **Foundry Agents:** Visible in [Microsoft Foundry portal](https://ai.azure.com)

## Testing

### Local Mode (default, no Azure resources needed)
```bash
pytest tests/ -v
```

### Azure Mode (requires deployed Azure resources)
```bash
pytest tests/ --azure -v
```

### Skip Azure-dependent tests
```bash
pytest tests/ -m "not azure" -v
```

### Azure Deployment

```bash
# Deploy infrastructure
az deployment group create \
  --resource-group <your-resource-group> \
  --template-file infra/main.bicep \
  --parameters infra/parameters/dev.bicepparam
```

### API Documentation

Once running locally, visit:
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **OpenAPI JSON:** http://localhost:8000/openapi.json

## API Overview

| Module | Endpoints | Key Operations |
|--------|-----------|----------------|
| **Submissions** | `POST/GET/PUT /api/v1/submissions` | Create, list, get, update submissions |
| | `POST /api/v1/submissions/{id}/triage` | AI-powered triage and risk scoring |
| | `POST /api/v1/submissions/{id}/quote` | Generate quote (calls Underwriting Agent) |
| | `POST /api/v1/submissions/{id}/bind` | Bind submission to policy |
| | `POST /api/v1/submissions/{id}/documents` | Upload supporting documents |
| **Policies** | `POST/GET/PUT /api/v1/policies` | Create, list, get, update policies |
| | `POST /api/v1/policies/{id}/endorse` | Mid-term endorsement |
| | `POST /api/v1/policies/{id}/renew` | Renew policy |
| | `POST /api/v1/policies/{id}/cancel` | Cancel policy |
| **Claims** | `POST/GET/PUT /api/v1/claims` | Create (FNOL), list, get, update claims |
| | `POST /api/v1/claims/{id}/reserve` | Set reserves |
| | `POST /api/v1/claims/{id}/payment` | Record payment |
| | `POST /api/v1/claims/{id}/close` | Close claim |
| | `POST /api/v1/claims/{id}/reopen` | Reopen claim |
| **Products** | `POST/GET/PUT /api/v1/products` | Manage product definitions |
| | `POST /api/v1/products/{id}/rate` | Rate a submission |
| | `GET /api/v1/products/{id}/coverages` | List available coverages |
| **Billing** | `POST/GET /api/v1/billing/accounts` | Create/get billing accounts |
| | `POST /api/v1/billing/accounts/{id}/payment` | Record payment |
| | `GET/POST /api/v1/billing/accounts/{id}/invoices` | List/issue invoices |
| **Compliance** | `GET /api/v1/compliance/decisions` | List AI decision records (EU AI Act) |
| | `GET /api/v1/compliance/audit-trail` | Filtered audit trail |
| | `POST /api/v1/compliance/bias-report` | Generate bias analysis report |
| | `GET /api/v1/compliance/system-inventory` | AI system inventory |
| **Reinsurance** | `/api/v1/reinsurance/*` | Treaty management, cessions, recoveries |
| **Actuarial** | `/api/v1/actuarial/*` | Reserves, triangles, IBNR, rate adequacy |
| **MGA** | `/api/v1/mga/*` | MGA authorities, bordereaux, performance |
| **Renewals** | `/api/v1/renewals/*` | Upcoming renewals, term generation, processing |
| **Finance** | `/api/v1/finance/*` | Financial summary, cashflow, commissions |
| **Knowledge** | `/api/v1/knowledge/*` | Guidelines, claims precedents, compliance rules |
| **Documents** | `POST /api/v1/documents/upload` | Upload with OCR + AI extraction |
| | `POST /api/v1/submissions/acord-ingest` | ACORD 125/126 XML ingestion |
| **Demo** | `POST /api/v1/demo/full-workflow` | Complete lifecycle in one call |
| **Health** | `GET /health`, `GET /ready` | Health and readiness probes |

See [API Documentation](docs/api/) for the full specification.

## Demo Workflow

Try the complete insurance lifecycle in a single API call:

```bash
curl -X POST http://localhost:8000/api/v1/demo/full-workflow | python -m json.tool
```

This creates a sample submission (Quantum Dynamics Corp — tech, $12M revenue), triages it, calculates a premium via the rating engine, binds a policy with 5 cyber coverages, files a ransomware claim, and sets $150K in reserves. Returns a step-by-step trace with timing (~3ms total):

```json
{
  "workflow_id": "demo-abc123",
  "status": "completed",
  "total_duration_ms": 3,
  "policy_number": "POL-DEMO-A1B2C3",
  "claim_number": "CLM-DEMO-X1Y2Z3",
  "premium": 18617.04,
  "summary": "✅ Demo complete in 3ms — Submission → Triage → Quote ($18,617) → Policy → Claim (ransomware, $150K reserve)",
  "steps": [
    {"step": 1, "name": "create_submission", "status": "completed"},
    {"step": 2, "name": "triage", "status": "completed"},
    {"step": 3, "name": "quote", "status": "completed"},
    {"step": 4, "name": "bind_policy", "status": "completed"},
    {"step": 5, "name": "file_claim", "status": "completed"},
    {"step": 6, "name": "set_reserves", "status": "completed"}
  ]
}
```

## ACORD Ingestion

Upload an ACORD 125/126 XML commercial insurance application:

```bash
curl -X POST http://localhost:8000/api/v1/submissions/acord-ingest \
  -F "file=@application.xml"
```

The parser extracts applicant info, business profile, policy details, loss history, and prior insurance — then creates a submission automatically.

## Agent Architecture

OpenInsure agents are organized in three tiers:

**Tier 1 — Orchestrator** (Foundry Agent Service): Coordinates multi-step workflows (submission-to-bind, claims workflows), collects decision records, manages escalations
**Tier 2 — Domain Agents** (Foundry Agent Service): Submission, Underwriting, Policy, Claims, Compliance — each owns a business domain
**Tier 3 — Utility Agents** (Foundry Agent Service): Document (OCR/classification), Knowledge (retrieval from knowledge base)

Every agent decision produces a **Decision Record** for EU AI Act compliance:

```json
{
  "decision_id": "uuid",
  "agent_id": "underwriting-agent-v0.1",
  "model_used": "gpt-5.1",
  "decision_type": "underwriting_recommendation",
  "confidence": 0.82,
  "reasoning": { "chain_of_thought": "...", "key_factors": [...] },
  "fairness_metrics": { "disparate_impact_ratio": 0.95 },
  "human_oversight": { "required": false, "reason": "within_auto_authority" }
}
```

## Implementation Status

### Phase 1 — Core Platform & Cyber MVP ✅

- ✅ Core domain model (Party, Submission, Policy, Claim, Product, Billing)
- ✅ REST API with 90+ endpoints across 21 modules
- ✅ 8 AI agents with decision record logging
- ✅ Azure infrastructure (9 Bicep modules, 13+ Azure resources)
- ✅ Knowledge base (cyber product, underwriting guidelines, regulatory requirements)
- ✅ EU AI Act compliance layer (decision records, audit trail, bias monitoring)
- ✅ MCP Server interface
- ✅ Role-based access control (19 platform roles, authority delegation)
- ✅ React dashboard with 22 pages
- ✅ Cyber Liability SMB product (5 coverages, configurable rating engine)
- ✅ CI/CD pipeline (lint, type check, security scan, 445+ tests, build)

### Phase 2 — Dashboard & Workbenches ✅

- ✅ Underwriting Workbench, Claims Workbench, Compliance Workbench
- ✅ Broker Portal for external self-service
- ✅ Multi-agent orchestration workflows (new_business, claims_workflow)

### Phase 3 — Carrier Modules ✅

- ✅ Reinsurance management (treaty lifecycle, cession calculation, recovery tracking, SQL persistence)
- ✅ Actuarial analytics (loss triangles, IBNR estimation, reserve adequacy, rate adequacy)
- ✅ MGA oversight (delegated authority management, bordereaux, performance scoring)
- ✅ Reinsurance Dashboard, Actuarial Workbench, MGA Oversight Dashboard — all wired to live APIs

### Phase 4 — Renewals, Finance & Integrations ✅

- ✅ Renewal workflow (90/60/30-day identification, AI-powered term generation, SQL persistence)
- ✅ Financial reporting (premium/claims analytics, cash flow, commissions, reconciliation)
- ✅ ACORD 125/126 XML ingestion with comprehensive field extraction
- ✅ Azure Document Intelligence adapter (OCR + structured extraction for PDF/images)
- ✅ Knowledge graph: claims precedents, compliance rules (EU AI Act, GDPR, NAIC)
- ✅ Live demo endpoint — full lifecycle in a single API call
- ✅ Finance Dashboard, Renewals Page — wired to live APIs

### Phase 5 — Security & Quality ✅

- ✅ SQL injection hardening (parameterized pagination across all repositories)
- ✅ Production error sanitization (global exception handler)
- ✅ Constant-time API key comparison (timing attack prevention)
- ✅ File upload size validation (50MB limit)
- ✅ Comprehensive E2E test (full lifecycle: submission → bind → claim → close)
- ✅ OpenAPI documentation with tag descriptions and request examples

### In Progress

- 🔄 M365 Copilot publishing
- 🔄 Azure AI Search vector indexing for knowledge retrieval

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend** | Python 3.12+ / FastAPI / Pydantic v2 |
| **Dashboard** | React 18 + TypeScript + Vite + TanStack Query |
| **AI Platform** | Azure AI Foundry (Agent Service, AI Search, Models) |
| **AI Models** | GPT-5.1 (primary), 1,900+ models via Foundry Model Router |
| **Agent Framework** | Azure AI Foundry Agent Service (Python SDK) |
| **Document AI** | Azure AI Document Intelligence (OCR + structured extraction) |
| **Database** | Azure SQL (transactional) + Cosmos DB NoSQL (knowledge graph) |
| **Search** | Azure AI Search (vector + keyword hybrid) |
| **Storage** | Azure Blob Storage |
| **Events** | Azure Event Grid + Service Bus |
| **Identity** | Microsoft Entra ID + Managed Identity (passwordless) |
| **IaC** | Bicep (9 modules) |
| **CI/CD** | GitHub Actions |
| **Hosting** | Azure Container Apps |
| **Security** | Parameterized SQL, constant-time auth, CORS, file size limits |

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

**Development workflow:**
1. Fork the repository
2. Create a feature branch: `git checkout -b feat/your-feature`
3. Write tests first (TDD)
4. Implement the feature
5. Ensure all quality gates pass: `ruff check && mypy && pytest`
6. Submit a PR

## License

OpenInsure is licensed under [AGPL-3.0](LICENSE). 

**What this means:**
- ✅ Use freely for any purpose
- ✅ Modify and distribute
- ✅ Build proprietary apps that consume OpenInsure APIs (separate works)
- ⚠️ If you modify and deploy OpenInsure itself (including as a network service), you must release your modifications under AGPL-3.0

For proprietary modifications, contact us about a commercial license.

## Acknowledgments

Built with the Microsoft AI stack: [Microsoft Foundry](https://foundry.microsoft.com), Azure, and GitHub Copilot.

Inspired by the vision of AI-native insurance operations where agents handle the routine, humans handle the exceptions.
