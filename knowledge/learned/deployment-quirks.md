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
