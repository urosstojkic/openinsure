# Work Routing

How to decide who handles what.

## Routing Table

| Work Type | Route To | Examples |
|-----------|----------|----------|
| Backend API, services, repos | Backend | New endpoints, SQL repos, workflow engine, Foundry integration |
| React pages, components, UX | Frontend | Dashboard pages, components, API clients, Tailwind styling |
| Azure infra, Bicep, CI/CD | Infra | Container Apps, SQL networking, GitHub Actions, deploy scripts |
| Insurance domain, products, regs | Insurance | Underwriting rules, claims workflows, reinsurance, ACORD, EU AI Act |
| Tests, quality gates, Playwright | QA | Unit tests, E2E tests, smoke tests, coverage, Playwright audits |
| Security, RBAC, auth, audit | Security | Authority engine, JWT/API key auth, bias monitoring, audit trail |
| Docs, history, decisions | Scribe | README, architecture docs, decision records, session logs |
| Code review | QA + Security | Review PRs, check quality, suggest improvements |
| Scope & priorities | Insurance | What to build next, trade-offs, domain decisions |
| Async issue work (bugs, tests, small features) | @copilot 🤖 | Well-defined tasks matching capability profile |
| Session logging | Scribe | Automatic — never needs routing |

## Issue Routing

| Label | Action | Who |
|-------|--------|-----|
| `squad` | Triage: analyze issue, evaluate @copilot fit, assign `squad:{member}` label | Lead |
| `squad:{name}` | Pick up issue and complete the work | Named member |
| `squad:copilot` | Assign to @copilot for autonomous work (if enabled) | @copilot 🤖 |

### How Issue Assignment Works

1. When a GitHub issue gets the `squad` label, the **Lead** triages it — analyzing content, evaluating @copilot's capability profile, assigning the right `squad:{member}` label, and commenting with triage notes.
2. **@copilot evaluation:** The Lead checks if the issue matches @copilot's capability profile (🟢 good fit / 🟡 needs review / 🔴 not suitable). If it's a good fit, the Lead may route to `squad:copilot` instead of a squad member.
3. When a `squad:{member}` label is applied, that member picks up the issue in their next session.
4. When `squad:copilot` is applied and auto-assign is enabled, `@copilot` is assigned on the issue and picks it up autonomously.
5. Members can reassign by removing their label and adding another member's label.
6. The `squad` label is the "inbox" — untriaged issues waiting for Lead review.

### Lead Triage Guidance for @copilot

When triaging, the Lead should ask:

1. **Is this well-defined?** Clear title, reproduction steps or acceptance criteria, bounded scope → likely 🟢
2. **Does it follow existing patterns?** Adding a test, fixing a known bug, updating a dependency → likely 🟢
3. **Does it need design judgment?** Architecture, API design, UX decisions → likely 🔴
4. **Is it security-sensitive?** Auth, encryption, access control → always 🔴
5. **Is it medium complexity with specs?** Feature with clear requirements, refactoring with tests → likely 🟡

## Rules

1. **Eager by default** — spawn all agents who could usefully start work, including anticipatory downstream work.
2. **Scribe always runs** after substantial work, always as `mode: "background"`. Never blocks.
3. **Quick facts → coordinator answers directly.** Don't spawn an agent for "what port does the server run on?"
4. **When two agents could handle it**, pick the one whose domain is the primary concern.
5. **"Team, ..." → fan-out.** Spawn all relevant agents in parallel as `mode: "background"`.
6. **Anticipate downstream work.** If a feature is being built, spawn the tester to write test cases from requirements simultaneously.
7. **Issue-labeled work** — when a `squad:{member}` label is applied to an issue, route to that member. The Lead handles all `squad` (base label) triage.
8. **@copilot routing** — when evaluating issues, check @copilot's capability profile in `team.md`. Route 🟢 good-fit tasks to `squad:copilot`. Flag 🟡 needs-review tasks for PR review. Keep 🔴 not-suitable tasks with squad members.

## Branch Strategy

All squad work uses the naming convention: `squad/{issue-number}-{slug}`

Examples:
- `squad/156-referential-integrity`
- `squad/201-add-reinsurance-api`
- `squad/189-fix-claim-state-machine`

See `.squad/templates/issue-lifecycle.md` for the full issue-to-merge flow.

## Parallel Execution Rules

Agents are grouped into dependency tiers that determine execution ordering:

| Tier | Agents | Execution | Rationale |
|------|--------|-----------|-----------|
| **P0 — Lead** | Lead (coordinator) | Sequential | Must triage and assign before others start |
| **P1 — Specialists** | Backend, Frontend, Insurance, Security | Parallel OK | Independent domain owners; can work simultaneously |
| **P2 — Supporting** | QA, Scribe, Infra | Parallel OK | Can run alongside P1 or after P1 completes |

### Parallel Execution Guidelines

1. **P1 agents can always run in parallel** with each other (e.g., Backend + Frontend on the same feature).
2. **P2 agents can run in parallel** with P1 or each other (e.g., QA writes tests while Backend implements).
3. **P0 (Lead) is sequential** — triage and routing must complete before specialist work begins.
4. **Cross-tier dependencies** — if a P2 agent (e.g., QA) depends on P1 output (e.g., Backend API), the P2 agent should wait for the dependency to complete.
5. **Fan-out pattern** — for "Team, ..." requests, spawn all relevant P1+P2 agents in parallel.

## Dependency Tiers

- **P0 = Lead (sequential):** Triage, routing, priority decisions. Must complete before work begins.
- **P1 = Specialists (parallel OK):** Backend, Frontend, Insurance, Security. Own their domains independently.
- **P2 = Supporting (parallel OK):** QA, Scribe, Infra. Support P1 work and can run concurrently.
