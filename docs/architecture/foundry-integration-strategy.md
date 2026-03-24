# Foundry Integration Strategy

> **Status:** Proposed  
> **Date:** 2025-07-15  
> **Authors:** Backend + Insurance Squad  
> **Scope:** Evaluate native Foundry Agent Service capabilities and recommend migration path from custom Python implementations.

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current Architecture](#current-architecture)
3. [Foundry Native Capabilities Analysis](#foundry-native-capabilities-analysis)
4. [What We Built That Foundry Already Does](#what-we-built-that-foundry-already-does)
5. [New Foundry vs Old Foundry API](#new-foundry-vs-old-foundry-api)
6. [Recommended Architecture](#recommended-architecture)
7. [Migration Path](#migration-path)

---

## Executive Summary

OpenInsure currently integrates with Microsoft Foundry Agent Service for LLM reasoning but builds substantial custom infrastructure around it: knowledge retrieval, enrichment, comparable accounts, learning loops, and MCP tooling. After studying the Foundry Agent Service documentation, we identified **six native capabilities** that could replace or augment our custom code, plus one capability (MCP tool consumption) that would fundamentally change our architecture from "app calls agents" to "agents call app."

**Key finding:** Our highest-value custom code (submission-specific knowledge injection, comparable account matching, EU AI Act compliance) has no Foundry equivalent and should be preserved. However, we should migrate knowledge retrieval to Azure AI Search, enrichment to web search + function calling, and session continuity to Foundry Memory.

---

## Current Architecture

### How We Integrate with Foundry Today

```
┌─────────────────────────────────────────────────────┐
│  OpenInsure Application                             │
│                                                     │
│  ┌──────────────┐    ┌───────────────────────────┐  │
│  │  Agent Layer  │───>│  Knowledge + Context      │  │
│  │  (base.py)   │    │  - prompts.py             │  │
│  │              │    │  - knowledge_store.py      │  │
│  │  execute():  │    │  - comparable_accounts.py  │  │
│  │  1. Build    │    │  - learning_loop.py        │  │
│  │     prompt   │    │  - enrichment.py           │  │
│  │  2. Inject   │    └───────────────────────────┘  │
│  │     context  │                                    │
│  │  3. Call     │    ┌───────────────────────────┐  │
│  │     Foundry  │───>│  FoundryAgentClient       │  │
│  │  4. Parse    │    │  - responses.create()     │  │
│  │     result   │    │  - agent_reference        │  │
│  │  5. Create   │    │  - JSON parsing           │  │
│  │     Decision │    │  - Fallback handling       │  │
│  │     Record   │    └──────────┬────────────────┘  │
│  └──────────────┘               │                    │
│                                  │                    │
│  ┌──────────────┐               │                    │
│  │  MCP Server  │               │                    │
│  │  (27 tools)  │               │                    │
│  │  Exposes API │               │                    │
│  │  to clients  │               │                    │
│  └──────────────┘               │                    │
└─────────────────────────────────┼────────────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │  Microsoft Foundry        │
                    │  Agent Service            │
                    │                           │
                    │  10 prompt agents          │
                    │  (gpt-5.1 model)          │
                    │  - No tools attached      │
                    │  - No knowledge base      │
                    │  - No memory              │
                    │  - Single-turn only       │
                    │  - Text in → text out     │
                    └───────────────────────────┘
```

### Current Flow (Prompt Injection Pattern)

1. Agent `execute()` is called with a task (e.g., triage a submission)
2. `_build_prompt()` assembles context:
   - Underwriting guidelines filtered by LOB, industry, SIC, revenue, security score
   - Comparable accounts with loss ratios from `ComparableAccountFinder`
   - Historical accuracy metrics from `DecisionOutcomeTracker`
   - Enrichment data from `EnrichmentService`
3. The complete prompt (task + all context) is sent to Foundry via `FoundryAgentClient.invoke()`
4. Foundry agent processes the prompt and returns JSON
5. Response is parsed, wrapped in a `DecisionRecord`, and returned

### Key Limitation

Foundry agents are **stateless text processors** in our current setup. They receive everything they need in a single prompt and return a single response. All intelligence about what context to retrieve and how to use it lives in our Python code, not in the agents.

---

## Foundry Native Capabilities Analysis

### A1. Azure AI Search Tool ✅ HIGH VALUE

**What it does:** Agents can natively query an Azure AI Search vector index. The agent decides when to search, formulates queries, and incorporates results — all without application code.

**Current state:** We inject knowledge via `prompts.py` → `knowledge_store.py` (in-memory static data) with fallback to Cosmos DB. Knowledge is pre-selected by the application and stuffed into the prompt.

**Impact:** Instead of our app deciding what knowledge is relevant and injecting it, the agent could query an Azure AI Search index on demand. The agent sees the full submission and autonomously searches for relevant guidelines, rating factors, and regulatory requirements.

**Prerequisites:**
- Azure AI Search resource with vector index
- `Edm.String` fields (searchable + retrievable) and `Collection(Edm.Single)` vector fields
- Project connection between Foundry and Search
- RBAC: `Search Index Data Contributor` + `Search Service Contributor` on project managed identity
- Supports: SIMPLE, VECTOR, SEMANTIC, VECTOR_SIMPLE_HYBRID, VECTOR_SEMANTIC_HYBRID queries

**Recommendation:** **Adopt.** Index our knowledge base (underwriting guidelines, regulatory requirements, coverage rules, ACORD specs) into Azure AI Search. Attach `AzureAISearchToolDefinition` to each agent. This replaces `knowledge_store.py` and the prompt-injection pattern in `prompts.py`.

### A2. File Search ✅ MEDIUM VALUE

**What it does:** Agents search uploaded files in a vector store using semantic + keyword search. Supports PDF, Word, Markdown, and more.

**Current state:** We don't use file search. Comparable accounts are computed in Python (`comparable_accounts.py`), and ACORD documents are processed by `document_intelligence.py`.

**Impact:** Could replace comparable account retrieval — upload historical submissions/policies as files, let the agent search for similar ones. Also useful for searching ACORD form definitions, policy wordings, and claims precedents.

**Prerequisites:**
- Create vector store via REST API
- Upload files and attach to vector store
- Attach `FileSearchTool` with `vector_store_ids` to agent

**Recommendation:** **Adopt for document-heavy use cases** (ACORD forms, policy wordings). For comparable accounts, Azure AI Search with structured data is better than file search over raw documents.

### A3. Function Calling ✅ HIGH VALUE

**What it does:** Define custom functions the agent can invoke. The agent decides when to call them, provides arguments, and your app executes the function and returns results.

**Current state:** All data retrieval happens before the agent is called. The agent never calls back to our APIs.

**Impact:** Agents could call our APIs on demand:
- `GET /api/v1/knowledge/rating-factors/{lob}` — fetch rating factors
- `GET /api/v1/submissions/{id}` — fetch submission details
- `GET /api/v1/analytics/loss-ratio/{lob}` — fetch portfolio metrics
- `POST /api/v1/enrichment/enrich` — trigger external enrichment

This inverts the control flow: instead of us pre-loading everything, the agent requests what it needs.

**Recommendation:** **Adopt selectively.** Start with read-only functions (knowledge queries, enrichment). Avoid write operations until trust is established. Use `strict=True` for schema validation.

### A4. Memory ✅ HIGH VALUE

**What it does:** Persistent agent memory across sessions, devices, and workflows. Stores user preferences, conversation summaries, and user profiles. Memory is partitioned per user via `scope`.

**Current state:** We have `DecisionOutcomeTracker` (`learning_loop.py`) which tracks AI decisions vs. real-world outcomes in-memory. This data is injected into prompts so agents see their own performance history.

**Impact:** Foundry Memory could:
- Store per-user preferences (underwriter risk appetite, preferred formats)
- Maintain conversation history across sessions
- Build agent-specific knowledge (e.g., "Healthcare submissions are typically underpriced by 15%")

**Prerequisites:**
- Embedding model deployment (e.g., `text-embedding-3-small`)
- System-assigned managed identity on project
- `Azure AI User` role on AI Services resource

**Recommendation:** **Adopt for user preferences and session continuity.** Our learning loop is more specialized (decision-vs-outcome tracking with accuracy metrics) and should be preserved as a complement to Foundry Memory, not replaced by it.

### A5. MCP Tool Consumption ✅ TRANSFORMATIVE

**What it does:** Foundry agents can connect to remote MCP servers and call tools exposed by them. The agent discovers available tools and calls them on demand.

**Current state:** Our MCP server (`mcp/server.py`) exposes 27 tools and 5 resources to external clients (GitHub Copilot, Claude Desktop). But our own Foundry agents don't consume it — they receive pre-assembled prompts.

**Impact:** This is the most transformative capability. If Foundry agents consumed our MCP server, they could:
- Create submissions, file claims, generate documents **on their own**
- Query analytics, check compliance, run workflows
- Access any of our 27 tools on demand

This shifts from "app orchestrates agents" to "agents orchestrate themselves via MCP."

**Prerequisites:**
- MCP server must be deployed as a remote HTTP endpoint (Azure Container Apps or Azure Functions)
- `MCPTool` attached to agent with `server_url` pointing to deployed MCP endpoint
- Approval workflow for sensitive operations (`require_approval="always"`)
- 100-second timeout per MCP call

**Recommendation:** **Adopt as the long-term architecture.** Deploy MCP server to Azure Container Apps, attach as `MCPTool` on orchestrator agent. Use `require_approval` for write operations. This enables true autonomous agent workflows.

### A6. Code Interpreter ✅ MEDIUM VALUE

**What it does:** Agents run Python in a sandboxed environment. Supports data analysis, chart generation, file processing.

**Current state:** Actuarial calculations (premium computation, loss ratio analysis) are done in our Python services. The agent only receives pre-computed results.

**Impact:** Agents could run their own actuarial calculations:
- Premium = base_rate × industry_factor × revenue_band × security_modifier × incident_multiplier
- Loss ratio trending over time
- Reserve adequacy analysis with statistical methods

**Recommendation:** **Adopt for analytics agent.** The `openinsure-analytics` agent would benefit from running its own calculations over portfolio data. Not needed for transactional agents (submission, policy, claims).

### A7. Web Search ✅ MEDIUM VALUE

**What it does:** Real-time public web search with citations. No setup required — works out of the box.

**Current state:** Enrichment is simulated (`enrichment.py` generates deterministic fake data based on submission hash). No real external data.

**Impact:** The enrichment agent could search for:
- Company news and financial reports
- Security breach databases and vulnerability disclosures
- Industry benchmarks and regulatory changes
- Competitor analysis

**Prerequisites:** None (works out of the box). Note: Data Protection Addendum does NOT apply to data sent to Bing.

**Recommendation:** **Adopt for enrichment agent** with caution. Web search data is untrusted — validate before use in underwriting decisions. Good complement to structured enrichment APIs.

---

## What We Built That Foundry Already Does

| Custom Component | Foundry Native Alternative | Replace? | Notes |
|---|---|---|---|
| `knowledge_store.py` — In-memory static knowledge | **Azure AI Search tool** — Vector index with semantic search | **Yes** | Index our guidelines, rating factors, regulatory docs into AI Search |
| `prompts.py` — Context assembly + injection | **Azure AI Search + Function Calling** — Agent retrieves own context | **Partially** | Agent autonomously searches; we keep submission-specific filtering logic |
| `comparable_accounts.py` — Similar submission matching | **File Search** over historical submissions OR **Azure AI Search** with structured index | **Yes** | Structured search (AI Search) preferred over file search for tabular data |
| `learning_loop.py` — Decision outcome tracking | **Foundry Memory** — Persistent agent memory | **No** | Our learning loop tracks decision accuracy quantitatively; Memory is for user preferences/summaries. Keep both. |
| `enrichment.py` — External data simulation | **Web Search + Function Calling** — Real external data | **Yes** | Replace simulated data with real web search + API calls |
| `mcp/server.py` — MCP server for external clients | **MCP Tool** — Foundry agents consume MCP servers | **Complement** | Don't replace; let Foundry agents also consume our MCP server |
| `foundry_client.py` — Responses API wrapper | **SDK `create_version` + Responses API** | **Keep** | Still needed for invocation; update to new API patterns |
| `base.py` — DecisionRecord / EU AI Act compliance | **No equivalent** | **Keep** | Foundry has no compliance audit trail — this is our differentiator |
| `orchestrator.py` — Multi-agent workflow engine | **Foundry Workflows** (portal-based) | **Not yet** | Foundry workflows are portal-only; our code-based orchestrator is more flexible |

---

## New Foundry vs Old Foundry API

### API Comparison

| Aspect | Old (Classic) API | New Foundry API |
|---|---|---|
| **Create agent** | `client.agents.create_agent(model=..., name=..., instructions=...)` | `client.agents.create_version(agent_name=..., definition=PromptAgentDefinition(...))` |
| **List agents** | `client.agents.list_agents()` | `client.agents.list()` |
| **Delete agent** | `client.agents.delete_agent(agent_id)` | `client.agents.delete(agent_name=name)` |
| **Invoke agent** | threads + runs (`create_and_process`) | `openai_client.responses.create(..., extra_body={"agent": {"name": ..., "type": "agent_reference"}})` |
| **Portal visibility** | Classic portal only | Both classic and new Foundry portal |
| **Versioning** | No versioning | Built-in version management |
| **Agent type** | Implicit | Explicit: `kind: "prompt"` via `PromptAgentDefinition` |
| **Tools** | `tools=[...]` parameter on `create_agent` | `tools=[...]` in `PromptAgentDefinition` |

### SDK Requirements

```bash
pip install azure-ai-projects --pre  # v2.x preview required
pip install azure-identity
```

### Environment Variables

```bash
PROJECT_ENDPOINT=https://<resource>.services.ai.azure.com/api/projects/<project>
MODEL_DEPLOYMENT_NAME=gpt-5.1
OPENAI_API_VERSION=2025-05-01-preview
```

### Creating Agents (New API)

```python
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition
from azure.identity import DefaultAzureCredential

client = AIProjectClient(
    endpoint=os.environ["PROJECT_ENDPOINT"],
    credential=DefaultAzureCredential(),
)

agent = client.agents.create_version(
    agent_name="my-agent",
    definition=PromptAgentDefinition(
        model="gpt-5.1",
        instructions="You are a helpful assistant.",
        tools=[...],  # Optional: WebSearchPreviewTool, AzureAISearchToolDefinition, etc.
    ),
)
```

### Invoking Agents (Responses API)

```python
openai_client = client.get_openai_client()

response = openai_client.responses.create(
    input=[{"role": "user", "content": "Hello"}],
    extra_body={"agent": {"name": "my-agent", "type": "agent_reference"}},
)
```

> **Note:** The `extra_body` key is `"agent"`, not `"agent_reference"`. Our `foundry_client.py` currently uses `"agent_reference"` which may work but should be updated to match the documented pattern.

---

## Recommended Architecture

### Target State

```
┌───────────────────────────────────────────────────────────────┐
│  OpenInsure Application                                       │
│                                                               │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐  │
│  │ Compliance    │     │ Orchestrator │     │  MCP Server  │  │
│  │ (EU AI Act)   │     │ (workflows)  │     │  (27 tools)  │◄─┤─ GitHub Copilot
│  │ DecisionRecord│     │              │     │              │◄─┤─ Claude Desktop
│  └──────────────┘     └──────────────┘     └──────┬───────┘  │
│                                                    │          │
└────────────────────────────────────────────────────┼──────────┘
                                                     │
                    ┌────────────────────────────────┼──────────┐
                    │  Microsoft Foundry Agent Service│          │
                    │                                ▼          │
                    │  ┌─────────────────────────────────────┐  │
                    │  │  Foundry Agents (10)                │  │
                    │  │                                     │  │
                    │  │  Tools:                             │  │
                    │  │  ├── Azure AI Search (knowledge)    │  │
                    │  │  ├── Web Search (enrichment)        │  │
                    │  │  ├── Function Calling (APIs)        │  │
                    │  │  ├── MCP (OpenInsure tools) ────────┤──┤── Calls our MCP server
                    │  │  ├── Code Interpreter (analytics)   │  │
                    │  │  └── Memory (session continuity)    │  │
                    │  └─────────────────────────────────────┘  │
                    │                                           │
                    │  ┌─────────────────────────────────────┐  │
                    │  │  Azure AI Search Index              │  │
                    │  │  - Underwriting guidelines          │  │
                    │  │  - Rating factors by LOB            │  │
                    │  │  - Regulatory requirements          │  │
                    │  │  - Coverage rules                   │  │
                    │  │  - ACORD form definitions           │  │
                    │  │  - Claims precedents                │  │
                    │  └─────────────────────────────────────┘  │
                    │                                           │
                    │  ┌─────────────────────────────────────┐  │
                    │  │  File Search Vector Store           │  │
                    │  │  - Historical submissions           │  │
                    │  │  - Policy documents                 │  │
                    │  │  - Claims files                     │  │
                    │  └─────────────────────────────────────┘  │
                    │                                           │
                    │  ┌─────────────────────────────────────┐  │
                    │  │  Memory Store                       │  │
                    │  │  - User preferences                 │  │
                    │  │  - Conversation summaries           │  │
                    │  │  - Underwriter risk appetite        │  │
                    │  └─────────────────────────────────────┘  │
                    └───────────────────────────────────────────┘
```

### What Changes

| Concern | Current (Prompt Injection) | Target (Foundry-Native) |
|---|---|---|
| **Knowledge retrieval** | App queries in-memory store, injects into prompt | Agent queries Azure AI Search index natively |
| **Enrichment** | App calls simulated providers, injects results | Agent uses Web Search + Function Calling for real data |
| **Comparable accounts** | App computes similarity scores, injects matches | Agent queries AI Search index with submission attributes |
| **Session memory** | None (single-turn) | Foundry Memory persists user preferences across sessions |
| **Tool execution** | MCP server serves external clients only | Foundry agents consume MCP server for self-service operations |
| **Actuarial calculations** | Python services compute, inject results | Analytics agent uses Code Interpreter for on-demand computation |
| **Learning loop** | App tracks accuracy, injects metrics into prompt | **Preserved** — injected as system context; no Foundry equivalent |
| **EU AI Act compliance** | App creates DecisionRecords per decision | **Preserved** — Foundry has no compliance audit trail |
| **Multi-agent orchestration** | Python orchestrator chains agents | **Preserved** — Foundry portal workflows are less flexible |

### What We Keep (Our Differentiators)

1. **DecisionRecord / EU AI Act compliance** — No Foundry equivalent. Every AI decision must produce an auditable record.
2. **Learning loop with accuracy tracking** — Foundry Memory stores preferences, not quantitative decision-vs-outcome metrics.
3. **Multi-agent orchestrator** — Our code-based orchestrator supports conditional routing, escalation thresholds, and parallel execution that Foundry portal workflows don't.
4. **RBAC + authority limits** — Domain-specific access control (e.g., auto-bind authority < $100K).
5. **Graceful fallback** — When Foundry is unavailable, safe defaults prevent system failure.

---

## Migration Path

### Phase 1: Fix Agent Registration (Quick Win — Days)

**What:** Update `create_foundry_agents.py` to use `create_version()` API.  
**Why:** Agents created with old `create_agent()` API are only visible in classic portal.  
**How:** Already done — see updated script in this PR.

**Deliverables:**
- [x] `create_foundry_agents.py` uses `create_version()` with `PromptAgentDefinition`
- [x] Sets `OPENAI_API_VERSION=2025-05-01-preview`
- [x] Uses `gpt-5.1` model
- [x] Consistent with `deploy_foundry_agents.py`

### Phase 2: Azure AI Search Knowledge Base (High Value — Weeks)

**What:** Index our knowledge base into Azure AI Search. Attach `AzureAISearchToolDefinition` to agents.  
**Why:** Replaces in-memory knowledge store. Agents autonomously retrieve relevant knowledge.  
**Dependencies:** Azure AI Search resource, project connection, RBAC setup.

**Steps:**
1. Provision Azure AI Search resource
2. Create index schema: guidelines, rating factors, regulatory requirements, coverage rules
3. Index content from `knowledge/` directory and `knowledge_store.py` data
4. Create project connection between Foundry and AI Search
5. Assign RBAC: `Search Index Data Contributor` + `Search Service Contributor`
6. Update agent definitions to include `AzureAISearchToolDefinition`
7. Test: verify agents retrieve correct knowledge for different LOBs/industries
8. Deprecate `knowledge_store.py` prompt injection (keep as fallback)

### Phase 3: Web Search for Enrichment (Medium Value — Weeks)

**What:** Enable `WebSearchPreviewTool` on the enrichment agent. Replace simulated data with real web search.  
**Why:** Real external data for underwriting decisions.  
**Dependencies:** None (web search works out of the box).

**Steps:**
1. Add `WebSearchPreviewTool` to `openinsure-enrichment` agent definition
2. Update enrichment agent instructions to search for: company news, breach databases, financial reports
3. Add instructions for citation/source tracking
4. Test: verify enrichment returns real, sourced data
5. Deprecate `enrichment.py` simulated providers

### Phase 4: Foundry Memory (Medium Value — Weeks)

**What:** Enable persistent memory for agents. Store user preferences and conversation context.  
**Why:** Enables multi-session continuity without our app managing state.  
**Dependencies:** Embedding model deployment (`text-embedding-3-small`).

**Steps:**
1. Deploy embedding model
2. Create memory store with `chat_summary_enabled` and `user_profile_enabled`
3. Configure `user_profile_details` to exclude sensitive financial/PII data
4. Attach `MemorySearchTool` to relevant agents (underwriting, claims)
5. Test: verify agents recall user preferences across sessions
6. Keep learning loop (`learning_loop.py`) as complement — it tracks different data

### Phase 5: MCP Tool Consumption (Transformative — Months)

**What:** Deploy MCP server to Azure Container Apps. Attach as `MCPTool` on Foundry agents.  
**Why:** Agents can call OpenInsure APIs on demand — true autonomous workflows.  
**Dependencies:** MCP server deployed as remote HTTP endpoint.

**Steps:**
1. Deploy MCP server to Azure Container Apps (we have Dockerfile)
2. Create project connection for MCP authentication
3. Attach `MCPTool` to orchestrator agent:
   - `server_url`: Container Apps endpoint
   - `require_approval`: `"always"` for write operations, `{"never": ["get_submission", "list_submissions", ...]}` for reads
   - `allowed_tools`: Start with read-only subset
4. Test: verify agent can call MCP tools and get results
5. Gradually expand `allowed_tools` as trust is established
6. Long-term: orchestrator agent manages entire workflows via MCP

### Phase 6: Function Calling + Code Interpreter (Medium Value — Months)

**What:** Define custom functions for structured API access. Enable Code Interpreter for analytics.  
**Why:** Function calling gives agents type-safe API access. Code Interpreter enables on-demand computation.

**Steps:**
1. Define function schemas for key APIs (knowledge queries, enrichment, analytics)
2. Add `FunctionTool` definitions to relevant agents
3. Enable `CodeInterpreterTool` on analytics agent
4. Test: verify function calls return correct data, code execution produces valid results

### Priority Matrix

| Phase | Value | Effort | Risk | Priority |
|---|---|---|---|---|
| 1. Fix Agent Registration | Low | Low | Low | **P0 — Do now** |
| 2. Azure AI Search | High | Medium | Medium | **P1 — Next sprint** |
| 3. Web Search Enrichment | Medium | Low | Low | **P1 — Next sprint** |
| 4. Foundry Memory | Medium | Medium | Low | **P2 — This quarter** |
| 5. MCP Consumption | High | High | Medium | **P2 — This quarter** |
| 6. Function Calling + Code Interpreter | Medium | Medium | Low | **P3 — Next quarter** |
