# Changelog

All notable changes to OpenInsure will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] - 2026-03-19

### Added
- ProcessWorkflowModal: Microsoft Foundry AI pipeline visualization in dashboard
- Squad agent team: 7 specialized development agents with persistent knowledge
- 3-year comprehensive seed script (1,200 submissions, 420 policies, 85 claims)
- Real SQL data rendering on all dashboard pages (field mapping fixes)
- Process buttons on Submissions and Claims pages

### Fixed
- SQL→dashboard field mapping (dates, names, severities, totals)
- Dashboard mock fallback restored for resilience
- SQL network access persistence
- CI pipeline green (lint + mypy fixes)

## [0.3.0] - 2026-07-22

### Added

- **Reinsurance Management**: Treaty lifecycle management (quota share, excess-of-loss, surplus, facultative), automatic cession calculation on policy bind, capacity utilization tracking, recovery calculation on claim payments, bordereau generation, Reinsurance Dashboard
- **Actuarial Analytics**: Loss development triangle generation, IBNR estimation (chain-ladder method), reserve adequacy analysis by LOB and accident year, rate adequacy testing, Actuarial Workbench with interactive triangles and charts
- **MGA Oversight**: Delegated authority management and monitoring, bordereaux ingestion and validation, authority utilization tracking, performance scoring and audit trail, MGA Oversight Dashboard with scorecards
- **Renewal Management**: 90/60/30-day renewal identification, automated renewal term generation, renewal processing (auto or manual review)
- **Financial Reporting**: Premium analytics (written, earned, unearned), claims analytics (paid, reserved, incurred), cash flow management and forecasting, commission tracking and reconciliation, Finance Dashboard
- **REST API endpoints**: `/api/v1/reinsurance/*`, `/api/v1/actuarial/*`, `/api/v1/mga/*`, `/api/v1/renewals/*`, `/api/v1/finance/*`
- **Test suite**: Expanded to 375 tests covering all new modules and Foundry AI pipeline

## [0.1.0] - 2026-03-09

### Added

- **Core Domain Model**: Party, Submission, Policy, Claim, Product, Billing entities (Pydantic v2)
- **REST API**: Full CRUD endpoints for all insurance operations (FastAPI)
- **AI Agent Framework**: Base agent class with EU AI Act decision record logging
  - Submission Agent (intake, extraction, triage)
  - Underwriting Agent (risk assessment, pricing, authority management)
  - Policy Agent (lifecycle: bind, endorse, renew, cancel)
  - Claims Agent (FNOL, coverage verification, reserving, settlement)
  - Document Agent (classification, extraction, generation)
  - Knowledge Agent (knowledge graph queries)
  - Compliance Agent (audit, bias monitoring, regulatory checking)
  - Multi-agent Orchestrator (new business and claims workflows)
- **Azure Infrastructure (Bicep IaC)**:
  - Azure SQL Database (transactional data)
  - Cosmos DB with Gremlin API (knowledge graph)
  - Azure AI Search (vector + keyword hybrid)
  - Azure Blob Storage (documents)
  - Azure Event Grid + Service Bus (event-driven architecture)
  - Managed Identity + RBAC (security)
  - Azure Monitor + Application Insights (observability)
- **Compliance Layer**:
  - Decision Record store (EU AI Act Art. 12)
  - Immutable audit trail
  - Bias monitoring with 4/5ths rule detection
- **Knowledge Base**:
  - Cyber liability SMB product definition
  - Cyber underwriting guidelines
  - US regulatory requirements
- **MCP Server**: OpenInsure exposed as MCP server for agent integration
- **CI/CD**: GitHub Actions pipeline (lint, type check, security scan, tests)
- **Documentation**: README, CONTRIBUTING, SECURITY, ADRs, deployment guide
