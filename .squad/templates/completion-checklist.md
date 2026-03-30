# Agent Completion Checklist

Before marking work as done, verify:

## Code Quality
- [ ] ruff check + format pass
- [ ] mypy passes (if applicable)
- [ ] bandit has no high-severity findings
- [ ] No hardcoded env-specific URLs

## Testing
- [ ] Unit tests added for new code
- [ ] All existing tests pass (636+)
- [ ] Foundry smoke test passes (if agent-related)
- [ ] Integration test against live backend (if API changes)

## Insurance Domain
- [ ] State machine transitions are valid
- [ ] Authority limits respected
- [ ] Audit trail records created for mutations

## Documentation
- [ ] CHANGELOG.md updated
- [ ] Feature guide updated (if user-facing)
- [ ] TECHNICAL_OVERVIEW.md updated (if architectural)
- [ ] copilot-instructions.md metrics refreshed

## Deployment
- [ ] Dashboard builds (`npm run build`)
- [ ] Backend builds (Docker)
- [ ] Deployed and verified on live
