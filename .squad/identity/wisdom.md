---
last_updated: 2026-03-19
---

# Team Wisdom

Reusable patterns and heuristics learned through work. NOT transcripts — each entry is a distilled, actionable insight.

## North Star Documents

All development decisions must align with these two specifications:

1. **`docs/architecture/architecture-spec-v01.md`** — The technical architecture specification. Defines: AI-native design principles, Microsoft Foundry platform architecture, knowledge graph approach, core domain modules (submission, underwriting, policy, claims, billing, compliance), agent taxonomy (3 tiers), data architecture, EU AI Act compliance, integration architecture, MCP server, open source strategy, and Phase 1 cyber insurance MVP scope.

2. **`docs/architecture/operating-model-v02.md`** — The organizational and operating model. Defines: carrier-first/MGA-deployable architecture, 16+ personas with Entra ID roles, RBAC data access matrix, action authority matrix, human-agent authority model (complexity × consequence), 7 detailed business process workflows, 12 role-specific dashboard specifications, escalation matrix, deployment profiles (carrier vs MGA), and 4-phase implementation priority.

**When in doubt, read the spec.** These documents are the source of truth for what OpenInsure should be.

## Patterns

**Pattern:** Foundry-first for all AI judgment. **Context:** Every operation involving triage, risk assessment, pricing, reserve estimation, fraud detection, compliance checking, or coverage analysis MUST call the deployed Microsoft Foundry agents (GPT-5.1). Local Python logic is ONLY a fallback when Foundry is unreachable.

**Pattern:** Enterprise-grade, no mocking in production paths. **Context:** All data flows through Azure SQL. Dashboard shows real data from the backend API. Mock data exists only as a graceful fallback when the backend is unreachable.

**Pattern:** Authority model enforcement. **Context:** Every bind, quote, settlement, and reserve action must check the AuthorityEngine before executing. The complexity × consequence matrix from the operating model determines whether an action is auto-executed, recommended, or requires approval.

**Pattern:** Decision Records for every AI action. **Context:** EU AI Act compliance requires every agent decision to produce an immutable DecisionRecord with reasoning chain, confidence score, data sources, and human oversight status.

**Pattern:** Quality compromises must be tracked. **Context:** When a technical compromise is made (e.g., using a different Azure service than specified), create a GitHub issue with the "quality" label explaining what was compromised, why, the impact, and the resolution path.
