# Issue Lifecycle

## Flow
Issue Created → Labeled `squad` → Lead triages → `squad:{agent}` label → Branch created → Implementation → PR → Review → Merge → Issue closes

## Branch Naming
`squad/{issue-number}-{slug}` (e.g., `squad/156-referential-integrity`)

## PR Requirements
- Title references issue: `fix: enforce referential integrity (#156)`
- Body includes `Closes #156`
- All quality gates pass
- Completion checklist signed off
