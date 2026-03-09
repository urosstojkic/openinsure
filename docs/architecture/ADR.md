# Architectural Decision Records (ADR)

This document captures the key architectural decisions for **OpenInsure**, the open-source AI-native insurance platform.

---

## ADR-001: Python + FastAPI for Backend

**Status:** Accepted  
**Date:** 2025-01-15  
**Deciders:** Platform Architecture Team

### Context

OpenInsure is an AI-native insurance platform that requires deep integration with machine-learning models, natural language processing, and multi-agent orchestration. The backend must handle async I/O efficiently (API calls to Azure services, AI model inference) while maintaining a productive developer experience.

### Decision

Use **Python 3.12+** with **FastAPI** as the primary backend framework.

### Rationale

- **AI/ML ecosystem:** Python is the de facto language for AI/ML. Libraries like scikit-learn, PyTorch, LangChain, Semantic Kernel, and the Azure AI SDK are Python-first. Using Python avoids costly FFI bridges.
- **Async support:** FastAPI is built on Starlette and uvicorn, providing native `async/await` for high-throughput concurrent I/O — critical when orchestrating multiple Azure service calls per request.
- **Type safety:** FastAPI's integration with Pydantic provides runtime validation and automatic OpenAPI schema generation, reducing bugs and improving developer experience.
- **Team expertise:** The founding engineering team has strong Python experience; ramping on a new language would delay delivery.
- **Community:** FastAPI is one of the fastest-growing Python frameworks with excellent documentation and a large contributor base.

### Consequences

- Compute-intensive operations (e.g., actuarial simulations) may need to be offloaded to background workers or compiled extensions.
- Deployment uses containerised uvicorn workers behind Azure Container Apps.
- GIL limitations are mitigated by async I/O and process-based scaling.

### Alternatives Considered

| Alternative | Why Not |
|---|---|
| Go + gRPC | Smaller AI/ML library ecosystem; steeper learning curve for data science team |
| Node.js + TypeScript | Weaker ML/AI library support; less natural for data pipeline work |
| Java + Spring Boot | Heavier framework; slower iteration cycle for AI experimentation |

---

## ADR-002: Pydantic v2 for Domain Entities

**Status:** Accepted  
**Date:** 2025-01-15  
**Deciders:** Platform Architecture Team

### Context

The insurance domain has complex entity models (policies, claims, submissions) with strict validation rules. These entities cross service boundaries (API ↔ domain ↔ database) and must be serialised to/from JSON, database rows, and event payloads.

### Decision

Use **Pydantic v2** as the foundation for all domain entities and value objects.

### Rationale

- **Validation:** Pydantic enforces constraints at construction time (e.g., premium > 0, dates in valid ranges), preventing invalid state from propagating.
- **Serialisation:** Native `.model_dump()` / `.model_validate()` handles JSON, dict, and ORM conversion with zero boilerplate.
- **Type safety:** Full `mypy` and IDE support through standard Python type annotations.
- **Performance:** Pydantic v2's Rust-based core (pydantic-core) is 5–50× faster than v1 for validation-heavy workloads.
- **FastAPI integration:** FastAPI uses Pydantic models directly for request/response schemas and OpenAPI generation.

### Consequences

- All domain entities inherit from `pydantic.BaseModel` with `model_config = {"frozen": True}` for immutability where appropriate.
- Custom validators use `@field_validator` and `@model_validator` decorators.
- Database ORMs (if used) map to/from Pydantic models rather than being used directly in the domain layer.

---

## ADR-003: Azure SQL + Cosmos DB Dual Storage

**Status:** Accepted  
**Date:** 2025-01-18  
**Deciders:** Platform Architecture Team, Data Engineering

### Context

OpenInsure needs to store both structured transactional data (policies, claims, financials) and highly connected knowledge data (product graphs, coverage relationships, regulatory mappings). A single storage technology cannot optimally serve both patterns.

### Decision

Use a **dual storage** strategy:
- **Azure SQL Database** for relational, transactional data (policies, claims, accounting).
- **Azure Cosmos DB** (Gremlin API) for the knowledge graph (products, coverages, regulatory rules, relationships).

### Rationale

- **ACID transactions:** Insurance transactions (binding a policy, recording a payment) require strong consistency and ACID guarantees that Azure SQL provides natively.
- **Graph queries:** The knowledge base (product → coverage → exclusion → regulation relationships) is naturally a graph. Gremlin traversals are far more expressive than SQL JOINs for path-finding and recommendation queries.
- **Scalability:** Cosmos DB provides global distribution and elastic throughput for read-heavy knowledge queries; Azure SQL provides predictable performance for write-heavy transactional workloads.
- **Azure-native:** Both are first-party Azure services with managed backups, patching, and AAD integration.

### Consequences

- Two connection adapters must be maintained (`DatabaseAdapter`, `CosmosGraphAdapter`).
- Cross-store consistency is handled via domain events (eventual consistency).
- Data migration requires separate strategies for relational and graph stores.

---

## ADR-004: Event-Driven Architecture with Event Grid + Service Bus

**Status:** Accepted  
**Date:** 2025-01-20  
**Deciders:** Platform Architecture Team

### Context

Insurance workflows are inherently asynchronous and multi-step (submission → underwriting → quoting → binding → issuance). Multiple services need to react to domain events (e.g., "policy bound" triggers billing, document generation, and compliance logging). The system must also maintain a complete audit trail for regulatory compliance.

### Decision

Use **Azure Event Grid** for domain event publication and **Azure Service Bus** for reliable message processing with dead-letter support.

### Rationale

- **Loose coupling:** Services publish events without knowing subscribers. New capabilities (e.g., analytics, notifications) subscribe without modifying producers.
- **Audit trail:** Every domain event is persisted, creating an immutable audit log that satisfies EU AI Act Art. 12 record-keeping requirements.
- **Reliability:** Service Bus provides at-least-once delivery, dead-letter queues for failed messages, and sessions for ordered processing.
- **Scalability:** Event Grid handles millions of events per second; Service Bus queues decouple producers from consumers under load.
- **Azure-native:** Both services integrate with Managed Identity (no shared keys) and Azure Monitor.

### Consequences

- All significant domain actions must emit events through the `EventBusAdapter`.
- Services must be idempotent (at-least-once delivery means duplicate events are possible).
- Dead-letter queues must be monitored and reprocessed operationally.

---

## ADR-005: Microsoft Agent Framework for AI Orchestration

**Status:** Accepted  
**Date:** 2025-01-22  
**Deciders:** Platform Architecture Team, AI Engineering

### Context

OpenInsure uses multiple specialised AI agents (underwriting, claims, compliance, portfolio management). These agents must collaborate, share context, and operate under enterprise governance constraints (audit logging, human oversight, access control).

### Decision

Use the **Microsoft Agent Framework** (Azure AI Foundry) for multi-agent orchestration.

### Rationale

- **Foundry integration:** Native integration with Azure AI Foundry provides model management, prompt versioning, and evaluation tooling out of the box.
- **Multi-agent patterns:** Built-in support for agent-to-agent delegation, shared memory, and conversation management — exactly what insurance workflows require.
- **Enterprise governance:** The framework provides guardrails, content filtering, and audit logging that align with EU AI Act requirements.
- **MCP compatibility:** The framework supports Model Context Protocol, enabling external tools and agents to interact with OpenInsure through a standardised interface.
- **Ecosystem:** Microsoft's investment in the agent framework ensures long-term support, security patches, and feature development.

### Consequences

- Agent definitions follow the framework's agent specification pattern.
- All agent interactions are logged through the compliance layer.
- Custom tools are exposed as MCP tools for framework compatibility.

---

## ADR-006: EU AI Act Compliance-by-Design

**Status:** Accepted  
**Date:** 2025-01-25  
**Deciders:** Platform Architecture Team, Legal, Compliance

### Context

The EU AI Act (Regulation 2024/1689) classifies AI systems used in insurance pricing and underwriting as **high-risk** (Annex III). Full compliance with obligations for high-risk AI systems is required by **August 2, 2026**. Non-compliance carries fines of up to 15 million EUR or 3 % of global turnover.

### Decision

Implement EU AI Act compliance as a **first-class architectural concern** — built into every layer from day one, not retrofitted.

### Rationale

- **August 2026 deadline:** The 18-month implementation window is tight; retroactive compliance would require a costly rewrite.
- **Penalty risk:** The fines are material. Building compliance into the architecture is cheaper than remediation after an enforcement action.
- **Market differentiator:** Early compliance signals trust and maturity to regulators, reinsurers, and enterprise customers.
- **Insurance-specific:** Insurance AI is explicitly high-risk under Annex III. There is no ambiguity about applicability.

### Implementation

| Requirement | Component |
|---|---|
| Art. 9 — Risk Management | `BiasMonitor`, risk scoring with human override |
| Art. 10 — Data Governance | Training data lineage tracked in knowledge graph |
| Art. 11 — Technical Documentation | ADRs, architecture docs, model cards |
| Art. 12 — Record-Keeping | `DecisionRecordStore`, `AuditTrailStore` |
| Art. 13 — Transparency | Explanation generation in every agent decision |
| Art. 14 — Human Oversight | Referral triggers, authority levels, escalation workflows |

### Consequences

- Every AI decision must produce a `DecisionRecord` with full reasoning chain.
- Bias monitoring runs on every decision type on a scheduled basis.
- Human oversight is enforced for decisions exceeding auto-bind authority.
- Documentation must be maintained as a living artefact.

---

## ADR-007: ACORD-Aligned Modern JSON/REST API

**Status:** Accepted  
**Date:** 2025-01-28  
**Deciders:** Platform Architecture Team, Integration Engineering

### Context

Insurance data exchange has historically relied on ACORD XML standards. While ACORD provides valuable data models and terminology, the XML-based transport is heavyweight and poorly suited to modern API-first architectures. OpenInsure must interoperate with carriers, brokers, and MGA platforms while remaining developer-friendly.

### Decision

Adopt **ACORD-aligned data models** expressed as **modern JSON/REST APIs** — using ACORD terminology and concepts without requiring legacy XML serialisation.

### Rationale

- **Interoperability:** ACORD's data dictionary provides a shared vocabulary understood across the insurance industry. Using the same field names and entity relationships ensures semantic compatibility.
- **Developer experience:** JSON/REST is the standard for modern API consumers. OpenAPI/Swagger documentation is auto-generated from Pydantic models.
- **No legacy XML constraints:** ACORD XML schemas are verbose and difficult to validate programmatically. JSON Schema provides equivalent validation with better tooling.
- **Incremental adoption:** Teams familiar with ACORD concepts can onboard quickly; teams new to insurance get well-documented field definitions.
- **MCP compatibility:** The MCP tool interface naturally maps to JSON request/response patterns.

### Consequences

- Domain entities use ACORD-aligned field names where applicable (e.g., `line_of_business`, `coverage_code`, `deductible`).
- An ACORD XML adapter may be added later for legacy integrations but is not part of the core API.
- API versioning follows REST conventions (`/api/v1/...`).
