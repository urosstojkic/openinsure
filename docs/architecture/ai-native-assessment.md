# AI-Native Assessment: OpenInsure

**Date:** 2025-07-25 (Updated: v0.5.0)
**Assessors:** Insurance + Backend Architecture Review (OpenInsure Squad)
**Verdict:** **AI-Native (8/10)** — closed-loop learning, contextual knowledge, and comparable account retrieval implemented

---

## Executive Summary

OpenInsure has moved from **AI-Assisted** to **AI-Native** with the v0.5.0
knowledge pipeline release. Three critical gaps identified in the original
assessment have been closed:

1. **Decision Learning Loop** — Agent decisions are now tracked against real-world
   outcomes (claims filed, policies renewed/cancelled). Accuracy metrics and
   improvement signals are computed per agent and injected back into prompts,
   enabling self-correcting AI behaviour.

2. **Comparable Account Retrieval** — When assessing a new submission, agents now
   see how similar past submissions were handled (pricing, claim outcomes, loss
   ratios). This is the strongest signal for pricing and is surfaced in both
   triage and underwriting prompts.

3. **Dynamic Knowledge Retrieval** — Knowledge is now contextual per submission.
   A healthcare company gets HIPAA rules and ransomware precedents, a fintech
   gets PCI/GLBA requirements, and jurisdiction-specific regulatory context
   (US/EU/UK) is automatically included.

### Remaining Gaps (2/10)

- ❌ **Foundry fallback** still returns hardcoded defaults (flat $5K premium)
- ❌ **Cross-agent disagreement detection** not yet implemented
- ❌ **Vector/semantic search** (Azure AI Search RAG) not yet integrated
- ❌ **Confidence calibration** against historical outcomes pending

---

## Part A — Current Reality: Agent-by-Agent Assessment

### How Agent Invocation Works

There are **two execution paths** in the codebase:

1. **Foundry path** (`workflow_engine.py` → `prompts.py` → `foundry_client.py`):
   The workflow engine calls `build_prompt_for_step()` which selects the correct
   prompt builder, injects knowledge from `InMemoryKnowledgeStore`, and sends
   the assembled prompt to Foundry via the OpenAI Responses API. This is the
   production path and it **does** include knowledge context.

2. **Local fallback path** (`base.py` → `*.process()`): When Foundry is
   unavailable, the base class `execute()` calls the agent's local `process()`
   method. These methods return **hardcoded safe defaults** — zero risk scores,
   empty classifications, `manual_review_required` flags. The base class
   `_build_prompt()` is a generic serializer that does **not** inject knowledge.

### Agent Assessment Table

| Agent | Intelligence Level | Knowledge Access | Decision Authority | Fallback Quality |
|-------|-------------------|-----------------|-------------------|-----------------|
| **Orchestrator** (`openinsure-orchestrator`) | Reasons over submission to pick processing path (standard/expedited/referral) | Workflow routing rules + authority tiers from knowledge store | Drives routing — determines which agents execute | No dedicated fallback; workflow engine skips orchestration step |
| **Enrichment** (`openinsure-enrichment`) | Synthesizes external risk signals into composite score | Security requirements + benchmark thresholds from knowledge store | Advisory — feeds risk context to underwriting | Step is `required=False`; workflow proceeds without it |
| **Submission/Triage** (`openinsure-submission`) | Classifies appetite match + risk score with guidelines context | Full appetite criteria, SIC codes, revenue ranges, security requirements from LOB-specific guidelines | **Drives triage** — determines proceed/decline/refer; advances submission to `underwriting` status | Returns `risk_score=0.42`, `recommendation=proceed_to_quote` — always passes everything through |
| **Underwriting** (`openinsure-underwriting`) | Prices premium using guidelines + deterministic rating engine breakdown | Full rating factors, industry/security/revenue multipliers, plus `_get_rating_breakdown()` from `CyberRatingEngine` | **Drives premium** — `recommended_premium` becomes `quoted_premium` on the submission | Returns `$5,000` flat — no risk-based pricing |
| **Policy Review** (`openinsure-policy`) | Reviews coverage adequacy, terms completeness, pricing within guidelines | Coverage options + exclusions + subjectivities from knowledge store | Advisory — logged at bind time but doesn't gate issuance | Skipped entirely; bind proceeds without review |
| **Claims** (`openinsure-claims`) | Assesses coverage, severity tier, reserve estimate, fraud score with precedent context | Claims precedents (reserve ranges, resolution times, red flags, case examples) by claim type | **Drives reserve** — `initial_reserve` and `severity_tier` used in claims workflow | Returns `coverage_confirmed=False`, `severity=unknown`, reserve `$0` — useless |
| **Compliance** (`openinsure-compliance`) | Audits all prior step results against EU AI Act articles | EU AI Act requirements (Art. 9-14), NAIC Model Bulletin, GDPR provisions | Advisory — logged but doesn't block; compliance failures are informational | Returns `compliant=False`, empty findings — maximally conservative |
| **Billing** (`openinsure-billing`) | Predicts default probability, recommends billing plan and collection strategy | Payment terms, grace periods, collection escalation thresholds | Advisory — recommendation only | Not invoked on fallback path |
| **Document** (`openinsure-document`) | Generates policy declarations, certificates, coverage schedules | Coverage options + exclusions from knowledge store | **Drives document content** — generated text becomes the policy document | Returns empty document — no document generated |
| **Knowledge** (`openinsure-knowledge`) | Retrieves and formats knowledge for other agents | Self-referential — IS the knowledge layer | Indirect — feeds context to other agents | Returns static Python dicts — functional but frozen |

### Critical Finding: Foundry Fallback Defeats the Purpose

When Foundry is down, the system degrades catastrophically:

**Evidence** (`src/openinsure/agents/submission_agent.py` → `process()`):
- Returns `classifications: {}`, `completeness_pct: 0`, `confidence: 0.0`
- Warning: `"AI unavailable — manual triage required"`

**Evidence** (`src/openinsure/agents/underwriting_agent.py` → `process()`):
- Returns `risk_score: 0`, `within_authority: False`, `status: "pending_referral"`
- Warning: `"AI unavailable — manual underwriting required"`

**Evidence** (`src/openinsure/api/submissions.py` line 551):
- Fallback triage: `{"risk_score": 0.42, "recommendation": "proceed_to_quote", "source": "local"}`
- Every submission passes triage regardless of risk

**Evidence** (`src/openinsure/api/submissions.py` line 712):
- Fallback quote: flat `$5,000.00` premium for every submission regardless of risk profile

**Verdict:** The fallback path makes the system a pass-through that accepts all
submissions at a flat rate. This is **not acceptable** for production insurance
operations. The deterministic rating engine (`CyberRatingEngine`) exists and
could provide meaningful fallback pricing, but is only used to enrich the AI
prompt — never as a standalone fallback.

---

## Part B — Knowledge Base Gap Analysis

### Is Knowledge Retrieval Actually Happening?

**Yes, partially.** The code trace:

1. `workflow_engine.py:262` calls `build_prompt_for_step(step_name, context, entity_id, entity_type)`
2. `prompts.py:688-689` (intake step) calls `get_triage_context(entity_data)` → returns LOB-specific guidelines
3. `prompts.py:34-50` tries Cosmos DB first (`store.query(f"underwriting_guidelines_{lob}")`), falls back to `_static_guidelines()`
4. `_static_guidelines()` calls `_knowledge_store().get_guidelines(lob)` → returns the Python dict for that LOB
5. The guidelines are serialized into the prompt as `UNDERWRITING GUIDELINES (from knowledge base):`

**Knowledge IS injected into prompts.** It is NOT hardcoded in prompt templates.
The `_get_knowledge_context_for_lob()` function (line 87) builds a rich context
string with appetite criteria, rating factors, coverage options, exclusions, and
subjectivities.

### What Knowledge Do Agents See vs. What's Available?

| Agent | What It Sees | What's Available But Not Used |
|-------|-------------|------------------------------|
| Triage | LOB-level appetite + rating factors | Industry-specific risk classifications from `knowledge/guidelines/cyber_underwriting.yaml` (referral triggers, red flags, required controls by tier) |
| Underwriting | LOB-level rating factors + deterministic rating breakdown | State-specific regulatory requirements, authority tiers with premium/limit caps |
| Claims | Claim-type precedents (reserve ranges, red flags, case examples) | Cross-claim pattern analysis, outcome history |
| Compliance | EU AI Act articles + NAIC bulletin | GDPR data retention rules, DPIA requirements |
| Policy | Coverage options + exclusions | Territorial restrictions, form filing requirements by state |
| Document | Coverage descriptions + exclusions | Full product definitions from `knowledge/products/cyber_liability_smb.yaml` |

### Is Knowledge Retrieval Dynamic or Static?

**Dynamic (v0.5.0).** Knowledge varies by:
- ✅ **Line of business** — cyber vs. general_liability vs. property get different guidelines
- ✅ **Claim type** — ransomware vs. data_breach vs. social_engineering get different precedents
- ✅ **Industry** — healthcare gets HIPAA, fintech gets PCI/GLBA, manufacturing gets OT/ICS context
- ✅ **Jurisdiction** — US gets NAIC/state rules, EU gets GDPR/AI Act, UK gets FCA/ICO rules
- ✅ **Revenue tier** — submission-specific guidelines filter by revenue band
- ✅ **Risk profile** — low-security submissions get ransomware precedents, prior incidents trigger breach precedents
- ✅ **Prior decisions** — comparable account retrieval shows how similar past submissions were handled
- ❌ **Semantic search** — knowledge retrieval is rule-based, not vector/RAG-based (future Phase 2)

### Can a Carrier Change Guidelines and Have Agents Use Them Immediately?

**Yes, for the in-memory store.** The `PUT /api/knowledge/guidelines/{lob}` endpoint
(knowledge.py:209) calls `mem.update_guidelines(lob, body)` which mutates the
singleton. All subsequent agent invocations will use the updated guidelines.

**However:** This only works within a single process. There is no persistence
mechanism — restarting the server resets to the Python constants. Cosmos DB is the
intended persistence layer but is optional and rarely configured in dev.

### How Is Knowledge Connected to Foundry?

**Prompt injection only.** Knowledge is serialized as text into the user message
sent to Foundry agents. There is:
- ❌ No RAG (Azure AI Search) integration
- ❌ No Foundry function calling / tool use to query knowledge on demand
- ❌ No vector embeddings or semantic search
- ✅ Structured prompt injection with labeled sections (`UNDERWRITING GUIDELINES:`, `CLAIMS PRECEDENTS:`, etc.)

---

## Part C — What's Missing for True AI-Native

### 1. Knowledge Retrieval Must Be Submission-Specific

**Current state:** `get_triage_context()` queries by LOB only (`underwriting_guidelines_{lob}`).
Every cyber submission gets identical guidelines regardless of the applicant's
industry, size, jurisdiction, or risk profile.

**Required:** Dynamic knowledge retrieval that filters by:
- Industry SIC code → industry-specific risk factors and rate multipliers
- Jurisdiction → state-specific regulatory requirements and filing obligations
- Revenue tier → appropriate authority levels and referral triggers
- Security posture → relevant control requirements and exemptions

### 2. Agent Decisions Must Feed Back Into Knowledge (Learning Loop)

**Current state:** Decisions are recorded via `compliance_repo.store_decision()`
(workflow_engine.py:319) but are **write-only**. No agent ever reads past decisions.
The knowledge store has no mechanism to incorporate outcomes.

**Required:**
- Track decision outcomes (was the policy profitable? was the claim estimate accurate?)
- Feed outcomes back as updated risk factors or precedent adjustments
- Implement a closed-loop: decision → outcome → knowledge update → improved future decisions

### 3. Agents Need Memory of Similar Past Decisions

**Current state:** Each agent invocation is stateless. The submission agent
triaging a healthcare company has no awareness that 50 similar healthcare
submissions were triaged last month, or that 3 of them resulted in claims.

**Required:**
- Comparable account retrieval: query past submissions with similar attributes
- Include outcomes in context: "5 similar accounts bound last quarter, 1 claim filed, avg premium $12K"
- This is the strongest signal for underwriting and must be surfaced to agents

### 4. Cross-Agent Context Passing Must Be Richer

**Current state:** The workflow engine passes step results forward via
`execution.context[f"{step.name}_result"] = resp` (workflow_engine.py:293).
Downstream agents see the raw JSON output of upstream agents.

**What's missing:**
- Confidence propagation — downstream agents should know upstream confidence
- Disagreement detection — if triage says "low risk" but enrichment flags high risk signals, no agent notices
- Context accumulation — the compliance agent should see ALL knowledge that was used, not just step outputs

### 5. Confidence-Based Routing Needs to Actually Drive Decisions

**Current state:** Low confidence (< 0.5) escalates the workflow
(workflow_engine.py:296-310). This is **functional** but:
- The threshold is hardcoded (0.5 for escalation, 0.7 for human oversight flag)
- Confidence values from agents are often default (0.8) when parsing fails
- There's no calibration — is an agent's 0.7 actually reliable?
- The escalation stops the workflow entirely; there's no "continue with human in the loop"

### 6. The Deterministic Rating Engine Is Underutilized

**Current state:** `CyberRatingEngine` exists in `services/rating.py` and
produces detailed factor breakdowns. It's only used to enrich the underwriting
prompt (prompts.py:734-784).

**What's missing:**
- Not used as a validation layer (agent premium vs. engine premium sanity check)
- Not used as the Foundry-down fallback (fallback is flat $5K instead)
- Not used for real-time premium bounds (agent could propose any premium)

---

## Part D — Recommended Architecture Changes

### Phase 1: Fix Knowledge Pipeline (Immediate — This PR)

1. **Make `get_triage_context()` industry-aware** — filter guidelines by
   submission's SIC code / industry to return relevant risk factors
2. **Add jurisdiction context** — include state-specific regulatory requirements
   in compliance and policy review prompts
3. **Use rating engine as fallback** — when Foundry is down, use
   `CyberRatingEngine` for pricing instead of flat $5K
4. **Add tests** — verify different submissions get different knowledge context

### Phase 2: Dynamic Knowledge Retrieval (Next Sprint)

1. **Azure AI Search index** over knowledge base documents (YAML files in
   `knowledge/` directory + Cosmos DB entries)
2. **Semantic search** at prompt-build time: query AI Search with submission
   attributes, return top-k relevant knowledge chunks
3. **Foundry function calling** — configure agents with a `query_knowledge`
   tool so they can pull additional context mid-reasoning

### Phase 3: Closed-Loop Learning (Next Quarter)

1. **Outcome tracking** — add `outcome` field to decision records (claim filed?
   profitable? accurate estimate?)
2. **Outcome-weighted knowledge** — adjust risk factors based on historical
   portfolio performance
3. **Comparable account retrieval** — at triage and underwriting time, query
   SQL for similar past submissions and their outcomes
4. **Confidence calibration** — track predicted vs. actual outcomes to calibrate
   each agent's confidence scores

### Phase 4: True Multi-Agent Coordination (Future)

1. **Agent-to-agent communication** — let agents query each other, not just
   pass JSON forward
2. **Disagreement resolution** — when agents disagree (triage says proceed,
   enrichment says high-risk), escalate with both perspectives
3. **Dynamic workflow routing** — let the orchestrator actually modify the
   workflow based on intermediate results (add/skip steps)
4. **Memory layer** — persistent agent memory across invocations for the same
   account/broker/industry

---

## Appendix: Code Evidence

### Knowledge Injection Flow (Working)

```
submissions.py:480  → get_triage_context(record)
prompts.py:34       → tries Cosmos: store.query(f"underwriting_guidelines_{lob}")
prompts.py:50       → falls back: _static_guidelines(submission)
prompts.py:78       → _knowledge_store().get_guidelines(lob)
knowledge_store.py:539 → returns UNDERWRITING_GUIDELINES["cyber"]
prompts.py:159      → _get_knowledge_context_for_lob(lob) builds rich context string
prompts.py:173      → injected into prompt as SUBMISSION DATA section
foundry_client.py:113 → sent to Foundry via responses.create()
```

### Fallback Path (Broken)

```
submissions.py:548  → Foundry not available
submissions.py:551  → fallback_triage = {"risk_score": 0.42, "recommendation": "proceed_to_quote"}
submissions.py:712  → fallback premium = $5,000.00 (flat, no risk adjustment)
```

### Knowledge Store Coverage

```python
# LOBs with full guidelines:  cyber, general_liability, property
# Claim types with precedents: ransomware, data_breach, business_interruption, social_engineering
# Compliance frameworks:       eu_ai_act, naic_model_bulletin, gdpr
# Billing rules:              payment_terms, grace_periods, collection_escalation
# Workflow rules:             standard/expedited/referral routing, authority_tiers
```

### Files with Knowledge YAML (Not Used by Agents)

```
knowledge/guidelines/cyber_underwriting.yaml  — 251 lines, rich referral triggers + authority tiers
knowledge/products/cyber_liability_smb.yaml   — 92 lines, product definition + rating weights
knowledge/regulatory/us_cyber_requirements.yaml — 249 lines, state filings + EU AI Act
```

These YAML files contain **more detailed knowledge** than the Python constants
but are purely documentary — no code reads them.
