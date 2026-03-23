# MCP Integration — Architecture & Assessment

> **Status:** ✅ Implemented (v1)
> **Last updated:** 2025-07-23
> **Owner:** Backend Agent

---

## A. Current MCP State

### What exists

OpenInsure ships a **standards-compliant MCP server** at `src/openinsure/mcp/server.py` built on the official [Model Context Protocol Python SDK](https://github.com/modelcontextprotocol/python-sdk) (`FastMCP`).

| Component | Path | Status |
|-----------|------|--------|
| MCP server module | `src/openinsure/mcp/server.py` | ✅ 16 tools, 5 resources |
| Package init | `src/openinsure/mcp/__init__.py` | ✅ Exports `mcp` + `OpenInsureMCPServer` |
| CLI entrypoint | `src/openinsure/mcp/__main__.py` | ✅ `python -m openinsure.mcp` |
| Dependency | `pyproject.toml` → `mcp>=1.0.0` | ✅ Added |
| Copilot CLI config | `.copilot/mcp-config.json` | ⚠️ Example only (GitHub MCP) |
| Backward-compat wrapper | `OpenInsureMCPServer` class | ✅ Passes all existing tests |

### What works

- **stdio transport:** `python -m openinsure.mcp` — consumed by Copilot CLI, Claude Desktop, any MCP client
- **SSE transport:** `python -m openinsure.mcp --sse` — consumed by web-based MCP clients
- **16 tools** covering submissions, claims, policies, metrics, compliance, and workflows
- **5 resources** with `insurance://` URI scheme for read-only context
- **Real repository wiring** — tools call actual domain repositories (in-memory or Azure SQL depending on `storage_mode`)
- **Legacy backward compatibility** — `OpenInsureMCPServer` class wraps the FastMCP tools for existing integration tests

### Known limitations

1. **No auth on MCP transport** — the MCP server does not check API keys. In production, MCP access should be gated by transport-level auth (SSH tunnel, mTLS, or API gateway).
2. **Resource handlers** read from the backend API but return `{"error": ...}` if the entity doesn't exist (no stub fallback).
3. **Single-process** — the MCP server runs as its own process, separate from the FastAPI server. Both connect to the same Azure backend.

---

## B. MCP Server Design

### Tool Inventory (16 tools)

#### Submission Tools
| Tool | Description | Parameters |
|------|-------------|------------|
| `create_submission` | Create a new insurance submission | `applicant`, `line_of_business`, `annual_revenue`, `employee_count`, `industry` |
| `get_submission` | Retrieve submission by ID | `submission_id` |
| `list_submissions` | List submissions with optional filter | `status?`, `limit?` |
| `triage_submission` | Run AI triage (appetite, risk, priority) | `submission_id` |
| `quote_submission` | Generate underwriting quote via rating engine | `submission_id`, `annual_revenue`, `employee_count`, `security_score`, `limit`, `deductible` |
| `bind_submission` | Bind a quoted submission → active policy | `submission_id`, `payment_method?` |

#### Claims Tools
| Tool | Description | Parameters |
|------|-------------|------------|
| `file_claim` | First Notice of Loss (FNOL) | `policy_id`, `loss_date`, `description`, `cause_of_loss?`, `estimated_amount?` |
| `get_claim` | Retrieve claim by ID | `claim_id` |
| `list_claims` | List claims with optional filter | `status?`, `limit?` |
| `set_reserve` | Set/update claim reserves | `claim_id`, `amount`, `category?`, `notes?` |

#### Policy Tools
| Tool | Description | Parameters |
|------|-------------|------------|
| `get_policy` | Retrieve policy by ID | `policy_id` |
| `list_policies` | List policies with optional filter | `status?`, `limit?` |

#### Query Tools
| Tool | Description | Parameters |
|------|-------------|------------|
| `get_metrics` | Portfolio dashboard KPIs | *(none)* |
| `get_agent_decisions` | AI decision audit trail | `limit?` |

#### Compliance Tools
| Tool | Description | Parameters |
|------|-------------|------------|
| `run_compliance_check` | EU AI Act compliance check | `decision_id` |

#### Workflow Tools
| Tool | Description | Parameters |
|------|-------------|------------|
| `run_full_workflow` | End-to-end: create → triage → quote → bind | `applicant`, `annual_revenue?`, `employee_count?` |

---

## C. MCP Resources (read-only context)

Resources use the `insurance://` URI scheme and return JSON.

| URI Template | Description |
|-------------|-------------|
| `insurance://submissions/{id}` | Submission details |
| `insurance://policies/{id}` | Policy details including coverages and status |
| `insurance://claims/{id}` | Claim details, reserves, and payment history |
| `insurance://metrics/summary` | Portfolio-level business KPIs |
| `insurance://products/{id}` | Product definition with coverages and rating factors |

---

## D. Usage Guide

### Backend URL Configuration (White-Label)

The MCP server is **white-label ready**. Each tenant points the MCP server
at their own Azure Container Apps backend — no code changes needed.

**Resolution order:**

| Priority | Method | Example |
|----------|--------|---------|
| 1 | `OPENINSURE_API_BASE_URL` env var | `https://acme-insurance.azurecontainerapps.io` |
| 2 | `--api-url` CLI argument | `python -m openinsure.mcp --api-url https://...` |
| 3 | Localhost fallback (dev only) | `http://localhost:8000` |

> **⚠️ Production:** Always set `OPENINSURE_API_BASE_URL`. The localhost fallback
> emits a warning log and is intended for local development only.

### Running the MCP server

```bash
# stdio transport (for Copilot CLI, Claude Desktop)
python -m openinsure.mcp

# With explicit backend URL
python -m openinsure.mcp --api-url https://acme-insurance.swedencentral.azurecontainerapps.io

# SSE transport (for web clients)
python -m openinsure.mcp --sse
```

### Copilot CLI configuration (white-label)

Add to `.copilot/mcp-config.json`, setting `OPENINSURE_API_BASE_URL` to
the tenant's Azure Container Apps backend URL:

```json
{
  "mcpServers": {
    "openinsure": {
      "command": "python",
      "args": ["-m", "openinsure.mcp"],
      "env": {
        "OPENINSURE_API_BASE_URL": "https://acme-insurance.swedencentral.azurecontainerapps.io"
      }
    }
  }
}
```

### Claude Desktop configuration (white-label)

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "openinsure": {
      "command": "python",
      "args": ["-m", "openinsure.mcp"],
      "env": {
        "OPENINSURE_API_BASE_URL": "https://acme-insurance.swedencentral.azurecontainerapps.io"
      }
    }
  }
}
```

### Programmatic usage (Python)

```python
from openinsure.mcp import OpenInsureMCPServer

server = OpenInsureMCPServer()

# Discover tools
tools = await server.list_tools()

# Execute a tool
result = await server.call_tool("get_metrics", {})

# Read a resource
resource = await server.read_resource("insurance://metrics/summary")
```

---

## E. Architecture Diagram

```
┌──────────────────────────────────────────────────────┐
│                    MCP Clients                        │
│  Copilot CLI │ Claude Desktop │ Custom Orchestrators  │
└──────┬───────┴───────┬────────┴───────────┬──────────┘
       │  stdio/SSE    │                    │
       ▼               ▼                    ▼
┌──────────────────────────────────────────────────────┐
│              OpenInsure MCP Server                    │
│          (python -m openinsure.mcp)                  │
│                                                      │
│  ┌─────────────┐ ┌─────────────┐ ┌──────────────┐   │
│  │  16 Tools   │ │ 5 Resources │ │  Instructions │   │
│  └──────┬──────┘ └──────┬──────┘ └──────────────┘   │
└─────────┼───────────────┼────────────────────────────┘
          │               │
          ▼               ▼
┌──────────────────────────────────────────────────────┐
│           OpenInsure Domain Layer                     │
│                                                      │
│  ┌─────────────┐ ┌──────────┐ ┌──────────────────┐  │
│  │ Repositories│ │  Rating  │ │   Compliance     │  │
│  │ (factory)   │ │  Engine  │ │   Repository     │  │
│  └──────┬──────┘ └──────────┘ └──────────────────┘  │
└─────────┼────────────────────────────────────────────┘
          │
          ▼
┌──────────────────────────────────────────────────────┐
│              Storage Backend                          │
│     InMemory (dev) │ Azure SQL + Cosmos (prod)       │
└──────────────────────────────────────────────────────┘
```

---

## F. Implementation Plan — Phase 2 Roadmap

### 1. Foundry Agent Delegation

Wire MCP tools through the AI agent orchestrator instead of calling repositories directly:

```python
@mcp.tool()
async def triage_submission(submission_id: str) -> str:
    # Phase 2: delegate to SubmissionAgent + UnderwritingAgent
    from openinsure.agents.orchestrator import AgentOrchestrator
    orchestrator = AgentOrchestrator()
    result = await orchestrator.triage(submission_id)
    return json.dumps(result.to_dict())
```

### 2. Authentication & Authorization

- Add API key validation to the MCP transport layer
- Map MCP callers to RBAC roles (underwriter, adjuster, broker, auditor)
- Enforce authority limits (e.g., broker can't bind > $1M)

### 3. Additional Tools

| Tool | Priority | Description |
|------|----------|-------------|
| `assess_claim` | High | AI-driven claims assessment via ClaimsAgent |
| `run_claims_workflow` | High | End-to-end claims processing |
| `run_renewal` | Medium | Generate renewal terms |
| `endorse_policy` | Medium | Mid-term endorsement |
| `cancel_policy` | Medium | Policy cancellation |
| `search_knowledge` | Medium | Query knowledge graph |
| `generate_bordereaux` | Low | MGA reporting |
| `run_bias_report` | Low | EU AI Act bias analysis |

### 4. Additional Resources

| URI | Priority | Description |
|-----|----------|-------------|
| `insurance://knowledge/{topic}` | Medium | Underwriting guidelines |
| `insurance://agents/{agent_id}/decisions` | Medium | Per-agent audit trail |
| `insurance://reinsurance/treaties` | Low | Treaty capacity |

### 5. Testing Strategy

- **Unit tests:** Each tool function in isolation with in-memory repos
- **Integration tests:** Full `OpenInsureMCPServer` wrapper (existing tests pass)
- **Protocol tests:** Use `mcp` SDK test client to validate MCP wire protocol
- **E2E tests:** Start MCP server via stdio, call tools via MCP client library

### 6. Observability

- Structured logging via `structlog` (already in place)
- OpenTelemetry spans for each tool invocation
- Decision records for AI-backed tools (EU AI Act Art. 12)

---

## G. Security Considerations

1. **Transport security:** stdio is process-local (safe). SSE should be behind TLS in production.
2. **No secrets in tool responses:** Tool handlers must never return credentials, connection strings, or internal infrastructure details.
3. **Input validation:** All tool parameters are typed via FastMCP decorators. UUID inputs are parsed with `UUID()` constructor (rejects invalid formats).
4. **Rate limiting:** Not implemented at MCP level — should be enforced at transport/gateway layer.
5. **Audit trail:** All tool calls are logged via `structlog` with tool name and arguments.
