# OpenInsure

**AI-Native Open Source Core Insurance Platform**

[![CI](https://github.com/urosstojkic/openinsure/actions/workflows/ci.yml/badge.svg)](https://github.com/urosstojkic/openinsure/actions/workflows/ci.yml)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](https://opensource.org/licenses/AGPL-3.0)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)

> Every module — underwriting, policy administration, claims, billing, compliance — is designed from the ground up to be operated by, and through, AI agents.

## What Is This?

OpenInsure is an open-source, AI-native core insurance platform built on the Microsoft AI stack (Foundry + Azure). It is **not** a traditional core system with AI bolted on — AI is the primary interface and execution engine, with human oversight on exceptions.

**Traditional system:** Human opens screen → fills forms → clicks buttons → reviews output
**OpenInsure:** Agent receives submission → extracts data → assesses risk → generates quote → binds within authority → escalates exceptions to humans

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
│                    Copilot Studio                             │
│      (No-code agent config, topic routing, guardrails)       │
├─────────────────────────────────────────────────────────────┤
│                Microsoft Foundry                             │
│  ┌──────────────┬──────────────┬───────────────────────┐    │
│  │ Agent Service │  Foundry IQ  │   Foundry Models      │    │
│  │ (Multi-agent  │ (Knowledge   │  (GPT-5.2, Claude,   │    │
│  │  orchestration)│  retrieval) │   Phi, Mistral)       │    │
│  └──────────────┴──────────────┴───────────────────────┘    │
├─────────────────────────────────────────────────────────────┤
│              Azure Infrastructure                            │
│  Azure SQL │ Cosmos DB │ AI Search │ Blob Storage │ Events  │
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

## Quick Start

### Prerequisites

- Python 3.12+
- Azure subscription (for production; works locally with in-memory stores)
- Azure CLI (`az`) and Bicep CLI

### Local Development

```bash
# Clone the repository
git clone https://github.com/urosstojkic/openinsure.git
cd openinsure

# Install dependencies
pip install -e ".[dev]"

# Run the development server
uvicorn openinsure.main:app --reload --port 8000

# Run tests
pytest tests/ -v --cov=src/openinsure

# Lint and format
ruff check src/ tests/ && ruff format src/ tests/

# Type check
mypy src/openinsure/
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

Once running, visit:
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **OpenAPI JSON:** http://localhost:8000/openapi.json

## API Overview

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /health` | GET | Health check |
| `POST /api/v1/submissions` | POST | Create submission |
| `POST /api/v1/submissions/{id}/triage` | POST | AI triage |
| `POST /api/v1/submissions/{id}/quote` | POST | Generate quote |
| `POST /api/v1/submissions/{id}/bind` | POST | Bind to policy |
| `POST /api/v1/claims` | POST | Report FNOL |
| `GET /api/v1/compliance/decisions` | GET | Decision records (EU AI Act) |

See [API Documentation](docs/api/) for the full specification.

## Agent Architecture

OpenInsure agents are organized in three tiers:

**Tier 1 — Orchestrator** (Copilot Studio): Routes requests to specialized agents
**Tier 2 — Domain Agents** (Foundry Agent Service): Submission, Underwriting, Policy, Claims, Billing, Compliance
**Tier 3 — Utility Agents** (Foundry Agent Service): Document, Data, Communication, Analytics

Every agent decision produces a **Decision Record** for EU AI Act compliance:

```json
{
  "decision_id": "uuid",
  "agent_id": "underwriting-agent-v0.1",
  "model_used": "gpt-5.2",
  "decision_type": "underwriting_recommendation",
  "confidence": 0.82,
  "reasoning": { "chain_of_thought": "...", "key_factors": [...] },
  "human_oversight": { "required": false, "reason": "within_auto_authority" }
}
```

## Phase 1: Cyber Insurance MVP

Phase 1 delivers a working cyber insurance submission-to-bind workflow:

- ✅ Core domain model (Party, Submission, Policy, Claim, Product, Billing)
- ✅ REST API with full CRUD operations
- ✅ AI Agent framework with decision record logging
- ✅ Azure infrastructure (Bicep IaC)
- ✅ Knowledge base (cyber insurance product, underwriting guidelines)
- ✅ EU AI Act compliance layer
- ✅ MCP Server interface
- 🔄 Multi-agent orchestration workflows
- 🔄 Document intelligence (OCR, extraction)
- 🔄 M365 Copilot publishing

**Success Criteria:**
- Process a cyber submission from email to bindable quote in <15 minutes
- Extract ACORD application data with 90%+ accuracy
- Generate premium quotes within 5% of human underwriter pricing
- Complete audit trail for every AI decision

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend** | Python 3.12+ / FastAPI / Pydantic v2 |
| **AI Platform** | Microsoft Foundry (Agent Service, IQ, Models) |
| **Agent Framework** | Microsoft Agent Framework (Python SDK) |
| **Database** | Azure SQL (transactional) + Cosmos DB Gremlin (knowledge graph) |
| **Search** | Azure AI Search (vector + keyword hybrid) |
| **Storage** | Azure Blob Storage |
| **Events** | Azure Event Grid + Service Bus |
| **Identity** | Microsoft Entra ID |
| **IaC** | Bicep |
| **CI/CD** | GitHub Actions |

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
