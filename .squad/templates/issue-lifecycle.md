# Issue Lifecycle

## Flow
Issue Created → Labeled `squad` → Lead triages → `squad:{agent}` label → Branch created → Implementation → PR created → Quality gates pass → **Agent merges PR** → Issue auto-closes

## Branch Naming
`squad/{issue-number}-{slug}` (e.g., `squad/156-referential-integrity`)

## PR Requirements
- Title references issue: `fix: enforce referential integrity (#156)`
- Body includes `Closes #156`
- All quality gates pass (lint, tests, build, Foundry smoke test)
- Completion checklist signed off

## Auto-Merge (MANDATORY)
Agents MUST merge their own PRs after quality gates pass. The user should NOT need to intervene:
```bash
# Create PR
gh pr create --base main --head squad/{issue}-{slug} --title "{type}: {description} (#{issue})" --body "Closes #{issue}"

# Merge (squash into main)
gh pr merge {pr_number} --squash --admin --subject "{type}: {description} (#{issue})"
```

Never leave branches unmerged. If merge conflicts exist, resolve them before merging.
