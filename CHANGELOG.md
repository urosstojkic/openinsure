# Changelog

All notable changes to OpenInsure will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.6.0] — 10/10 AI-Native with Foundry Tools

### Added
- **Azure AI Search Knowledge Tool**: All 10 Foundry agents now have `AzureAISearchToolDefinition` attached. Agents autonomously search the `openinsure-knowledge` index for underwriting guidelines, rating factors, regulatory requirements, and coverage rules — replacing the prompt injection pattern in `prompts.py`.
  - Knowledge indexer script: `src/scripts/index_knowledge.py` — parses YAML knowledge files into chunked documents with hybrid vector + keyword schema, optional embeddings via `text-embedding-ada-002`, `--dry-run` support
  - Index schema: `id`, `content`, `title`, `category`, `source`, `tags`, `content_vector` (1536-dim HNSW)
- **Web Search for Enrichment**: `openinsure-enrichment` agent gets `WebSearchPreviewToolDefinition` for real-time company research, breach database lookups, and regulatory change detection. Replaces simulated data from `enrichment.py`.
- **Foundry Memory for Session Continuity**: `openinsure-underwriting` and `openinsure-claims` agents get `MemoryToolDefinition` for cross-session user preference storage, conversation summaries, and agent knowledge accumulation.
- **Function Calling for Underwriting**: `openinsure-underwriting` agent gets two `FunctionToolDefinition` tools:
  - `get_rating_factors(lob)` — fetches cyber insurance rating factors by line of business
  - `get_comparable_accounts(industry_sic, annual_revenue?, employee_count?)` — finds similar historical accounts for pricing comparison
- **Multi-Turn Conversation Support**: `foundry_client.py` now supports Foundry conversations via `create_conversation()` and `invoke_in_conversation()`. The existing `invoke()` method accepts an optional `conversation_id` kwarg for backward compatibility.
- **Canonical Deploy Script**: `src/scripts/deploy_foundry_agents.py` is now the single source of truth for agent deployment — creates all 10 agents with tools, discovers search connections at runtime, environment-driven configuration.

### Changed
- `config.py`: Added `search_connection_id` setting for Foundry project connection to AI Search
- `.env`: Added `OPENINSURE_FOUNDRY_PROJECT_ENDPOINT` for Foundry Agent Service
- `foundry_client.py`: Refactored JSON parsing into `_parse_response()` static method (DRY)
- `docs/architecture/foundry-integration-strategy.md`: Updated status to "Implemented (Phases 1–4)" with full implementation log

### Architecture
- **Tool assignment matrix**: AI Search (all agents), Web Search (enrichment), Memory (underwriting + claims), Function Calling (underwriting)
- **Graceful degradation**: All tools are optional — agents deploy without tools when connections are unavailable
- **Preserved**: DecisionRecord/EU AI Act compliance, learning loop, orchestrator, knowledge_store fallback, enrichment fallback

## [0.5.0] — AI-Native Knowledge Pipeline

### Added
- **Decision Learning Loop** (`services/learning_loop.py`): Tracks AI decision outcomes for continuous improvement. When claims are filed or policies renew/cancel, outcomes are correlated with the original triage/quote/bind decisions. Computes per-agent accuracy metrics and detects systematic biases (e.g., "Healthcare submissions were underpriced by 15%"). Historical accuracy context is injected into agent prompts so agents self-correct over time.
  - API: `GET /api/v1/analytics/decision-accuracy`, `POST /api/v1/analytics/decision-outcome`
  - MCP tool: `get_decision_accuracy`
  - Closes #86
- **Comparable Account Retrieval** (`services/comparable_accounts.py`): When assessing a new submission, agents now see how similar past submissions were handled. Matches by LOB, industry (SIC prefix), revenue band (±50%), employee count (±50%), and security maturity. Returns pricing history, claim outcomes, and loss ratios.
  - API: `GET /api/v1/submissions/{id}/comparables`
  - MCP tool: `get_comparable_accounts`
  - Triage prompt includes: "COMPARABLE ACCOUNTS: 3 similar tech companies — 2 proceeded, 1 declined"
  - Underwriting prompt includes: "COMPARABLE PRICING: Similar companies priced at $8K-$15K. Average loss ratio: 42%"
  - Closes #87
- **Dynamic Knowledge Retrieval** (enhanced `agents/prompts.py`): Knowledge retrieval is now contextual per submission. A healthcare company gets HIPAA rules, a fintech gets PCI/GLBA requirements, and a ransomware-heavy industry gets ransomware precedents. Jurisdiction-aware regulatory context (US/EU/UK) is included automatically.
  - New knowledge store methods: `get_industry_guidelines()`, `get_compliance_rules_for_jurisdiction()`, `get_claims_precedents_by_type()`
  - 6 industry profiles: healthcare, financial_services, technology, retail, manufacturing, education
  - 3 jurisdiction profiles: US, EU, UK
  - Closes #88
- **55 new unit tests** covering all three features (520 total, up from 465)
- **2 new MCP tools** (`get_decision_accuracy`, `get_comparable_accounts`) bringing total to 29

### Changed
- `build_triage_prompt()` and `build_underwriting_prompt()` now accept `dynamic_knowledge`, `comparable_context`, and `learning_context` keyword arguments for AI-native context injection
- `build_prompt_for_step()` (workflow engine dispatcher) automatically retrieves and injects learning loop context, comparable accounts, and dynamic knowledge for intake and underwriting steps
- `InMemoryKnowledgeStore` expanded with industry-specific guidelines, jurisdiction compliance rules, and fuzzy claims precedent matching

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
