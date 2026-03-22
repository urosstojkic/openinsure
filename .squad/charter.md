# OpenInsure Squad Charter

## Mission

Build and maintain OpenInsure — an AI-native, open-source core insurance platform deployed as a template into customer-owned Azure tenants.

## Principles

1. **Foundry-first** — AI agents run in Microsoft Foundry, not local stubs
2. **Real data only** — No mocking in production; all dashboards show SQL data
3. **Fail-closed** — AI safety defaults reject on uncertainty
4. **Enterprise-grade** — Authority matrix, audit trail, EU AI Act compliance
5. **Template model** — Each deployment is single-tenant in customer's Azure

## Quality Gates

- All PRs: ruff + mypy + bandit + pytest (440+ tests)
- Pre-deploy: scripts/smoke_test.py (15 checks)
- Post-deploy: Playwright visual verification

## Coordinator

| Name | Role | Notes |
|------|------|-------|
| Squad | Coordinator | Routes work to specialized agents, enforces quality gates. Does not generate domain artifacts. |

## Members

| Name | Role | Charter | Status |
|------|------|---------|--------|
| Backend | Python/FastAPI Specialist | `.squad/agents/backend/charter.md` | ✅ Active |
| Frontend | React/TypeScript Specialist | `.squad/agents/frontend/charter.md` | ✅ Active |
| Infra | Azure/DevOps Specialist | `.squad/agents/infra/charter.md` | ✅ Active |
| Insurance | Insurance Domain Expert | `.squad/agents/insurance/charter.md` | ✅ Active |
| QA | Testing & Quality Specialist | `.squad/agents/qa/charter.md` | ✅ Active |
| Security | Security & Compliance | `.squad/agents/security/charter.md` | ✅ Active |
| Scribe | Documentation Specialist | `.squad/agents/scribe/charter.md` | ✅ Active |

## Coding Agent

| Name | Role | Charter | Status |
|------|------|---------|--------|
| @copilot | Coding Agent | — | 🤖 Coding Agent |

### Capabilities

**🟢 Good fit — auto-route when enabled:**
- Bug fixes in Python backend or React dashboard
- New API endpoints following existing router patterns
- Test additions matching existing pytest conventions
- Dependency updates and configuration changes
- Documentation updates

**🟡 Needs review:**
- New Foundry agent definitions (must follow InsuranceAgent pattern)
- State machine transition changes (domain impact)
- RBAC role or authority limit changes
- Database schema changes (SQL migration required)

**🔴 Not suitable:**
- Authority engine threshold changes (requires Insurance + Security review)
- EU AI Act compliance model changes (legal review required)
- Azure infrastructure changes (Infra agent owns deploy.ps1)
- Multi-agent orchestration workflow redesign

## Project Context

- **Owner:** OpenInsure
- **Stack:** Python/FastAPI backend, React/TypeScript dashboard, Azure (SQL, Foundry, Container Apps)
- **Distribution:** Azure template deployment (single-tenant per customer)
- **Universe:** Insurance Operations
- **Created:** 2026-03-09
