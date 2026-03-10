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
- ✅ 35+ REST API endpoints covering submissions, policies, claims, billing, products, and compliance
- ✅ React dashboard with 11 role-specific views (Executive, Underwriting Workbench, Claims Workbench, Compliance Workbench, Broker Portal)
- ✅ Cyber Liability SMB product with 5 coverages and configurable rating engine
- ✅ EU AI Act compliance: immutable decision records, bias monitoring (4/5ths rule), audit trail
- ✅ Role-based access control with 19 platform roles and authority delegation
- ✅ Azure infrastructure: 13+ resources defined as Bicep IaC

### Why OpenInsure?

| | Guidewire | mea Platform | Corgi | **OpenInsure** |
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
| **Billing** | Premiums, payments, commissions, installment plans | Billing Agent |
| **Compliance** | EU AI Act, audit trail, bias monitoring, regulatory | Compliance Agent |

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

Agents are visible in the [Azure AI Foundry portal](https://ai.azure.com) under the `uros-ai-foundry-demo` project.

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

# Run tests
pytest tests/ -v --cov=src/openinsure

# Lint and format
ruff check src/ tests/ && ruff format src/ tests/

# Type check
mypy src/openinsure/
```

### Live Deployment

| Service | URL |
|---------|-----|
| **Dashboard** | https://openinsure-dashboard.braveriver-f92a9f28.swedencentral.azurecontainerapps.io |
| **Backend API** | https://openinsure-backend.braveriver-f92a9f28.swedencentral.azurecontainerapps.io |
| **Swagger UI** | https://openinsure-backend.braveriver-f92a9f28.swedencentral.azurecontainerapps.io/docs |
| **Foundry Agents** | [ai.azure.com](https://ai.azure.com) → `uros-ai-foundry-demo` project |

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
  --resource-group openinsure-dev \
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
| **Health** | `GET /health`, `GET /ready` | Health and readiness probes |

See [API Documentation](docs/api/) for the full specification.

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

## Phase 1: Cyber Insurance MVP

Phase 1 delivers a working cyber insurance submission-to-bind workflow:

- ✅ Core domain model (Party, Submission, Policy, Claim, Product, Billing)
- ✅ REST API with 35+ endpoints across 7 modules
- ✅ 8 AI agents with decision record logging (Submission, Underwriting, Policy, Claims, Compliance, Document, Knowledge, Orchestrator)
- ✅ Azure infrastructure (9 Bicep modules, 13+ Azure resources)
- ✅ Knowledge base (cyber insurance product, underwriting guidelines, regulatory requirements)
- ✅ EU AI Act compliance layer (immutable decision records, audit trail, bias monitoring with 4/5ths rule)
- ✅ MCP Server interface
- ✅ Role-based access control (19 platform roles, authority delegation)
- ✅ React dashboard with 11 role-specific views
- ✅ Underwriting Workbench, Claims Workbench, Compliance Workbench
- ✅ Broker Portal for external self-service
- ✅ Cyber Liability SMB product (5 coverages, configurable rating engine)
- ✅ Multi-agent orchestration workflows (new_business, claims_workflow)
- ✅ CI/CD pipeline (lint, type check, security scan, tests ≥80% coverage, build)
- 🔄 Document intelligence (OCR, extraction) — in progress
- 🔄 M365 Copilot publishing — planned

**Success Criteria:**
- Process a cyber submission from email to bindable quote in <15 minutes
- Extract ACORD application data with 90%+ accuracy
- Generate premium quotes within 5% of human underwriter pricing
- Complete audit trail for every AI decision

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend** | Python 3.12+ / FastAPI / Pydantic v2 |
| **Dashboard** | React 18 + TypeScript + Vite |
| **AI Platform** | Azure AI Foundry (Agent Service, AI Search, Models) |
| **AI Models** | GPT-5.1 (primary), 1,900+ models via Foundry Model Router |
| **Agent Framework** | Azure AI Foundry Agent Service (Python SDK) |
| **Database** | Azure SQL (transactional) + Cosmos DB NoSQL (knowledge, decision records) |
| **Search** | Azure AI Search (vector + keyword hybrid) |
| **Storage** | Azure Blob Storage |
| **Events** | Azure Event Grid + Service Bus |
| **Identity** | Microsoft Entra ID + Managed Identity (passwordless) |
| **IaC** | Bicep (9 modules) |
| **CI/CD** | GitHub Actions |
| **Hosting** | Azure Container Apps |

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
