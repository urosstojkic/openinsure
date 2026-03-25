# E2E Test Results — v90

> **Date**: 2026-03-25  
> **Backend**: `https://openinsure-backend.proudplant-9550e5a5.swedencentral.azurecontainerapps.io`  
> **Auth**: `X-API-Key: dev-key-change-me`  
> **Tool**: httpx (Python)

## Results

| # | Test | Status | Details |
|---|------|--------|---------|
| 1 | Submission lifecycle | ✅ PASS | Created → Triaged → Quoted ($5,000) → Bound (policy created) |
| 2 | Claims lifecycle | ✅ PASS | Claim filed (data_breach) → Reserve set ($75,000) |
| 3 | Knowledge API | ✅ PASS | `GET /api/v1/knowledge/guidelines/cyber` — guidelines retrieved from Cosmos |
| 4 | Metrics summary | ✅ PASS | `GET /api/v1/metrics/summary` — 1,642 submissions, 575 policies, 140 claims, 22.5% bind rate |
| 5 | Compliance decisions | ✅ PASS | `GET /api/v1/compliance/decisions` — 174 decision records found |
| 6 | Agent traces | ✅ PASS | `GET /api/v1/agent-traces` — 174 agent invocations logged |
| 7 | Demo workflow | ✅ PASS | `POST /api/v1/demo/full-workflow` — completed in 284ms, 6 steps (Submit → Triage → Quote $18,617 → Bind → Claim → Reserve) |
| 8 | Escalations | ✅ PASS | `GET /api/v1/escalations` — 3 escalation records found |

**Result: 8/8 tests passed** ✅

## Test Details

### 1. Submission Lifecycle (Create → Triage → Quote → Bind)

- **Create**: `POST /api/v1/submissions` with `applicant_name`, `line_of_business: cyber`, `annual_revenue: 5000000`
- **Triage**: `POST /api/v1/submissions/{id}/triage` — risk scored, appetite matched
- **Quote**: `POST /api/v1/submissions/{id}/quote` — premium calculated at $5,000
- **Bind**: `POST /api/v1/submissions/{id}/bind` — policy created
- **Auth**: `X-User-Role: underwriter`

### 2. Claims Lifecycle (File → Reserve)

- **File claim**: `POST /api/v1/claims` with `claim_type: data_breach`, `policy_id` from existing policy
- **Set reserve**: `POST /api/v1/claims/{id}/reserve` with `amount: 75000, category: indemnity`
- **Auth**: `X-User-Role: openinsure-claims-adjuster` (RBAC enforced — other roles trigger escalation)
- **Note**: `claims-manager` and `underwriter` roles correctly escalate reserve-setting to claims-adjuster

### 3. Knowledge API

- **Endpoint**: `GET /api/v1/knowledge/guidelines/cyber`
- **Response**: Cyber underwriting guidelines with coverage rules, risk factors, and appetite criteria
- **Source**: Cosmos DB (with in-memory fallback)

### 4. Metrics Summary

- **Endpoint**: `GET /api/v1/metrics/summary`
- **Key metrics**: 1,642 submissions total | 369 bound (22.5% bind rate) | 575 policies | 140 claims
- **Status breakdown**: received: 157, triaging: 69, underwriting: 90, quoted: 131, declined: 184, bound: 369

### 5. Compliance Decisions

- **Endpoint**: `GET /api/v1/compliance/decisions`
- **Count**: 174 decision records (EU AI Act Art. 12 compliant)
- **Contents**: Each record includes agent_id, decision_type, confidence, reasoning chain, fairness metrics

### 6. Agent Traces

- **Endpoint**: `GET /api/v1/agent-traces`
- **Count**: 174 agent invocations logged
- **Includes**: Agent name, input/output, duration, model used, decision record reference

### 7. Demo Workflow

- **Endpoint**: `POST /api/v1/demo/full-workflow`
- **Duration**: 284ms total
- **Steps**: 6 (create_submission → triage → quote → bind_policy → file_claim → set_reserves)
- **Output**: Policy POL-DEMO-F627FE, Claim CLM-DEMO-8D7726, Premium $18,617

### 8. Escalations

- **Endpoint**: `GET /api/v1/escalations`
- **Count**: 3 escalation records (created during claims reserve tests with insufficient role)
- **Behavior**: RBAC correctly escalates when role lacks authority — working as designed
