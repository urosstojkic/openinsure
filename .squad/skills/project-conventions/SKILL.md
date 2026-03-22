---
name: "project-conventions"
description: "Core conventions and patterns for the OpenInsure codebase"
domain: "python, fastapi, react, azure, insurance"
confidence: "high"
source: "extracted"
---

## Context

OpenInsure is an AI-native insurance platform with a Python/FastAPI backend, React/TypeScript dashboard, and Azure infrastructure (SQL, Foundry, Container Apps). All patterns below are enforced conventions — agents must follow them when generating code.

## Patterns

### FastAPI Endpoint Conventions

Every API module follows the router pattern. All `/api/v1/*` routes require authentication via the `get_current_user` dependency.

```python
from fastapi import APIRouter, Depends
from openinsure.api.auth import get_current_user
from openinsure.models import SomeRequest, SomeResponse
from openinsure.api.errors import make_error

router = APIRouter()

@router.get("/{item_id}", response_model=SomeResponse)
async def get_item(item_id: str, user=Depends(get_current_user)):
    repo = get_some_repository()
    item = repo.get(item_id)
    if not item:
        return JSONResponse(404, make_error("Not found", "NOT_FOUND", resource_type="Item", resource_id=item_id))
    return item
```

- Routers are registered in `src/openinsure/api/router.py` via `include_router()`
- Prefix convention: `/api/v1/{domain}` (e.g., `/api/v1/submissions`, `/api/v1/claims`)
- All request/response bodies use Pydantic `BaseModel` subclasses
- Tags match the domain module name

### Repository Pattern

Dual implementation via factory — InMemory for local dev/CI, SQL for production.

```python
# Factory in src/openinsure/infrastructure/factory.py
@lru_cache
def get_submission_repository() -> BaseRepository:
    settings = get_settings()
    if settings.storage_mode == "azure" and settings.sql_connection_string:
        from openinsure.infrastructure.repositories.sql_submissions import SqlSubmissionRepository
        db = get_database_adapter()
        return SqlSubmissionRepository(db)
    from openinsure.infrastructure.repositories.submissions import InMemorySubmissionRepository
    return InMemorySubmissionRepository()
```

- InMemory repos live in `src/openinsure/infrastructure/repositories/{domain}.py`
- SQL repos live in `src/openinsure/infrastructure/repositories/sql_{domain}.py`
- SQL repos use `_to_sql_row()` / `_from_sql_row()` for mapping
- Both implement the same base interface from `repository.py`
- `storage_mode` is set via environment variable or config

### State Machine Enforcement

All entity transitions are validated at the domain layer. Never change state directly.

```python
from openinsure.domain.state_machine import validate_submission_transition

# Valid: received → triaging → underwriting → quoted → bound
validate_submission_transition(current_state, target_state)  # raises InvalidTransitionError if invalid
```

- Submission: `received → triaging → underwriting → quoted → bound` (with decline/refer/expire branches)
- Policy: `draft → active → renewed | cancelled | expired`
- Claim: `fnol → investigation → reserved → settled | denied | closed`
- Invariant checkers enforce domain rules per state

### Error Handling

All API errors use the `ErrorResponse` model with `request_id` for tracing.

```python
from openinsure.api.errors import make_error, ErrorResponse

# ErrorResponse fields: error (human-readable), code (machine-readable), request_id, detail (optional)
return JSONResponse(
    status_code=404,
    content=make_error(
        "Submission not found",
        "NOT_FOUND",
        resource_type="Submission",
        resource_id=submission_id,
    ),
)
```

- Global exception handler in `main.py` catches unhandled exceptions
- Debug mode includes exception type in response; production returns generic message
- Every error response includes a `request_id` (UUID) for log correlation
- Never leak stack traces in production

### Testing

```bash
# Run all tests
pytest

# Run with Azure integration tests
pytest --azure

# Run specific test module
pytest tests/unit/test_domain/test_state_machine.py
```

- **Framework:** pytest with parametrized tests
- **Structure:** `tests/unit/`, `tests/integration/`, `tests/e2e/`
- **Unit tests:** Domain models, state machines, RBAC, agents, services
- **Integration tests:** API endpoints via `TestClient`, with `conftest.py` fixtures
- **E2E tests:** Full workflows (submission → triage → underwrite → quote → bind)
- **Fixtures:** `sample_submission_data()`, `sample_party_data()` in conftest.py
- **Azure-only tests:** Marked with `@pytest.mark.azure`, skipped without `--azure` flag
- **Foundry mocking:** Use mock `FoundryClient` that returns structured responses
- **Linting:** ruff (format + lint), mypy (type checking), bandit (security)

### Deployment

```powershell
# Deploy backend and dashboard
scripts/deploy.ps1

# Deploy backend only with specific version
scripts/deploy.ps1 -BackendOnly -Version v64

# Pre-deploy smoke test
python scripts/smoke_test.py
```

- `deploy.ps1` builds on ACR (server-side), deploys to Container Apps
- Auto-increments version from existing ACR tags
- `smoke_test.py` runs 15 checks against health, submissions, policies, claims, compliance
- Post-deploy: Playwright visual verification of dashboard pages

### Commit Conventions

- Include `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>` trailer when AI-assisted
- Reference issue numbers in commit messages (e.g., `fix #38: ACORD parser`)
- Conventional commits preferred: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`

### Foundry Agent Pattern

All agents inherit from `InsuranceAgent` base class.

```python
class MyAgent(InsuranceAgent):
    agent_id = "my_agent"
    agent_version = "0.1.0"
    capabilities = ["action_1", "action_2"]
    authority_limit = Decimal("50000")
```

- Every agent action produces a `DecisionRecord` (EU AI Act compliance)
- Agents call Foundry via `foundry_client.invoke(agent_name, message)`
- Response includes `source` ("foundry" or "fallback"), `execution_time_ms`
- Structured logging via `structlog`, retry via `tenacity`

## Examples

### ✓ Correct: New API endpoint

```python
# src/openinsure/api/renewals.py
router = APIRouter()

@router.get("/", response_model=list[RenewalSummary])
async def list_renewals(days: int = 90, user=Depends(get_current_user)):
    repo = get_policy_repository()
    return repo.get_renewals_due(days=days)
```

### ✗ Incorrect: Bypassing state machine

```python
# WRONG — never set state directly
submission.status = "bound"

# RIGHT — validate transition
validate_submission_transition(submission.status, "bound")
submission.status = "bound"
```

### ✗ Incorrect: Hardcoded data in dashboard

```python
# WRONG — no mock data in production
return {"submissions": [{"id": "fake-1", "status": "received"}]}

# RIGHT — query real repository
repo = get_submission_repository()
return {"submissions": repo.list_all()}
```

## Anti-Patterns

- ❌ **Direct SQL in API handlers** — Always go through the repository layer. Repositories handle row mapping and connection lifecycle.
- ❌ **Skipping DecisionRecord** — Every AI agent action must produce a `DecisionRecord`. No silent AI decisions.
- ❌ **Public database endpoints** — Azure SQL must use private endpoints only. Never expose connection strings.
- ❌ **Hardcoded role checks** — Use `Role(StrEnum)` constants from `rbac/roles.py`, never string literals like `"admin"`.
- ❌ **Local agent execution in production** — Foundry is the production runtime. `InsuranceAgent` subclasses are fallback for dev/CI only.
- ❌ **Multi-tenant data mixing** — Each deployment is single-tenant. No tenant_id filtering — data isolation is at the infrastructure level.
