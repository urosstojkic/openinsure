# Project Context

- **Project:** openinsure
- **Created:** 2026-03-19

## Core Context

Agent Scribe initialized and ready for work.

## Recent Updates

📌 Team initialized on 2026-03-19

### 2025-07-24 — Documentation Consolidation

Consolidated all project documentation into a clean, non-redundant structure:

- **`.github/copilot-instructions.md`** rewritten as 8-section development bible (12.8KB):
  1. Project Vision, 2. Squad-First Development, 3. Current Platform State,
  4. Architecture Quick Reference, 5. Key URLs, 6. Development Patterns,
  7. Deploy Process, 8. Documentation Map
- Removed duplicate pre-merge checklist (was listed in two separate sections)
- Added verified platform metrics: 448+ tests, 24 dashboard pages, 90+ endpoints,
  6 Foundry agents, 16 MCP tools
- Updated README.md with accurate counts and added MCP + process completeness sections
- Deduplicated AGENTS.md quality gates (now references copilot-instructions)
- Fixed stale numbers in developer-guide.md architecture diagram

**Principle applied**: every fact exists in exactly ONE place; other docs link to it.

## Learnings

- Dashboard has 24 pages (not 22 as previously documented)
- Test count is 448 (verify before updating docs)
- The copilot-instructions.md file uses LF line endings (not CRLF) after rewrite
- Process completeness is ~75% per the Insurance agent's assessment
- Key redundancies were: quality gates (4 places), coding conventions (3 places),
  insurance domain context (3 places)
