# AiScrum Pro ↔ Squad Integration Guide

## How AiScrum Pro Works With the Squad Framework

AiScrum Pro provides **sprint structure** (ceremonies, quality gates, velocity tracking).
The Squad provides **domain expertise** (insurance knowledge, backend patterns, security rules).
claude-code-prompts provides **quality patterns** (verification, anti-rationalization, memory).

### Worker Prompt Template

When AiScrum Pro dispatches a worker for an issue, the prompt should include:

```
You are working on OpenInsure issue #{issue_number}: {title}

## Squad Context
Read the relevant Squad charter before implementing:
- Backend work: `.squad/agents/backend/charter.md`
- Frontend work: `.squad/agents/frontend/charter.md`
- Security work: `.squad/agents/security/charter.md`
- Insurance domain: `.squad/agents/insurance/charter.md`

## Project Context
Read `.github/copilot-instructions.md` for the project bible.
Read `knowledge/learned/` for known gotchas specific to this codebase.

## Quality Requirements (from completion checklist)
Before marking done, verify:
- [ ] ruff check + format pass
- [ ] All tests pass
- [ ] Dashboard builds (if frontend changes)
- [ ] Foundry smoke test (if agent-related changes)
- [ ] No stubs/fallbacks in live mode

## Anti-Rationalization (from Verification Specialist)
- Do NOT just "read the code and decide it looks correct" — execute it
- Do NOT rely solely on unit tests — verify independently  
- Run at least one adversarial probe before marking PASS
- If you're thinking "this is probably fine" — stop and run the actual check

## Synthesis Mandate
Your prompt must be self-contained. Cite file paths, line numbers, and exact changes.
```

### Challenger Agent Integration

AiScrum Pro's challenger agent should use the Verifier charter:
```
Read `.squad/agents/verifier/charter.md` for your mandate.
Your job is to TRY TO BREAK the implementation, not confirm it works.
```

### Sprint Retro → Knowledge Extraction

After each sprint retro, extract learnings to `knowledge/learned/`:
- New SQL gotchas → `knowledge/learned/sql-gotchas.md`
- New deployment quirks → `knowledge/learned/deployment-quirks.md`
- New Foundry patterns → `knowledge/learned/foundry-patterns.md`
- New portal lessons → `knowledge/learned/portal-lessons.md`

### Escalation Model

AiScrum Pro decides HOW to implement. The human decides WHAT to build.
Always escalate:
- Architecture changes (new tables, new services)
- Breaking API changes
- Infrastructure cost changes
- Security policy changes
