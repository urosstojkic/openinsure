---
updated_at: 2026-03-20
focus_area: Expert assessment remediation
version: v63
branch: main
tests_passing: 440+
api_endpoints: 90+
dashboard_pages: 22
foundry_agents: 6
team_size: 7 active agents + Scribe + @copilot
team_identity: Insurance Operations
process: All work through PRs. Co-authored-by trailer on AI-assisted commits. smoke_test.py before deploy.
---

# What We're Focused On

**Status:** v63 deployed, CI green, addressing expert assessment findings across 10 open issues.

## Current State

- **Version:** v63 (Container Apps)
- **Branch:** main
- **Build:** CI green (ruff + mypy + bandit + pytest)
- **Tests:** 440+ passing
- **Stack:** Python 3.12 / FastAPI, React 18 / TypeScript, Azure SQL + Foundry + Container Apps

**Team:** 7 specialized agents (Backend, Frontend, Infra, Insurance, QA, Security, Scribe)

## Completed (Phases 1–4)

- ✅ Foundry-first agent architecture — 6 agents deployed (Submission, Underwriting, Policy, Claims, Compliance, Document)
- ✅ Authority engine with escalation chains — auto-execute / recommend / require-approval / escalate
- ✅ EU AI Act compliance — DecisionRecord on every AI action, bias monitoring (4/5ths rule)
- ✅ 22 dashboard pages with real SQL data — executive, finance, reinsurance, MGA, actuarial workbenches
- ✅ RBAC with 23 Entra ID roles — deployment-scoped (Carrier vs MGA)
- ✅ State machine enforcement on all entity transitions
- ✅ ProcessWorkflowModal — Foundry AI pipeline visualization with confidence scores
- ✅ 3-year seed script — 1,200 submissions, 420 policies, 85 claims
- ✅ Squad framework — 7 agents with charters, decisions, skills

## Active Work in Progress

Expert assessment findings — 10 open issues across domain depth, compliance, and integration:

- **#3:** Document intelligence with Azure AI — ACORD form OCR extraction
- **#10:** Azure OpenAI RBAC workaround — managed identity token scoping
- **#38:** ACORD 125/126 ingestion — structured form parsing pipeline
- **#39:** Live demo workflow — upload → extract → triage → quote → bind end-to-end
- **#40:** Reinsurance treaty modeling — facultative and treaty placement workflows
- **#41:** Actuarial loss triangle calculation — IBNR reserve estimation
- **#42:** Bordereaux reporting — MGA oversight monthly data exchange
- **#43:** Premium audit trail — finance reconciliation with GL integration
- **#44:** Multi-LOB product configuration — property, casualty, professional lines
- **#45:** Renewal pipeline automation — 90/60/30 day identification and outreach

## Vision

"AI-native does not mean 'uses AI.' It means AI is the primary interface and execution engine, not an enhancement to a human-operated system. The default path is autonomous, with human oversight on exceptions."

## Process

- All changes through PRs with quality gates (ruff + mypy + bandit + pytest)
- Pre-deploy: `scripts/smoke_test.py` (15 checks)
- Deploy: `scripts/deploy.ps1` (ACR build → Container Apps)
- Post-deploy: Playwright visual verification
