# Deployment Quirks

Lessons learned from deploying OpenInsure to Azure.

## ARM64 / x64 Python

- **Problem:** ARM64 Python cannot use `pyodbc` because ODBC Driver 17 for SQL Server is x64 only.
- **Fix:** Use x64 Python at `C:\Users\urstojki\AppData\Local\Programs\Python\Python313\python.exe` for any SQL-related work.
- **Confidence:** High — verified repeatedly.

## Azure SQL Public Access

- **Problem:** Company policy disables SQL public access daily via Azure Policy.
- **Fix:** Use private endpoint for all SQL connections. Do not rely on firewall rules for public access.
- **Confidence:** High — observed daily resets.

## Cosmos DB Authentication

- **Problem:** Cosmos DB has `disableLocalAuth=true` — connection strings with keys will fail.
- **Fix:** Use `DefaultAzureCredential` only. No connection string auth.
- **Confidence:** High.

## Container App Environment Variables

- **Problem:** Container App needs `OPENINSURE_API_KEY` env var for API key authentication to work.
- **Fix:** Set it in the Container App configuration. If missing, all authenticated endpoints return 401.
- **Confidence:** High.

## Deploy Script Constraints

- **Problem:** `Start-Job` in PowerShell breaks Azure CLI authentication context.
- **Fix:** Do not use `Start-Job` in deploy scripts. Run Azure CLI commands sequentially in the same process.
- **Confidence:** High — caused silent auth failures.

## Docker Build Context

- **Problem:** Build context is `.` (repo root), not `src/`. The Dockerfile is at the repository root.
- **Fix:** Always run `docker build -f Dockerfile .` from the repo root.
- **Confidence:** High.

## Health Probes — Liveness Must Be Lightweight

- **Problem:** If `/health` checks SQL and Foundry, a transient database outage triggers Container Apps restarts, creating a cascade where the pod never stabilises.
- **Fix:** `/health` (liveness) must only confirm the process is alive — no dependency checks. Use `/ready` (readiness) for dependency checks and `/startup` for initial boot verification. Container Apps removes pods from the LB on readiness failure but only restarts on liveness failure.
- **Confidence:** High — observed restart loop in dev.

## CD Pipeline — Run Migrations Before Deploy, Not During Startup

- **Problem:** Running migrations in the app's `lifespan` startup handler means every replica applies migrations on restart. Under concurrent scale-out, two replicas can race and fail.
- **Fix:** Run migrations as a separate step in the CD pipeline *before* updating container images. The app's startup still tries migrations (idempotent), but the CD step ensures they are applied once.
- **Confidence:** Medium — not yet observed at scale, but best-practice from Azure SQL docs.

## Bicep Design — Container Apps Module Needs All Outputs

- **Problem:** The Container Apps module needs SQL FQDN, Cosmos endpoint, Search endpoint, etc., as environment variables. If you deploy Container Apps in a separate Bicep module, you must thread all outputs through `main.bicep` parameters.
- **Approach chosen:** Single `main.bicep` orchestrates all modules; Container Apps module receives outputs as parameters. Alternative was using `az containerapp update --set-env-vars` in a script, but IaC-first is more reproducible.
- **Confidence:** High.

## ACR Name Must Be Globally Unique

- **Problem:** ACR names are globally unique DNS names (`*.azurecr.io`). A name like `openinsureacr` will collide.
- **Fix:** Use `resourceToken` (from `uniqueString()`) as a suffix: e.g. `openinsuredevacra1b2c3`.
- **Confidence:** High.

## Renaming Response Fields Breaks Tests Silently

- **Problem:** When standardising `events.py` response envelope (`events`→`items`, `count`→`total`), the test at `test_event_store.py:260` used `body["count"]` and `body["events"]`. The failure only surfaced at runtime as a `KeyError`, not a type error.
- **Fix:** After renaming any response model field, grep tests for the old field name: `grep -rn '"count"\|"events"' tests/`. Pydantic response models don't protect against dict-key access in tests.
- **Confidence:** High — hit this exact issue.

## Envelope Audit Needs Full-Codebase Grep, Not Spot-Checks

- **Problem:** Initial fix for #287 only checked the 6 main CRUD modules. A second audit found 11 more endpoints across `broker.py`, `underwriter.py`, `gdpr.py`, `events.py`, `documents.py`, `work_items.py`, `workflows.py`, `parties.py`, and `risk_attributes.py` that still returned non-standard envelopes.
- **Fix:** Grep all API files for `-> dict[str` and `-> list[` return types, plus audit every response model missing `skip`/`limit` fields. The command: `grep -rn 'response_model=\|-> dict\[str\|-> list\[' src/openinsure/api/`.
- **Confidence:** High — the full audit caught 11 endpoints the initial pass missed.
