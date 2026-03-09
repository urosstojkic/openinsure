# OpenInsure — Copilot Instructions

## Mandatory Pre-Merge Checklist

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
