# End-to-End Demo Case: NexGen Robotics Inc

> Full lifecycle walkthrough — submission → triage → quote → bind → claim → reserve — demonstrating how the OpenInsure platform processes an insurance application.

## Case Summary

| Field | Value |
|---|---|
| Company | NexGen Robotics Inc |
| Industry | Technology / Robotics-AI (SIC 3559) |
| Revenue | $22,000,000 |
| Employees | 180 |
| Line of Business | Cyber Liability |
| Security Score | 6/10 (0.6) |
| Prior Incidents | 1 |
| Controls | MFA ✓, Endpoint Protection ✓, Backup ✓, IR Plan ✗ |

---

## Step 1: Create Submission (Broker)

```http
POST /api/v1/submissions
X-User-Role: broker
```

**Payload:**
```json
{
  "applicant_name": "NexGen Robotics Inc",
  "applicant_email": "underwriting@nexgenrobotics.ai",
  "channel": "portal",
  "line_of_business": "cyber",
  "risk_data": {
    "annual_revenue": 22000000,
    "employee_count": 180,
    "industry": "technology",
    "industry_sic_code": "3559",
    "security_maturity_score": 6,
    "security_score": 0.6,
    "prior_incidents": 1,
    "has_mfa": true,
    "has_endpoint_protection": true,
    "has_backup_strategy": true,
    "has_incident_response_plan": false,
    "requested_limit": 1000000,
    "requested_deductible": 10000
  }
}
```

**Response (201 Created):**
```json
{
  "id": "9ffa233b-895a-4738-bb26-3c0f12523272",
  "submission_number": "SUB-2026-EBF3",
  "status": "received",
  "channel": "portal",
  "line_of_business": "cyber"
}
```

---

## Step 2: Triage — AI Risk Assessment (Underwriter)

```http
POST /api/v1/submissions/{id}/triage
X-User-Role: underwriter
```

**Response (200):**
```json
{
  "submission_id": "9ffa233b-895a-4738-bb26-3c0f12523272",
  "status": "underwriting",
  "risk_score": 6.0,
  "recommendation": "proceed_to_quote"
}
```

**Key findings from the Foundry AI agent:**
- Risk score: **6.0/10** (moderate risk)
- Recommendation: **proceed_to_quote**
- The agent noted the company has MFA, endpoint protection, and backup strategy, but **lacks an incident response plan** — a required control under cyber underwriting guidelines
- Industry (technology) and revenue ($22M) are within appetite
- Prior incidents (1) below the maximum threshold of 5

---

## Step 3: Generate Quote (Underwriter)

```http
POST /api/v1/submissions/{id}/quote
X-User-Role: underwriter
```

**Response (200):**
```json
{
  "submission_id": "9ffa233b-895a-4738-bb26-3c0f12523272",
  "quote_id": "4678186f-0d4a-4a24-8f12-37aaf8efd723",
  "premium": 5000.00,
  "currency": "USD",
  "coverages": [
    {
      "name": "Cyber Liability",
      "limit": 1000000,
      "deductible": 10000
    }
  ],
  "authority": {
    "decision": "auto_execute",
    "reason": "Premium within auto-quote limit."
  }
}
```

Premium of **$5,000** for $1M coverage limit with $10K deductible. The authority engine approved auto-execution since the premium is within the auto-quote threshold.

---

## Step 4: Bind Policy (Senior UW)

```http
POST /api/v1/submissions/{id}/bind
X-User-Role: senior_uw
```

**Response (200):**
```json
{
  "submission_id": "9ffa233b-895a-4738-bb26-3c0f12523272",
  "policy_id": "3068fac8-4df7-4d45-b8fe-506c265ba3cb",
  "status": "bound",
  "authority": {
    "decision": "auto_execute",
    "reason": "Premium within auto-bind limit."
  }
}
```

Policy **POL-2026-1190B6** created. Submission status changed to "bound".

---

## Step 5: File a Claim (Claims Adjuster)

```http
POST /api/v1/claims
X-User-Role: claims_adjuster
```

**Payload:**
```json
{
  "policy_id": "3068fac8-4df7-4d45-b8fe-506c265ba3cb",
  "claim_type": "ransomware",
  "description": "Ransomware attack on production systems. Attackers encrypted 85% of server infrastructure and demanded $500K ransom. Estimated loss includes business interruption, forensic investigation, data recovery, and notification costs.",
  "date_of_loss": "2025-06-15",
  "reported_by": "NexGen Robotics CISO",
  "contact_email": "ciso@nexgenrobotics.ai"
}
```

**Response (201 Created):**
```json
{
  "id": "e987b456-550f-43f3-b410-fa2d6f0db96c",
  "claim_number": "CLM-18584710",
  "status": "reported",
  "severity": "medium",
  "total_reserved": 0.0
}
```

---

## Step 6: Set Reserve (Claims Manager)

The initial adjuster reserve attempt was **escalated** because $180K exceeds adjuster authority. A claims_manager completed the reserve:

```http
POST /api/v1/claims/{id}/reserve
X-User-Role: claims_manager
```

**Payload:**
```json
{
  "category": "indemnity",
  "amount": 180000,
  "currency": "USD",
  "notes": "Initial reserve for ransomware remediation, business interruption, notification costs"
}
```

**Response (201 Created):**
```json
{
  "claim_id": "e987b456-550f-43f3-b410-fa2d6f0db96c",
  "reserve_id": "910bcede-e27f-437f-bed9-6eb3246f6c2f",
  "category": "indemnity",
  "amount": 180000.0,
  "total_reserved": 180000.0,
  "authority": {
    "decision": "require_approval",
    "reason": "Reserve requires CCO approval."
  }
}
```

---

## Step 7: Verification

### 7a. Submission Detail
```http
GET /api/v1/submissions/9ffa233b-895a-4738-bb26-3c0f12523272
```
- Status: **bound** ✓
- Risk Score: **6.0** ✓
- Triage and underwriting decision records created ✓

### 7b. Policy
```http
GET /api/v1/policies/3068fac8-4df7-4d45-b8fe-506c265ba3cb
```
- Policy Number: **POL-2026-1190B6** ✓
- Status: **active** ✓
- Premium: **$5,000** ✓

### 7c. Claim
```http
GET /api/v1/claims/e987b456-550f-43f3-b410-fa2d6f0db96c
```
- Claim Number: **CLM-18584710** ✓
- Status: **reserved** ✓
- Total Reserved: **$180,000** ✓

### 7d. Compliance Decisions
```http
GET /api/v1/compliance/decisions
```
- Total decisions: **112** (includes triage, underwriting, and policy_review for this case)
- Decision records include confidence scores and reasoning chains ✓

### 7e. Metrics Summary
```http
GET /api/v1/metrics/summary
```
| Metric | Value |
|---|---|
| Total Submissions | 1,619 |
| Active Policies | 573 |
| Open Claims | 139 |
| GWP | $27,327,318.60 |
| Loss Ratio | 62.1% |
| Bind Rate | 21.9% |

---

## Entity IDs Reference

| Entity | ID |
|---|---|
| Submission | `9ffa233b-895a-4738-bb26-3c0f12523272` |
| Quote | `4678186f-0d4a-4a24-8f12-37aaf8efd723` |
| Policy | `3068fac8-4df7-4d45-b8fe-506c265ba3cb` |
| Claim | `e987b456-550f-43f3-b410-fa2d6f0db96c` |
| Reserve | `910bcede-e27f-437f-bed9-6eb3246f6c2f` |

---

## Roles Used

| Step | Role | Purpose |
|---|---|---|
| 1. Create Submission | `broker` | Submit new business |
| 2. Triage | `underwriter` | AI-assisted risk assessment |
| 3. Quote | `underwriter` | Generate premium |
| 4. Bind | `senior_uw` | Bind policy |
| 5. File Claim | `claims_adjuster` | Report loss |
| 6. Set Reserve | `claims_manager` | Authorize reserve (>adjuster limit) |

## Authority Escalation

The platform's authority engine enforces role-based limits:
- **Auto-quote**: Premium ≤ $500K (auto-approved)
- **Auto-bind**: Premium ≤ $500K (auto-approved)
- **Claims reserve**: Adjuster limit exceeded at $180K → escalated to claims_manager
- **High reserves**: Claims manager's reserve still flagged for CCO approval
