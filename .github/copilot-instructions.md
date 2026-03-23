# OpenInsure — Copilot Instructions

> **This is the single source of truth for development context.** Read this at the start of every session.

---

## 1. Project Vision

OpenInsure is an **enterprise-grade, open-source core insurance platform** — agent-native, built on Azure and Microsoft Foundry. This is not a prototype or demo. Every feature must be production-ready, every endpoint must handle real data, every UI must satisfy a VP of Underwriting using it daily.

**There are no token limits.** Every Squad agent should take as much resources as needed to deliver the best output possible. No shortcuts, no "good enough," no stubs. Read the full context, understand the domain, implement completely, test thoroughly. Quality over speed, always.

### North Star Documents (do not modify)

| Document | Purpose |
|----------|---------|
| `docs/architecture/architecture-spec-v01.md` | Technical architecture vision |
| `docs/architecture/operating-model-v02.md` | Operating model with 16+ personas |

---

## 2. Squad-First Development (MANDATORY)

This project uses the **Squad framework** (`.squad/`) for all development. Every task MUST be routed through Squad agents.

### Routing Table

| Work Type | Route To | Charter |
|-----------|----------|---------|
| Backend API, services, repos | **Backend** | `.squad/agents/backend/charter.md` |
| React pages, components, UX | **Frontend** | `.squad/agents/frontend/charter.md` |
| Azure infra, Bicep, CI/CD | **Infra** | `.squad/agents/infra/charter.md` |
| Insurance domain, products, regs | **Insurance** | `.squad/agents/insurance/charter.md` |
| Tests, quality gates, Playwright | **QA** | `.squad/agents/qa/charter.md` |
| Security, RBAC, auth, audit | **Security** | `.squad/agents/security/charter.md` |
| Docs, history, decisions | **Scribe** | `.squad/agents/scribe/charter.md` |

Full routing rules including issue triage and @copilot assignment: `.squad/routing.md`

### How to Route Work

1. **Read the user's request** and determine which Squad agent(s) should handle it
2. **Reference the agent's charter** in the prompt — include the charter file path
3. **Fan-out for cross-cutting work** — spawn multiple agents in parallel (e.g., Backend + Frontend + QA)
4. **After completion**: update the agent's `history.md` with learnings
5. **Record decisions** in `.squad/decisions.md` if architectural choices were made
6. **Label GitHub issues** with `squad:{agent}` for tracking

### Quality Gates (MANDATORY before deploy)

1. **CI must be green** — Check `gh run list --limit 1` before deploying. If CI is red, fix it first. Never deploy with failing CI. No exceptions.
2. `python -m ruff check src/ tests/ --fix && python -m ruff format src/ tests/`
3. `python -m pytest tests/ -x -q --ignore=tests/e2e/test_full_lifecycle.py`
4. `cd dashboard && npm run build`
5. `python scripts/smoke_test.py {backend_url}` — 15 checks must pass
6. Deploy: `pwsh scripts/deploy.ps1` (auto-versioning, sequential builds)

Quality compromises MUST be documented as GitHub issues with `quality` label.

### Never Do

- Never launch generic unnamed agents — always route through Squad
- Never deploy without smoke test passing
- Never use mock data in production (`VITE_USE_MOCK` must be `false`)
- Never use `Start-Job` for Azure CLI (breaks auth — use sequential commands)
- Never merge on red CI. "Tests passed locally" is NOT sufficient.
- Never hardcode credentials, connection strings, or API keys

---

## 3. Current Platform State

| Metric | Value |
|--------|-------|
| Tests | 448+ (pytest, CI green) |
| API endpoints | 90+ across 21 modules |
| Dashboard pages | 24 (React 18 + TypeScript + Tailwind) |
| Foundry agents | 6 deployed on Azure AI Foundry |
| MCP tools | 16 tools + 5 resources |
| Azure SQL data | 1,540 submissions, 513 policies, 115 claims |
| Portfolio | $24.19M GWP, 36.9% loss ratio, 88.8% combined ratio |
| CI pipeline | ruff + mypy + bandit + pytest (GitHub Actions) |
| Hosting | Azure Container Apps (VNet + private endpoint) |

### Foundry Agents (Azure AI Foundry Agent Service)

| Agent | Purpose |
|-------|---------|
| **Orchestrator** | Multi-step workflow coordination, decision record collection |
| **Submission** | Intake, classification, extraction, triage, appetite matching |
| **Underwriting** | Risk assessment, cyber scoring, premium calculation, authority check |
| **Policy** | Bind, issue, endorse, renew, cancel |
| **Claims** | FNOL intake, coverage verification, reserving, fraud detection |
| **Compliance** | Decision audit, bias analysis, regulatory checking |

Every agent decision produces an immutable **Decision Record** (EU AI Act Art. 12). Confidence < 0.7 triggers automatic escalation to human oversight.

### Process Completeness (~75%)

See `docs/architecture/process-completeness.md` for the full gap analysis. Key gaps: data enrichment, billing pipeline, subrogation, document generation, automatic cession on bind.

---

## 4. Architecture Quick Reference

### Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.12+ / FastAPI / Pydantic v2 |
| Dashboard | React 18 + TypeScript + Vite + TanStack Query + Tailwind |
| AI Platform | Azure AI Foundry (Agent Service, AI Search, 1,900+ models) |
| Database | Azure SQL (transactional) + Cosmos DB Gremlin (knowledge graph) |
| Storage | Azure Blob Storage |
| Events | Azure Event Grid + Service Bus |
| Identity | Microsoft Entra ID + Managed Identity |
| IaC | Bicep (9 modules in `infra/`) |
| Hosting | Azure Container Apps |

### Core Entity Lifecycle

```
Submission: received -> triaging -> underwriting -> quoted -> bound -> POLICY
                 \-> referred -> (approved -> underwriting | declined)
                 \-> declined

Policy: draft -> active -> (endorsed) -> (cancelled -> reinstated -> active) -> expired
                   \-> renewed -> new Policy

Claim: reported -> under_investigation -> reserved -> (approved -> settled -> closed)
                                                   \-> denied -> closed
```

Full entity relationships and state machines: `docs/architecture/data-model.md`

### Key Design Patterns

| Pattern | Location | Notes |
|---------|----------|-------|
| Repository (InMemory + SQL) | `infrastructure/repositories/` | Swap via `storage_mode` env var |
| Service Factory | `infrastructure/factory.py` | LRU-cached dependency creation |
| Domain Entities | `domain/*.py` | Pydantic v2, immutable, ACORD-aligned |
| Agent Base | `agents/base.py` | `InsuranceAgent` ABC + `DecisionRecord` |
| Foundry Client | `agents/foundry_client.py` | Azure AI Projects SDK with graceful fallback |
| Router Composition | `api/router.py` | Hierarchical routers with auth dependency |

### Source Tree

```
src/openinsure/
+-- agents/          # 8 AI agents (base, foundry_client, submission, underwriting, ...)
+-- api/             # FastAPI routers (submissions, policies, claims, products, ...)
+-- compliance/      # EU AI Act: decision records, audit trail, bias monitoring
+-- domain/          # Pydantic entities (party, submission, policy, claim, product, billing)
+-- infrastructure/  # Azure adapters + repository implementations
|   +-- repositories/  # InMemory* and Sql* variants
+-- knowledge/       # Knowledge graph schemas & query builders
+-- mcp/             # MCP Server (16 tools, 5 resources, stdio + SSE)
+-- rbac/            # Roles, authority matrix, authentication
+-- services/        # Business logic (rating, lifecycle, claims, workflow engine)
+-- main.py          # FastAPI app entry point
```

### Auth Model

- **Dev/test**: `X-User-Role` header selects role (no auth required)
- **Production**: JWT / API key via `X-API-Key` header, Entra ID for Azure services
- **RBAC**: 19 platform roles, authority delegation engine in `rbac/`
- **Azure services**: `DefaultAzureCredential` (managed identity, no secrets in code)

---

## 5. Key URLs

| Resource | URL |
|----------|-----|
| Dashboard | https://openinsure-dashboard.proudplant-9550e5a5.swedencentral.azurecontainerapps.io |
| Backend API | https://openinsure-backend.proudplant-9550e5a5.swedencentral.azurecontainerapps.io |
| API Docs (Swagger) | https://openinsure-backend.proudplant-9550e5a5.swedencentral.azurecontainerapps.io/docs |
| GitHub | https://github.com/urosstojkic/openinsure |
| Foundry Portal | https://ai.azure.com (project-scoped) |
| Local API | http://localhost:8000/docs |
| Local Dashboard | http://localhost:5173 |

---

## 6. Development Patterns

### Domain-Driven Design

- Domain entities in `src/openinsure/domain/` — Pydantic v2 models, immutable where appropriate
- Services in `src/openinsure/services/` — orchestrate domain operations
- Infrastructure adapters in `src/openinsure/infrastructure/` — thin wrappers around Azure SDKs
- API layer in `src/openinsure/api/` — thin, delegates to services, never contains business logic

### Insurance-Specific Rules

- All monetary values: `Decimal` (never `float`)
- All entity IDs: `UUID`
- All timestamps: ISO 8601 UTC
- Domain events published for every state change
- ACORD-aligned entity names: Party, Submission, Policy, Claim, Product, Billing

### Azure Integration

- `azure.identity.DefaultAzureCredential` for all Azure service auth
- Connection strings from environment variables via pydantic-settings
- Async clients for all Azure SDK operations
- Retry with exponential backoff via `tenacity`
- Structured logging via `structlog` (JSON format)

### Compliance (EU AI Act)

- Every AI decision produces a `DecisionRecord` with reasoning chain, confidence, fairness metrics
- Immutable audit trail for all state changes
- Bias monitoring: 4/5ths rule analysis across demographic groups
- Human oversight: escalation when confidence < 0.7 or authority exceeded

### Coding Conventions

- Python 3.12+ with strict typing (`mypy --strict`)
- Pydantic v2 for all data models — use `model_validator`, `field_validator`
- FastAPI dependency injection for services and adapters
- Async/await for all I/O operations
- TDD-first: write tests before implementation
- Conventional commits: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`

---

## 7. Deploy Process

### Automated (recommended)

Push to `main` → CI green → CD auto-deploys via GitHub Actions (`.github/workflows/cd.yml`).

The CD workflow:
1. Triggers on successful CI completion on `main`
2. Logs into Azure via OIDC (federated credentials, no secrets stored)
3. Builds both images on ACR with `--cache-from` for faster rebuilds
4. Deploys to Container Apps with SHA-pinned image tags
5. Runs smoke tests against production

**Required GitHub repo secrets** (configure in Settings → Secrets → Actions):
- `AZURE_CLIENT_ID` — Service principal app registration client ID
- `AZURE_TENANT_ID` — Azure AD tenant ID
- `AZURE_SUBSCRIPTION_ID` — Azure subscription ID

See `docs/deployment/azure-setup.md` for OIDC federated credential setup.

### Manual (immediate deploy)

```bash
# Full deploy (auto-version, both backend + dashboard)
pwsh scripts/deploy.ps1

# Selective
pwsh scripts/deploy.ps1 -BackendOnly
pwsh scripts/deploy.ps1 -DashboardOnly

# Post-deploy verification
python scripts/smoke_test.py https://openinsure-backend.proudplant-9550e5a5.swedencentral.azurecontainerapps.io
```

The deploy script: ACR build, Container Apps update, auto-incrementing version tags (`v1`, `v2`, ...). No login prompts — uses existing `az login` session.

For Azure infrastructure setup: `docs/deployment/azure-setup.md`

---

## 8. Documentation Map

| Document | Purpose | Audience |
|----------|---------|----------|
| `README.md` | Public-facing: what is OpenInsure, quick start, features | Everyone |
| `AGENTS.md` | Agent development guidelines, repo structure, coding standards | Copilot agents |
| `CONTRIBUTING.md` | How to contribute, branch strategy, PR process | Contributors |
| `SECURITY.md` | Security policy, vulnerability reporting | Security |
| `CHANGELOG.md` | Release history | Everyone |
| `docs/architecture/architecture-spec-v01.md` | North star: technical architecture vision | Architects |
| `docs/architecture/operating-model-v02.md` | North star: operating model, 16+ personas | Product / architects |
| `docs/architecture/data-model.md` | Entity relationships, 26 tables, state machines | Backend devs |
| `docs/architecture/process-flows.md` | Agent workflows, RBAC matrix, integration architecture | All devs |
| `docs/architecture/process-completeness.md` | Gap analysis with roadmap (~75% complete) | Product / planning |
| `docs/architecture/mcp-integration.md` | MCP server: 16 tools, 5 resources, usage guide | Integration devs |
| `docs/architecture/overview.md` | Architecture overview with diagrams | New developers |
| `docs/architecture/ADR.md` | 7 architectural decision records (immutable) | Architects |
| `docs/deployment/azure-setup.md` | Azure deployment walkthrough | Infra / DevOps |
| `docs/guides/document-channels.md` | Document upload, ACORD ingestion, OCR guide | Backend devs |
| `docs/developer-guide.md` | Developer setup, patterns, extending the platform | New developers |
| `docs/CAPABILITIES.md` | Full functional capabilities (for executives) | Business stakeholders |
| `.squad/routing.md` | Work routing rules + issue triage | Squad framework |
| `.squad/decisions.md` | Architectural decisions log | All devs |
