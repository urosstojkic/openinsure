# Learned Knowledge Index

Extracted lessons from OpenInsure development. These are things we learned the hard way — recurring mistakes, environment quirks, and non-obvious patterns that are not documented elsewhere.

## Categories

| File | Category | Key Topics |
|------|----------|------------|
| [sql-gotchas.md](sql-gotchas.md) | Database | Column mappings, NULL constraints, type coercion |
| [deployment-quirks.md](deployment-quirks.md) | DevOps | ARM64 issues, Azure policies, Container Apps, build context |
| [foundry-patterns.md](foundry-patterns.md) | AI/Agents | Agent invocation format, SDK patterns, timeouts |
| [portal-lessons.md](portal-lessons.md) | Frontend | API routing, nginx config, timeout handling, UX patterns |

## How to Use

1. **Before implementing:** Check if there's a known gotcha for the area you're working in
2. **After debugging:** Add new learnings to the appropriate file (or create a new one)
3. **Periodic review:** Run memory consolidation to merge, update, and prune stale entries

## Confidence Levels

- **High:** Verified multiple times, root cause understood
- **Medium:** Observed once, fix confirmed but root cause may have alternatives
- **Low:** Suspected pattern, needs more evidence
