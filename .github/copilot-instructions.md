# OpenInsure — Copilot Instructions

## Squad-First Development (MANDATORY)

This project uses the **Squad framework** (`.squad/`) for all development. Every task MUST be routed through Squad agents.

### Routing Rules (from `.squad/routing.md`)

| Work Type | Route To | Charter |
|-----------|----------|---------|
| Backend API, services, repos | **Backend** | `.squad/agents/backend/charter.md` |
| React pages, components, UX | **Frontend** | `.squad/agents/frontend/charter.md` |
| Azure infra, Bicep, CI/CD | **Infra** | `.squad/agents/infra/charter.md` |
| Insurance domain, products, regs | **Insurance** | `.squad/agents/insurance/charter.md` |
| Tests, quality gates, Playwright | **QA** | `.squad/agents/qa/charter.md` |
| Security, RBAC, auth, audit | **Security** | `.squad/agents/security/charter.md` |
| Docs, history, decisions | **Scribe** | `.squad/agents/scribe/charter.md` |

### How to Route Work

1. **Read the user's request** and determine which Squad agent(s) should handle it
2. **Reference the agent's charter** in the prompt — include the charter file path
3. **Fan-out for cross-cutting work** — spawn multiple agents in parallel (e.g., Backend + Frontend + QA)
4. **After completion**: update the agent's `history.md` with learnings
5. **Record decisions** in `.squad/decisions.md` if architectural choices were made
6. **Label GitHub issues** with `squad:{agent}` for tracking

### Quality Gates (ALWAYS, before deploy)

1. `python -m ruff check src/ tests/ --fix && python -m ruff format src/ tests/`
2. `python -m pytest tests/ -x -q --ignore=tests/e2e/test_full_lifecycle.py`
3. `cd dashboard && npm run build`
4. `python scripts/smoke_test.py {backend_url}` — 15 checks must pass
5. Deploy: `pwsh scripts/deploy.ps1` (auto-versioning, sequential builds, no login prompts)

### Never Do

- Never launch generic unnamed agents — always route through Squad
- Never deploy without smoke test passing
- Never use mock data in production (VITE_USE_MOCK must be false)
- Never use Start-Job for Azure CLI (breaks auth — use sequential commands)

## Project Vision

OpenInsure is an **enterprise-grade, open-source core insurance platform** — agent-native, built on Azure and Microsoft Foundry. This is not a prototype or demo. Every feature must be production-ready, every endpoint must handle real data, every UI must satisfy a VP of Underwriting using it daily.

**There are no token limits.** Every Squad agent should take as much resources as needed to deliver the best output possible. No shortcuts, no "good enough," no stubs. Read the full context, understand the domain, implement completely, test thoroughly. Quality over speed, always.

### North Star Documents
- `docs/architecture/architecture-spec-v01.md` — Technical architecture vision
- `docs/architecture/operating-model-v02.md` — Operating model with 16+ personas
- `docs/architecture/data-model.md` — Entity relationships and state machines
- `docs/architecture/process-flows.md` — Agent workflows and integration architecture

Before ANY merge to main, ALL of these must pass:
1. `pytest tests/ -v` — all green
2. `ruff check src/ tests/` — no errors
3. `ruff format --check src/ tests/` — compliant
4. `mypy src/openinsure/` — no errors
5. `bandit -r src/openinsure/ -ll` — no findings
6. Security review: no hardcoded credentials, proper auth, input validation
7. Quality compromises documented as GitHub issues

## Quick Reference

- **Language**: Python 3.12+ with strict typing
- **Framework**: FastAPI + Pydantic v2
- **Tests**: pytest (TDD-first — write tests before code)
- **Lint**: ruff (check + format)
- **Types**: mypy --strict
- **Security**: bandit, no hardcoded credentials
- **IaC**: Bicep (in `infra/`)

## Domain-Driven Design

All business logic lives in `src/openinsure/domain/` as Pydantic models.
Services in `src/openinsure/services/` orchestrate domain operations.
Infrastructure adapters in `src/openinsure/infrastructure/` handle external systems.
API layer in `src/openinsure/api/` is thin — delegates to services.

## Insurance-Specific Patterns

- All monetary values use `Decimal` (never `float`)
- All entity IDs are UUIDs
- All timestamps are ISO 8601 UTC
- Domain events published for every state change
- Every AI agent decision must produce a `DecisionRecord` (EU AI Act compliance)
- ACORD-aligned entity names: Party, Submission, Policy, Claim, Product

## Azure Integration Patterns

- Use `azure.identity.DefaultAzureCredential` for all Azure service auth
- Connection strings from environment variables (pydantic-settings)
- Async clients for all Azure SDK operations
- Retry with exponential backoff via tenacity
- Structured logging via structlog

## Compliance Requirements

- EU AI Act: Every AI decision → DecisionRecord with reasoning chain
- Audit trail: Immutable event log for all state changes
- Bias monitoring: Track outcomes across demographic groups
- Human oversight: Red/amber/green flagging for agent decisions
