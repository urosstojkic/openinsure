# Testing Patterns — OpenInsure

## Adversarial Findings (Bugs Discovered by Tests)

### 1. `renewal.py` — None premium crashes
`float(policy.get("total_premium", 0) or policy.get("premium", 0))` fails with
`TypeError: float() argument must be a string or a real number, not 'NoneType'`
when both `total_premium` and `premium` are explicitly `None`. The `or` chain
evaluates `None or None` → `None`, and `float(None)` raises.

### 2. `reinsurance.py` — Missing policy UUID crashes cession
Calling `calculate_cession()` with a policy dict that has no `"id"` key causes
`CessionRecord(policy_id="")` → Pydantic `ValidationError` because `""` is not
a valid UUID. Always pass a UUID in policy dicts.

### 3. `reinsurance.py` — Rate=1 boundary condition
`treaty.rate > 1` means rate=1 is treated as a direct multiplier (100% cession),
NOT divided by 100. Rates are either: <= 1 (used as-is, e.g. 0.25 = 25%) or
> 1 (divided by 100, e.g. 25 = 25%).

## Mock Patterns

### Mock Repository (async)
```python
from unittest.mock import AsyncMock, patch

mock_repo = AsyncMock()
mock_repo.list_all.return_value = [...]
with patch("openinsure.services.module.get_X_repository", return_value=mock_repo):
    result = await service_function()
```

### Mock Factory Functions
Always patch at the **factory** module, not the service module:
```python
# CORRECT — patch where it's defined:
with patch("openinsure.infrastructure.factory.get_document_intelligence") as m:
    svc = DocumentProcessingService()

# WRONG — service imports it at __init__ time:
with patch("openinsure.services.document_processing.get_document_intelligence") as m:
    # AttributeError: module does not have the attribute
```

### Mock Azure AI Search adapter
```python
mock_adapter = AsyncMock()
mock_adapter.search.return_value = {"results": [...]}
with patch("openinsure.services.knowledge_search.get_search_adapter", return_value=mock_adapter):
    results = await search_knowledge("query")
```

### Force In-Memory Mode for Integration/Contract Tests
```python
@pytest.fixture(scope="module")
def monkeypatch_module():
    from _pytest.monkeypatch import MonkeyPatch
    mp = MonkeyPatch()
    mp.setenv("OPENINSURE_STORAGE_MODE", "memory")
    mp.setenv("OPENINSURE_SQL_CONNECTION_STRING", "")
    mp.setenv("OPENINSURE_DEBUG", "true")
    # Clear factory LRU caches
    from openinsure.infrastructure import factory
    for attr in dir(factory):
        obj = getattr(factory, attr, None)
        if hasattr(obj, "cache_clear"):
            obj.cache_clear()
    yield mp
    mp.undo()
```

### TestClient with Exception Safety
Use `raise_server_exceptions=False` for contract/middleware tests:
```python
client = TestClient(app, raise_server_exceptions=False)
resp = client.get("/endpoint")
assert resp.status_code == 500  # Won't raise in test
```

## Domain Entity Factories
```python
from datetime import date
from decimal import Decimal
from openinsure.domain.reinsurance import ReinsuranceContract, TreatyType, TreatyStatus

def _treaty(**overrides):
    defaults = dict(
        treaty_number="TR-001",
        treaty_type=TreatyType.QUOTA_SHARE,
        reinsurer_name="Swiss Re",
        status=TreatyStatus.ACTIVE,
        effective_date=date(2024, 1, 1),
        expiration_date=date(2025, 1, 1),
        rate=Decimal("25"),
    )
    return ReinsuranceContract(**(defaults | overrides))
```

## Coverage Findings (as of v96)

| File | Before | After | Tests |
|------|--------|-------|-------|
| actuarial.py | 17% | 100% | 30 |
| reinsurance.py | 0% | 100% | 42 |
| renewal.py | 29% | 100% | 22 |
| knowledge_search.py | 0% | 100% | 20 |
| document_processing.py | 53% | 100% | 28 |
| main.py | 43% | 70% | 27 |

Lines still uncovered in main.py: 66-115 (lifespan/startup with async migration +
seed + escalation queue — requires mocking multiple async services), 139 (CORS
branch), 297 (non-debug 500 handler — needs `debug=False` fixture).
