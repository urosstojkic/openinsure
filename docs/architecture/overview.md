# OpenInsure — Architecture Overview

## Introduction

OpenInsure is an **open-source, AI-native insurance platform** designed for Managing General Agents (MGAs), carriers, and insurtech startups. It combines modern software architecture with EU AI Act compliance-by-design to deliver a platform that is transparent, auditable, and production-ready.

This document provides a human-readable overview of the system architecture.

---

## High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                        External Consumers                            │
│   MCP-compatible Agents  │  Broker Portals  │  API Clients          │
└──────────────┬───────────┴──────────┬───────┴──────────┬────────────┘
               │                      │                  │
               ▼                      ▼                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         API Gateway (FastAPI)                        │
│   /api/v1/submissions  │ /api/v1/quotes │ /api/v1/policies │ ...   │
│                         MCP Server Interface                        │
└──────────────┬──────────────────────────────────────────┬───────────┘
               │                                          │
      ┌────────▼────────┐                        ┌────────▼────────┐
      │  Agent Layer     │                        │  Compliance     │
      │  (AI Foundry)    │                        │  Layer          │
      │                  │                        │                 │
      │ • Underwriting   │◄──────────────────────►│ • Decision      │
      │ • Claims         │   Every decision is    │   Records       │
      │ • Portfolio      │   logged & monitored   │ • Audit Trail   │
      │ • Compliance     │                        │ • Bias Monitor  │
      └────────┬─────────┘                        └─────────────────┘
               │
      ┌────────▼────────────────────────────────────────────┐
      │                   Domain Services                    │
      │  Submission │ Quoting │ Binding │ Claims │ Products  │
      └────────┬────────────────────────────────┬───────────┘
               │                                │
  ┌────────────▼────────────┐    ┌──────────────▼──────────────┐
  │   Transactional Store   │    │      Knowledge Graph         │
  │   (Azure SQL)           │    │   (Cosmos DB — Gremlin)      │
  │                         │    │                              │
  │ • Policies              │    │ • Products & Coverages       │
  │ • Claims                │    │ • Regulatory Rules           │
  │ • Submissions           │    │ • Underwriting Guidelines    │
  │ • Financial Txns        │    │ • Industry Classifications   │
  └─────────────────────────┘    └──────────────────────────────┘
               │                                │
               └────────────────┬───────────────┘
                                │
  ┌─────────────────────────────▼──────────────────────────────────┐
  │                    Event Bus (Event Grid + Service Bus)         │
  │                                                                │
  │  submission.received → underwriting.started → quote.created    │
  │  policy.bound → claim.reported → compliance.check.completed    │
  └────────────────────────────────────────────────────────────────┘
               │                                │
  ┌────────────▼─────────┐    ┌─────────────────▼──────────────┐
  │   Document Store     │    │    AI Search                    │
  │   (Blob Storage)     │    │   (Azure AI Search)             │
  │                      │    │                                 │
  │ • Policy Documents   │    │ • Hybrid Vector + Keyword       │
  │ • Claim Evidence     │    │ • Knowledge Base Indexing       │
  │ • Regulatory Filings │    │ • Product Recommendations       │
  └──────────────────────┘    └─────────────────────────────────┘
```

---

## Layer Descriptions

### API Gateway

The FastAPI application serves as the single entry point for all external interactions. It provides:

- **REST API** endpoints for submissions, quotes, policies, and claims.
- **MCP Server** interface that allows any MCP-compatible agent to discover and invoke OpenInsure tools and resources.
- **Authentication** via Azure AD / Entra ID with role-based access control.
- **Rate limiting** and request validation via Pydantic models.

### Agent Layer

Specialised AI agents handle insurance-specific reasoning, powered by Azure AI Foundry:

| Agent | Responsibility |
|---|---|
| **Underwriting Agent** | Evaluates submissions, assesses risk, recommends pricing |
| **Claims Agent** | Processes FNOL, triages claims, recommends reserves |
| **Portfolio Agent** | Monitors portfolio metrics, identifies concentration risk |
| **Compliance Agent** | Validates decisions against regulatory rules and EU AI Act |

Agents operate under strict governance: every decision produces a `DecisionRecord` with full reasoning chain, and authority levels determine when human oversight is required.

### Compliance Layer

The compliance layer is **not** an afterthought — it is woven into every decision path:

- **DecisionRecordStore**: Immutable storage for every AI decision with inputs, outputs, reasoning, and confidence scores (EU AI Act Art. 12).
- **AuditTrailStore**: Append-only event log tracking every system action with actor attribution and correlation IDs.
- **BiasMonitor**: Analyses decision outcomes for disparate impact using the 4/5ths rule, generating reports and recommendations (EU AI Act Art. 9).

### Domain Services

Pure business logic implemented as Python services:

- **Submission Service**: Intake and validation of insurance applications.
- **Quoting Service**: Premium calculation based on product rating factors.
- **Binding Service**: Policy issuance with payment processing.
- **Claims Service**: FNOL intake, triage, reserve setting, and settlement.
- **Product Service**: Product catalogue management backed by the knowledge graph.

### Infrastructure Adapters

Thin adapters wrap Azure services, providing a clean interface to the domain:

| Adapter | Azure Service | Purpose |
|---|---|---|
| `DatabaseAdapter` | Azure SQL | Transactional data (ACID) |
| `CosmosGraphAdapter` | Cosmos DB (Gremlin) | Knowledge graph queries |
| `BlobStorageAdapter` | Blob Storage | Document management |
| `EventBusAdapter` | Event Grid + Service Bus | Domain event publishing |
| `SearchAdapter` | Azure AI Search | Hybrid vector + keyword search |

All adapters use `DefaultAzureCredential` for passwordless authentication.

---

## Key Design Principles

1. **Compliance-by-Design**: EU AI Act obligations are architectural constraints, not features to add later.
2. **Event-Driven**: Every significant action emits a domain event, enabling loose coupling and complete audit trails.
3. **Human-in-the-Loop**: AI agents recommend; humans approve above defined thresholds.
4. **ACORD-Aligned**: Industry-standard terminology ensures interoperability without legacy XML overhead.
5. **Cloud-Native**: Designed for Azure Container Apps with managed identity, auto-scaling, and infrastructure-as-code.

---

## Data Flow: Quote-to-Bind

```
1. Broker submits application via API / MCP
         │
         ▼
2. Submission Service validates & stores → Azure SQL
         │
         ├──► Event: submission.received
         │
         ▼
3. Underwriting Agent evaluates risk
   • Queries knowledge graph for product rules
   • Scores risk factors
   • Checks referral triggers
   • Generates DecisionRecord
         │
         ├──► Event: underwriting.completed
         │
         ▼
4. Quoting Service calculates premium
   • Applies rating factors from product YAML
   • Applies territory and industry multipliers
   • Returns quote with coverages and limits
         │
         ├──► Event: quote.created
         │
         ▼
5. Broker reviews and requests bind
         │
         ▼
6. Binding Service issues policy
   • Validates authority level
   • Processes payment
   • Creates policy record
         │
         ├──► Event: policy.bound
         │
         ▼
7. Compliance Agent runs post-bind checks
   • Verifies DecisionRecord completeness
   • Checks bias monitor results
   • Logs audit event
```

---

## Security Model

- **Authentication**: Azure Entra ID (AAD) for all users and services.
- **Authorization**: Role-based access control (RBAC) with insurance-specific roles (underwriter, claims adjuster, compliance officer, actuary).
- **Data Encryption**: TLS 1.3 in transit; Azure-managed encryption at rest.
- **Secrets**: Azure Key Vault for all secrets; no credentials in code or config.
- **Network**: Virtual network isolation with private endpoints for all Azure services.

---

## Deployment Model

OpenInsure is deployed as containerised services on **Azure Container Apps**:

- Auto-scaling based on HTTP traffic and queue depth.
- Blue-green deployments with traffic splitting.
- Infrastructure defined in **Bicep** templates (see `infra/`).
- CI/CD via GitHub Actions (see `.github/workflows/`).

For detailed deployment instructions, see [Azure Setup Guide](../deployment/azure-setup.md).
