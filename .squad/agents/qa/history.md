# QA Agent — History

## Learnings

- Tests run with storage_mode=memory by default — no Azure needed
- SQL repo changes require updating tests that reference status values (received vs submitted)
- E2E tests must handle both mock and real API responses
- Playwright testing verifies deployed Azure Container Apps dashboards
