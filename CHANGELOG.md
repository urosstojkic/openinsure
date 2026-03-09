# Changelog

All notable changes to OpenInsure will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
