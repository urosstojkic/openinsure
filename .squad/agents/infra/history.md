# Infrastructure Agent — History

## Learnings

- Azure SQL public access gets reset — needs to be in Bicep IaC to persist
- ODBC Driver 18 in container doesn't support Authentication= attribute — use access token struct
- Access token must be UTF-16-LE encoded with struct.pack('<I{len}s', len, bytes) for SQL_COPT_SS_ACCESS_TOKEN
- Container App managed identity needs to be SQL Entra admin (not just RBAC Contributor)
- Event Grid topic uses CloudEventV1.0 schema — event publisher must format correctly
- Dashboard Dockerfile must use .env.production with VITE_USE_MOCK=false
