# OpenInsure — Agent Instructions

These instructions apply to all Copilot agents working in this repository.

## Project Overview

OpenInsure is an AI-native open-source core insurance platform built on Microsoft Foundry + Azure. Every module (underwriting, policy admin, claims, billing, compliance) is designed to be operated by AI agents. Phase 1 targets Cyber Insurance MVP.

## Project Priorities

1. **Enterprise grade, no mocking**: Every operation must use real Azure services and Foundry agents. No stubs, no fake data, no in-memory shortcuts in production code paths. Local fallbacks exist ONLY for when Azure services are unreachable.
2. **Quality over speed**: Every change must pass all quality gates before merge
3. **TDD-first**: Write tests before implementation — lights-out codebase principle
4. **Small, testable diffs**: Target ~150 lines per PR for reviewability
5. **Security-first**: Managed identity, no hardcoded credentials, Key Vault for secrets
6. **Compliance-by-design**: Every AI decision must produce a Decision Record (EU AI Act)
7. **Foundry-first**: Every operation involving AI judgment (triage, risk assessment, reserve estimation, fraud detection, compliance checking, coverage analysis) MUST call the deployed Foundry agents. Local Python logic is ONLY a fallback when Foundry is unavailable.

## Foundational Principles

- **Stakeholder Authority** — Agents NEVER change priorities, scope, or close issues autonomously. Escalate concerns and wait.
- **Agents-first, screens-second** — Every business process is exposed as an agent-callable API
- **Knowledge graph over model weights** — Durable insurance intelligence lives in structured knowledge, not fine-tuned models
- **ACORD-aligned, not ACORD-dependent** — Modern JSON/REST with ACORD mapping layers

## Repo Structure

- `src/openinsure/` — Python source code (FastAPI backend)
  - `domain/` — Pydantic domain entities (Party, Submission, Policy, Claim, Product, Billing)
  - `api/` — REST API endpoints (FastAPI routers)
  - `agents/` — AI agent definitions (submission, underwriting, policy, claims, billing, compliance, document, knowledge)
  - `knowledge/` — Knowledge graph layer (Cosmos DB Gremlin, AI Search)
  - `services/` — Business logic services (rating engine, document processing, policy lifecycle)
  - `infrastructure/` — Azure service adapters (SQL, Cosmos, Blob, Event Grid, AI Search)
  - `mcp/` — MCP Server interface for external agent integration
  - `compliance/` — Decision records, audit trail, bias monitoring (EU AI Act)
- `tests/` — Test suite (pytest)
  - `unit/` — Unit tests for domain, services, agents, compliance
  - `integration/` — Integration tests for API and infrastructure
  - `e2e/` — End-to-end tests (submission-to-bind workflow)
- `infra/` — Bicep IaC for Azure deployment
- `knowledge/` — Knowledge base YAML files (products, guidelines, regulatory)
- `docs/` — Documentation (architecture, API, deployment)

## Key Commands

```bash
# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v --cov=src/openinsure

# Lint and format
ruff check src/ tests/ && ruff format src/ tests/

# Type check
mypy src/openinsure/

# Security scan
bandit -r src/openinsure/ -c pyproject.toml

# Run dev server
uvicorn openinsure.main:app --reload --port 8000

# Run all checks
ruff check src/ tests/ && ruff format --check src/ tests/ && mypy src/openinsure/ && pytest tests/ -v
```

## Coding Conventions

- Python 3.12+ with strict typing
- Pydantic v2 for all data models — use model_validator, field_validator
- FastAPI dependency injection for services and adapters
- Async/await for all I/O operations
- structlog for structured logging (JSON format)
- tenacity for retry logic with exponential backoff
- UUID for all entity IDs
- ISO 8601 for all timestamps (UTC)
- Domain events for all state changes (published via Event Grid)
- All monetary values as Decimal (never float)

## Architectural Decisions

See `docs/TECHNICAL_OVERVIEW.md` Appendix C for immutable architectural decisions.

Key ADRs:
- ADR-001: Python FastAPI for backend
- ADR-002: Pydantic v2 for domain entities
- ADR-003: Azure SQL for transactional data, Cosmos DB for knowledge graph
- ADR-004: Event-driven architecture with Azure Event Grid + Service Bus
- ADR-005: Microsoft Agent Framework for AI agents
- ADR-006: EU AI Act compliance-by-design with Decision Records
- ADR-007: ACORD-aligned data model with modern JSON/REST APIs

## Safety

- Don't delete or overwrite output artifacts unless explicitly asked
- Don't edit `.env` or database files directly
- Don't modify ADRs without explicit confirmation
- Never hardcode credentials, connection strings, or API keys
- Always use managed identity for Azure service connections
- Every AI decision MUST produce a DecisionRecord

## Quality Gates (All Must Pass)

See `.github/copilot-instructions.md` §2 for the complete quality gates checklist.

## Security Requirements (Non-Negotiable)

See `SECURITY.md` for the full security policy. Key non-negotiables:

1. **No hardcoded credentials** — All secrets via environment variables or Key Vault
2. **Input validation** — All API inputs validated via Pydantic models
3. **Authentication** — All /api/* endpoints require authentication
4. **CORS** — No wildcard origins; environment-specific allowed origins
5. **Error handling** — Error responses MUST NOT leak internal details (stack traces, connection strings)
6. **Dependency security** — `bandit -r src/openinsure/ -ll` must pass with 0 findings
7. **Test coverage** — Every new feature must include tests; API endpoints must have integration tests
8. **Decision records** — Every AI agent decision must produce a DecisionRecord

## Quality Compromise Tracking

When a technical compromise is made (e.g., using a different Azure service than specified, using stubs instead of real implementations, reducing test coverage threshold), the agent MUST:

1. Document the compromise clearly in the commit message
2. Create a GitHub issue with label "quality" explaining:
   - What was compromised
   - Why (the technical constraint)
   - Impact on the system
   - Proposed resolution path
3. Never silently reduce quality without transparent tracking

## Available Agents

| Agent | Invoke With | Use For |
|-------|------------|---------|
| Code Developer | `@code-developer` | Write/improve code, refactoring |
| Test Engineer | `@test-engineer` | Write tests, coverage analysis, TDD |
| Documentation | `@documentation-agent` | Technical docs, README, API docs |
| Security Reviewer | `@security-reviewer` | Security audit, credential scan, OWASP |
| Architect | `@architect` | ADR compliance, system design review |
| Compliance Agent | `@compliance-reviewer` | EU AI Act, GDPR, regulatory compliance |
| Insurance Domain Expert | `@insurance-expert` | Insurance domain logic, ACORD alignment |
| Challenger | `@challenger` | Adversarial review of decisions and PRs |
| CI Fixer | `@ci-fixer` | Diagnose and fix CI/CD failures |

## ⛔ Workflow Gates

**⛔ Gate 0: PROCESS OVER SPEED — Every code change requires: feature branch → PR → CI green → merge. No exceptions.**

1. **Every Change → Branch + PR**: `git checkout -b feat/<issue>-<name>` → commit → push → `gh pr create` → CI green → squash-merge. Never `git push origin main`. Never `--no-verify`.

### ⛔ Gate 1: CI Gate — Enforcement

```bash
gh run list --branch <branch> --limit 3   # ALL must show ✓
gh run view <run-id> --log-failed          # If any show ✗, diagnose
```

- **Do NOT merge on red. No exceptions.**
- "Tests passed locally" is NOT sufficient — CI must be green.
- Only after CI is green: `gh pr merge <number> --squash --delete-branch`

## Insurance Domain Context

OpenInsure operates in the insurance industry with these key concepts:
- **Submission**: An application for insurance coverage, received from brokers/agents
- **Underwriting**: Risk assessment and pricing of insurance submissions
- **Policy**: The insurance contract once a submission is bound
- **Claim**: A request for payment under an insurance policy
- **FNOL**: First Notice of Loss — initial claim report
- **Rating**: The process of calculating insurance premiums
- **Endorsement**: A mid-term modification to an existing policy
- **Bordereaux**: Detailed premium/claims reports for MGAs
- **MGA**: Managing General Agent — authorized to bind coverage on behalf of carriers
- **LOB**: Line of Business (e.g., cyber, property, auto insurance)
