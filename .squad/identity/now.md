---
updated_at: 2025-07-21
focus_area: Review v2 complete — all issues closed
version: v73
branch: main
tests_passing: 506
api_endpoints: 118
dashboard_pages: 25
foundry_agents: 8
team_size: 7 active agents + Scribe + @copilot
team_identity: Insurance Operations
process: All work through PRs. Co-authored-by trailer on AI-assisted commits. smoke_test.py before deploy.
---

# What We're Focused On

**Status:** v73 deployed, CI green, review v2 complete — 10/10 expert assessment issues verified and closed.

## Current State

- **Version:** v73 (Container Apps)
- **Branch:** main
- **Build:** CI green (ruff + mypy + bandit + pytest)
- **Tests:** 506 passing (417 unit)
- **Stack:** Python 3.12 / FastAPI, React 18 / TypeScript, Azure SQL + Foundry + Container Apps

**Team:** 7 specialized agents (Backend, Frontend, Infra, Insurance, QA, Security, Scribe)

## Completed (Phases 1–6)

- ✅ Foundry-first agent architecture — 8 agents deployed (Orchestrator, Submission, Underwriting, Policy, Claims, Compliance, Document, Knowledge)
- ✅ Authority engine with escalation chains — auto-execute / recommend / require-approval / escalate
- ✅ EU AI Act compliance — DecisionRecord on every AI action, bias monitoring with real disparate impact analysis (4/5ths rule)
- ✅ 25 dashboard pages with real SQL data — executive, finance, reinsurance, MGA, actuarial workbenches, knowledge UI
- ✅ RBAC with 23 Entra ID roles — deployment-scoped (Carrier vs MGA)
- ✅ State machine enforcement on all entity transitions
- ✅ ProcessWorkflowModal — Foundry AI pipeline visualization with confidence scores
- ✅ UW workbench detail panel with risk assessment breakdown
- ✅ Broker portal full lifecycle (submit → track → quote → bind → claim)
- ✅ Escalation framework with sidebar badge and approve/reject workflow
- ✅ Knowledge graph UI with tabbed display
- ✅ Subjectivities tracking with CRUD and bind-blocking
- ✅ Automatic cession on policy bind
- ✅ Rating breakdown display with factor tables
- ✅ Claims notifications with breach notification tracking
- ✅ 3-year seed script — 1,540 submissions, 513 policies, 115 claims
- ✅ Squad framework — 7 agents with charters, decisions, skills
- ✅ Expert assessment — all 10 issues (#3–#75) closed and verified

## What's Next

- 🔄 M365 Copilot publishing
- 🔄 Azure AI Search vector indexing for knowledge retrieval
- 🔄 Billing API implementation (largest remaining gap)
- 🔄 Policy document generation

## Vision

"AI-native does not mean 'uses AI.' It means AI is the primary interface and execution engine, not an enhancement to a human-operated system. The default path is autonomous, with human oversight on exceptions."

## Process

- All changes through PRs with quality gates (ruff + mypy + bandit + pytest)
- Pre-deploy: `scripts/smoke_test.py` (15 checks)
- Deploy: `scripts/deploy.ps1` (ACR build → Container Apps)
- Post-deploy: Playwright visual verification
