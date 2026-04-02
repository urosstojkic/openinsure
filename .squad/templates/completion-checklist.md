# Agent Completion Checklist

Before marking work as done, verify:

## Code Quality
- [ ] ruff check + format pass
- [ ] mypy passes (if applicable)
- [ ] bandit has no high-severity findings
- [ ] No hardcoded env-specific URLs

## Testing
- [ ] Unit tests added for new code
- [ ] All existing tests pass (750+)
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

## Verification (Anti-Rationalization)
- [ ] I did NOT just "read the code and decide it looks correct" — I executed it
- [ ] I did NOT rely solely on AI-written unit tests — I verified independently
- [ ] I ran at least one adversarial probe (boundary values, error input, concurrent request)
- [ ] Every PASS claim is backed by actual command output, not inference
- [ ] If I'm thinking "this is probably fine" — I stopped and ran the actual check

## Deployment
- [ ] Dashboard builds (`npm run build`)
- [ ] Backend builds (Docker)
- [ ] Deployed and verified on live
