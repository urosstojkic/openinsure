# Security Agent — History

## Learnings

- bandit B608 on SQL repos — use nosec annotation, queries use parameterized ?
- CORS was wildcard — fixed to environment-aware origins
- Event publishing errors must not crash requests (non-critical path)
- Container App managed identity RBAC: needs explicit role on each Azure resource
