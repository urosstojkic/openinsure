# OpenInsure Developer Guide

> **The single reference for developing, extending, and deploying OpenInsure.**
> For architecture deep-dives see `docs/architecture/`. For capabilities overview see `docs/CAPABILITIES.md`.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Architecture Overview](#architecture-overview)
3. [Adding a New Line of Business](#adding-a-new-line-of-business)
4. [Product Configuration](#product-configuration)
5. [Rating Engine](#rating-engine)
6. [Agent Development](#agent-development)
7. [Knowledge Graph](#knowledge-graph)
8. [RBAC & Authority](#rbac--authority)
9. [Deployment](#deployment)
10. [API Reference](#api-reference)
11. [Coding Standards](#coding-standards)

---

## Quick Start

### Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.12+ | Backend runtime |
| Node.js | 20+ | Dashboard build |
| Azure CLI | Latest | Deployment & `az login` for DefaultAzureCredential |
| Git | Latest | Version control |
| ODBC Driver 18 | Latest | Azure SQL connectivity (local only) |

### Local Setup

```bash
# 1. Clone & install backend
git clone https://github.com/<org>/openinsure.git
cd openinsure
pip install -e ".[dev]"

# 2. Start the API (in-memory mode — no Azure needed)
uvicorn openinsure.main:app --reload --port 8000
# → http://localhost:8000/docs  (Swagger UI)
# → http://localhost:8000/health

# 3. Start the dashboard
cd dashboard
npm install
npm run dev
# → http://localhost:5173
```

When `OPENINSURE_DEBUG=true` (default for local dev), the API auto-seeds sample data:
5 submissions, 3 policies, 2 claims, 1 product, and 5 AI decision records.

### Environment Variables

Copy `.env.example` or create `.env` in the project root. Key variables:

```bash
# Application
OPENINSURE_DEBUG=true              # Enables sample data seeding
OPENINSURE_LOG_LEVEL=DEBUG
OPENINSURE_STORAGE_MODE=memory     # "memory" (local) or "azure" (real services)

# Azure (only needed when STORAGE_MODE=azure)
OPENINSURE_SQL_CONNECTION_STRING=Driver={ODBC Driver 18 for SQL Server};Server=...
OPENINSURE_COSMOS_ENDPOINT=https://...documents.azure.com:443/
OPENINSURE_SEARCH_ENDPOINT=https://...search.windows.net
OPENINSURE_STORAGE_ACCOUNT_URL=https://...blob.core.windows.net/
OPENINSURE_EVENTGRID_ENDPOINT=https://...eventgrid.azure.net/api/events
OPENINSURE_SERVICEBUS_CONNECTION_STRING=...servicebus.windows.net

# Foundry (for AI agent calls)
OPENINSURE_FOUNDRY_PROJECT_ENDPOINT=https://...services.ai.azure.com/api/projects/...
OPENINSURE_FOUNDRY_MODEL_DEPLOYMENT=gpt-4o
```

All Azure connections use **DefaultAzureCredential** (managed identity / `az login`) — never hardcoded secrets.

### Running Tests

```bash
# Full test suite (in-memory, no Azure needed)
pytest tests/ -v

# With coverage (must meet ≥80%)
pytest tests/ --cov=src/openinsure --cov-report=term --cov-fail-under=80

# Against real Azure resources
pytest tests/ --azure -v

# Skip Azure-dependent tests
pytest tests/ -m "not azure" -v
```

### Quality Gates (all must pass before merge)

```bash
ruff check src/ tests/              # Lint
ruff format --check src/ tests/     # Format check
mypy src/openinsure/                # Type check (strict mode)
bandit -r src/openinsure/ -ll       # Security scan
pytest tests/ -v --cov=src/openinsure --cov-fail-under=80
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  Dashboard (React 19 + Vite + Tailwind)                        │
│  21 views · 11 role-specific workbenches · Broker portal        │
└────────────────────────┬────────────────────────────────────────┘
                         │ REST
┌────────────────────────▼────────────────────────────────────────┐
│  FastAPI Backend (/api/v1/*)                                    │
│  35+ endpoints · RBAC middleware · Pydantic v2 validation       │
├─────────────┬──────────────┬───────────────┬────────────────────┤
│  Agents     │  Services    │  RBAC         │  Compliance        │
│  8 Foundry  │  Rating      │  24 roles     │  EU AI Act         │
│  agents     │  Lifecycle   │  Authority    │  Decision Records  │
│             │  Claims      │  matrix       │  Bias monitoring   │
├─────────────┴──────────────┴───────────────┴────────────────────┤
│  Infrastructure (Repository Pattern + Service Factory)          │
├──────────┬──────────┬──────────┬──────────┬──────────┬──────────┤
│ Azure SQL│ Cosmos DB│ AI Search│ Blob     │ Service  │ Event    │
│ (OLTP)   │ (KG)     │ (Vector) │ Storage  │ Bus      │ Grid     │
└──────────┴──────────┴──────────┴──────────┴──────────┴──────────┘
```

### Key Design Patterns

| Pattern | Where | Purpose |
|---------|-------|---------|
| **Repository** | `infrastructure/repository.py` | Abstract CRUD; swap in-memory ↔ SQL |
| **Service Factory** | `infrastructure/factory.py` | LRU-cached dependency creation; `storage_mode` toggle |
| **Domain Entities** | `domain/*.py` | Pydantic v2 models with `Money`, `Percentage`, `Score` types |
| **Agent Base** | `agents/base.py` | `InsuranceAgent` ABC with `DecisionRecord` logging |
| **Foundry Client** | `agents/foundry_client.py` | Azure AI Projects SDK with graceful fallback |
| **Router Composition** | `api/router.py` | Hierarchical routers with `Depends(get_current_user)` |

### Source Tree

```
src/openinsure/
├── agents/          # 8 AI agents (base, foundry_client, submission, underwriting, ...)
├── api/             # FastAPI routers (submissions, policies, claims, products, ...)
├── compliance/      # EU AI Act compliance layer
├── domain/          # Pydantic domain entities (common, party, submission, policy, ...)
├── infrastructure/  # Azure adapters + repository implementations
│   └── repositories/  # InMemory* and Sql* repository variants
├── knowledge/       # Knowledge graph schemas & query builders
├── mcp/             # MCP Server interface for external agent integration
├── rbac/            # Roles, authority matrix, authentication
├── services/        # Business logic (rating, lifecycle, claims, ...)
├── scripts/         # Deployment & migration utilities
├── config.py        # Pydantic Settings (OPENINSURE_* env vars)
└── main.py          # FastAPI app factory
```

For detailed architecture specs, see `docs/architecture/architecture-spec-v01.md` and `docs/architecture/ADR.md`.

---

## Adding a New Line of Business

This walkthrough uses Cyber Liability as the reference implementation.

### Step 1: Create Product Definition

Create a YAML file in `knowledge/products/`:

```yaml
# knowledge/products/professional_liability.yaml
product:
  code: "PL-001"
  name: "Professional Liability"
  line_of_business: "professional_liability"
  version: 1

  coverages:
    - code: "E-AND-O"
      name: "Errors & Omissions"
      description: "Professional negligence coverage"
      default_limit: 1000000
      min_limit: 250000
      max_limit: 10000000
      default_deductible: 10000
      available_deductibles: [5000, 10000, 25000, 50000]

  rating_factors:
    - name: "annual_revenue"
      type: "numeric"
      weight: 0.30
    - name: "years_in_business"
      type: "numeric"
      weight: 0.20
    - name: "industry_sic_code"
      type: "categorical"
      weight: 0.25
    - name: "prior_claims"
      type: "numeric"
      weight: 0.25

  exclusions:
    - code: "KNOWN-ACTS"
      description: "Known wrongful acts prior to inception"
    - code: "FRAUD"
      description: "Intentional fraud or criminal acts"

  pricing:
    min_premium: 1500
    max_premium: 250000
    base_rate_per_1000_revenue: 2.00

  territories: ["US-ALL"]
```

**Required fields:** `code`, `name`, `line_of_business`, `version`, `coverages` (with limits/deductibles), `rating_factors`, `exclusions`, `pricing`.

### Step 2: Add Rating Factors

Create a new rating engine or extend the existing one in `src/openinsure/services/`:

```python
# src/openinsure/services/pl_rating.py
from decimal import Decimal
from pydantic import BaseModel, Field

class PLRatingInput(BaseModel):
    annual_revenue: Decimal = Field(ge=0)
    years_in_business: int = Field(ge=0)
    industry_sic_code: str
    prior_claims: int = Field(ge=0, default=0)
    requested_limit: Decimal = Field(ge=0, default=Decimal("1000000"))
    requested_deductible: Decimal = Field(ge=0, default=Decimal("10000"))

class PLRatingEngine:
    def __init__(
        self,
        base_rate_per_thousand: Decimal = Decimal("2.00"),
        min_premium: Decimal = Decimal("1500"),
        max_premium: Decimal = Decimal("250000"),
    ):
        self.base_rate = base_rate_per_thousand
        self.min_premium = min_premium
        self.max_premium = max_premium

    def calculate_premium(self, rating_input: PLRatingInput) -> dict:
        base = (rating_input.annual_revenue / Decimal("1000")) * self.base_rate
        # Apply factor tables (see Rating Engine section)
        adjusted = base * self._get_experience_factor(rating_input.years_in_business)
        final = max(self.min_premium, min(self.max_premium, adjusted))
        return {"premium": final, "factors_applied": {...}}
```

See [Rating Engine](#rating-engine) for the full factor table reference.

### Step 3: Create Underwriting Guidelines

Create a YAML file in `knowledge/guidelines/`:

```yaml
# knowledge/guidelines/pl_underwriting.yaml
underwriting_guidelines:
  version: 1
  product_code: "PL-001"

  risk_appetite:
    acceptable_risk_score:
      min: 1
      max: 7
    target_industries:
      preferred:
        - "Legal Services (SIC 8111)"
        - "Accounting (SIC 8721)"
      declined:
        - "Medical malpractice"

  referral_triggers:
    - trigger: "prior_claims_3yr"
      action: "Refer to senior underwriter"
    - trigger: "revenue_above_25m"
      action: "Capacity review required"

  authority_levels:
    auto_bind:
      max_premium: 15000
      conditions: ["Risk score ≤ 5", "No referral triggers"]
    underwriter_1:
      max_premium: 75000
    committee:
      max_premium: 250000

  required_controls:
    - "Professional license verification"
    - "Quality assurance program"
```

### Step 4: Deploy Foundry Agent

Update or create an agent in `src/scripts/deploy_foundry_agents.py`:

```python
AGENTS["openinsure-pl-underwriting"] = {
    "instructions": """You are a Professional Liability underwriting agent.
    Evaluate risk for E&O submissions using these guidelines:
    {knowledge_context}

    Return JSON: {
      "risk_score": 1-10,
      "recommendation": "approve|refer|decline",
      "premium_indication": number,
      "reasoning": "...",
      "referral_triggers": []
    }""",
    "model": "gpt-4o",
}
```

Deploy with:

```bash
python src/scripts/deploy_foundry_agents.py
```

Test in the Foundry playground at `https://ai.azure.com` before wiring into the API.

### Step 5: Add API Endpoints (if needed)

Follow the existing router pattern:

```python
# src/openinsure/api/pl_submissions.py
from fastapi import APIRouter, Depends
from openinsure.rbac.auth import get_current_user, require_roles
from openinsure.rbac.roles import Role

router = APIRouter()

@router.post("/", dependencies=[Depends(require_roles(
    Role.CUO, Role.SENIOR_UNDERWRITER, Role.UW_ANALYST
))])
async def create_pl_submission(
    submission: PLSubmissionCreate,
    user: CurrentUser = Depends(get_current_user),
):
    repo = get_submission_repository()
    result = await repo.create(submission.model_dump())
    return result
```

Register in `src/openinsure/api/router.py`:

```python
api_v1_router.include_router(pl_router, prefix="/pl-submissions", tags=["professional-liability"])
```

### Step 6: Add Dashboard View (if needed)

```tsx
// dashboard/src/pages/PLSubmissions.tsx
import { DataTable } from '../components/DataTable';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../api/client';

export function PLSubmissions() {
  const { data } = useQuery({
    queryKey: ['pl-submissions'],
    queryFn: () => apiClient.get('/api/v1/pl-submissions').then(r => r.data),
  });

  return <DataTable data={data?.items ?? []} columns={columns} />;
}
```

Add routing in `dashboard/src/App.tsx`:

```tsx
<Route path="pl-submissions" element={
  <RouteGuard path="pl-submissions"><PLSubmissions /></RouteGuard>
} />
```

Update `NAV_ACCESS` to control role visibility:

```tsx
'/pl-submissions': ['cuo', 'senior_uw', 'uw_analyst'],
```

---

## Product Configuration

### YAML Schema

Product definitions live in `knowledge/products/` and follow this schema:

```yaml
product:
  code: string          # Unique product code (e.g., "CYBER-SMB-001")
  name: string          # Display name
  line_of_business: string  # LOB key (e.g., "cyber", "professional_liability")
  version: int          # Schema version

  coverages:            # List of coverage parts
    - code: string      # Coverage code (e.g., "BREACH-RESP")
      name: string
      description: string
      default_limit: int
      min_limit: int
      max_limit: int
      default_deductible: int
      available_deductibles: [int]

  rating_factors:       # Factors that influence premium
    - name: string
      type: "numeric" | "categorical"
      weight: float     # 0.0–1.0, all weights should sum to ~1.0

  exclusions:           # What's not covered
    - code: string
      description: string

  pricing:
    min_premium: int
    max_premium: int
    base_rate_per_1000_revenue: float

  territories: [string]  # Where the product is filed
```

### Current Product: Cyber Liability SMB (`CYBER-SMB-001`)

| Coverage | Default Limit | Range | Default Deductible |
|----------|---------------|-------|--------------------|
| First-Party Breach Response | $1M | $100K–$5M | $10K |
| Third-Party Liability | $1M | $250K–$10M | $25K |
| Regulatory Defense & Penalties | $500K | $100K–$2M | $10K |
| Business Interruption | $500K | $50K–$2M | $25K |
| Ransomware & Extortion | $500K | $100K–$2M | $10K |

---

## Rating Engine

The `CyberRatingEngine` in `src/openinsure/services/rating.py` uses multi-factor multiplicative pricing.

### Premium Formula

```
base_premium = (annual_revenue / 1000) × base_rate_per_thousand

adjusted = base_premium
         × revenue_factor
         × industry_factor
         × security_factor
         × controls_factor
         × incident_factor
         × limit_factor
         × deductible_factor

final_premium = clamp(min_premium, adjusted, max_premium)
```

### Factor Tables

#### Industry Risk (by SIC code prefix)

| SIC Prefix | Industry | Factor |
|------------|----------|--------|
| 73 | Computer services | 1.00 (baseline) |
| 72 | Computer maintenance | 0.90 |
| 53 | General merchandise | 0.70 |
| 58 | Eating/drinking | 0.80 |
| 82 | Education | 0.80 |
| 91 | Government | 1.10 |
| 63 | Insurance | 1.20 |
| 62 | Security brokers | 1.30 |
| 61 | Credit institutions | 1.40 |
| 60 | Banking | 1.50 |
| 80 | Healthcare | 1.60 |
| *other* | Default | 1.00 |

#### Revenue Bands

| Revenue Range | Factor |
|---------------|--------|
| < $1M | 0.80 |
| $1M–$5M | 1.00 |
| $5M–$10M | 1.15 |
| $10M–$25M | 1.30 |
| $25M–$50M | 1.50 |
| > $50M | 1.50 |

#### Security Maturity (0–10 score)

| Score | Rating | Factor |
|-------|--------|--------|
| ≥ 8.0 | Excellent | 0.70 (30% discount) |
| ≥ 6.0 | Good | 0.85 (15% discount) |
| ≥ 4.0 | Fair | 1.00 |
| ≥ 2.0 | Poor | 1.30 (30% loading) |
| < 2.0 | Very Poor | 1.60 (60% loading) |

#### Security Controls Credits

Each deployed control = **−5%** credit (max 20% = 4 controls):

- `has_mfa` — Multi-factor authentication
- `has_endpoint_protection` — EDR/EPP deployed
- `has_backup_strategy` — Offline/immutable backups
- `has_incident_response_plan` — Documented & tested plan

#### Prior Incidents

| Count | Factor |
|-------|--------|
| 0 | 1.00 |
| 1 | 1.25 |
| 2 | 1.50 |
| 3+ | 2.00 (auto-referral) |

#### Limit Factor

| Requested Limit | Factor |
|-----------------|--------|
| ≤ $500K | 0.70 |
| ≤ $1M | 1.00 |
| ≤ $2M | 1.30 |
| ≤ $5M | 1.60 |
| > $5M | 2.00 |

#### Deductible Credit

| Deductible | Factor |
|------------|--------|
| ≥ $100K | 0.70 |
| ≥ $50K | 0.80 |
| ≥ $25K | 0.90 |
| ≥ $10K | 0.95 |
| < $10K | 1.00 |

### Adding a New Factor

1. Add field to `RatingInput` model in `services/rating.py`
2. Create `_get_<factor>_factor()` method on `CyberRatingEngine`
3. Multiply into the `calculate_premium()` chain
4. Add the factor to `RatingResult.factors_applied` dict
5. Add tests in `tests/unit/test_services/`
6. Update the product YAML `rating_factors` list

### Calibrating Existing Factors

Factor values are constants in `services/rating.py`. To recalibrate:

1. Update the constants (e.g., `INDUSTRY_RISK_FACTORS["80"] = Decimal("1.7")`)
2. Run rating tests to verify premium ranges stay within `min_premium`/`max_premium`
3. Document changes in `CHANGELOG.md` — premium changes are material

---

## Agent Development

### Agent Architecture

```
InsuranceAgent (ABC)           ← agents/base.py
├── SubmissionAgent            ← Intake, triage, risk scoring
├── UnderwritingAgent          ← Risk assessment, pricing, authority
├── PolicyAgent                ← Bind, endorse, renew, cancel
├── ClaimsAgent                ← FNOL, coverage check, reserve, triage
├── ComplianceAgent            ← EU AI Act audit, bias monitoring
├── DocumentAgent              ← Classify, extract document data
├── KnowledgeAgent             ← Retrieve guidelines & rules
└── Orchestrator               ← Multi-agent workflow coordination
```

Every agent produces **`DecisionRecord`** objects (EU AI Act Art. 12–14):

```python
class DecisionRecord(BaseModel):
    decision_id: UUID
    timestamp: datetime          # UTC
    agent_id: str
    agent_version: str
    model_used: str
    decision_type: str
    input_summary: dict          # What the agent received
    output: dict                 # What the agent decided
    reasoning: dict              # Why (chain-of-thought)
    confidence: float            # 0.0–1.0
    fairness_metrics: dict       # Bias monitoring (4/5ths rule)
    human_oversight: dict        # Override flags
    execution_time_ms: int
```

### Foundry Integration

Agents call Azure AI Foundry via `FoundryAgentClient` (`agents/foundry_client.py`):

```python
client = FoundryAgentClient()

# Invoke a deployed agent
result = await client.invoke(
    agent_name="openinsure-underwriting",
    message="Evaluate this submission: {...}"
)
# result = {"response": {...}, "source": "foundry"} or fallback
```

The client uses `DefaultAzureCredential` and gracefully falls back when Foundry is unavailable.

### Creating a New Agent

**1. Define the agent class:**

```python
# src/openinsure/agents/my_agent.py
from openinsure.agents.base import InsuranceAgent, AgentConfig, AgentCapability

class MyAgent(InsuranceAgent):
    @property
    def capabilities(self) -> list[AgentCapability]:
        return [AgentCapability(
            name="my_capability",
            description="What this agent does",
            input_schema={...},
            output_schema={...},
        )]

    async def process(self, task: dict[str, Any]) -> dict[str, Any]:
        # 1. Call Foundry
        result = await self.execute_with_foundry(
            agent_name="openinsure-my-agent",
            prompt=f"Process: {task}",
            decision_type="my_decision",
            input_summary=task,
        )
        return result
```

**2. Deploy to Foundry:**

Add agent definition to `src/scripts/deploy_foundry_agents.py` and run:

```bash
python src/scripts/deploy_foundry_agents.py
```

**3. Wire into API endpoint:**

```python
@router.post("/my-action")
async def my_action(request: MyRequest, user = Depends(get_current_user)):
    agent = MyAgent(config=AgentConfig(agent_id="my-agent", ...))
    result = await agent.process(request.model_dump())
    return result
```

**4. Add tests:**

```python
# tests/unit/test_agents/test_my_agent.py
async def test_my_agent_process():
    agent = MyAgent(config=mock_config)
    result = await agent.process({"key": "value"})
    assert result["decision_type"] == "my_decision"
```

### Agent Prompt Engineering

Prompts follow this structure (see `deploy_foundry_agents.py`):

```
You are a [role] agent for OpenInsure.

Context:
{knowledge_context}        ← Product definitions, guidelines, regulatory

Task:
{specific_instructions}

Return JSON:
{
  "field1": "...",
  "reasoning": "...",
  "confidence": 0.0-1.0
}
```

**Tips:**
- Always request structured JSON output
- Include the knowledge context (product rules, guidelines) in the prompt
- Set confidence thresholds — escalate if < 0.7
- Test with the Foundry playground at `https://ai.azure.com` before deploying

### Multi-Agent Orchestration

The `Orchestrator` (`agents/orchestrator.py`) coordinates workflows:

**New Business Workflow:**
1. Submission Intake & Triage → `SubmissionAgent`
2. Document Processing → `DocumentAgent`
3. Knowledge Retrieval → `KnowledgeAgent`
4. Underwriting & Pricing → `UnderwritingAgent`
5. Policy Binding → `PolicyAgent`
6. Compliance Check → `ComplianceAgent`

**Claims Workflow:**
1. FNOL Pipeline (intake → coverage → reserve → triage) → `ClaimsAgent`
2. Investigation Support → `ClaimsAgent`
3. Compliance Check → `ComplianceAgent`

Each step emits domain events (e.g., `workflow.underwriting_complete`) and produces `DecisionRecord` objects.

---

## Knowledge Graph

### Structure

```
knowledge/
├── products/
│   └── cyber_liability_smb.yaml     # Product definitions
├── guidelines/
│   └── cyber_underwriting.yaml      # Underwriting rules & referral triggers
└── regulatory/
    └── us_cyber_requirements.yaml   # State filings, data privacy, EU AI Act
```

Knowledge YAML feeds into agent prompts as context and is indexed in Cosmos DB + AI Search for retrieval.

### Adding Knowledge

1. Create a YAML file in the appropriate subdirectory
2. Follow the existing schema (see `cyber_liability_smb.yaml` for products, `cyber_underwriting.yaml` for guidelines)
3. Seed to Cosmos DB:

```bash
python src/scripts/seed_knowledge_graph.py
```

This upserts each YAML file into Cosmos DB as a document with `entityType` (product/guideline/regulatory) and indexes the content for AI Search retrieval.

### Knowledge in Agent Prompts

When an agent processes a task, the `KnowledgeAgent` retrieves relevant YAML content and injects it into the prompt context. This ensures agents always operate with current product rules and guidelines.

---

## RBAC & Authority

### Roles (24 total)

| Category | Role | Enum | Carrier | MGA |
|----------|------|------|---------|-----|
| **Leadership** | CEO | `openinsure-ceo` | ✓ | ✓ |
| | CUO | `openinsure-cuo` | ✓ | ✓ |
| **Underwriting** | LOB Head | `openinsure-lob-head` | ✓ | — |
| | Senior Underwriter | `openinsure-senior-underwriter` | ✓ | ✓ |
| | UW Analyst | `openinsure-uw-analyst` | ✓ | ✓ |
| **Actuarial** | Chief Actuary | `openinsure-chief-actuary` | ✓ | — |
| | Actuary | `openinsure-actuary` | ✓ | — |
| **Claims** | Claims Manager | `openinsure-claims-manager` | ✓ | ✓ |
| | Claims Adjuster | `openinsure-claims-adjuster` | ✓ | ✓ |
| **Finance** | CFO | `openinsure-cfo` | ✓ | ✓ |
| | Finance | `openinsure-finance` | ✓ | ✓ |
| | Reinsurance Manager | `openinsure-reinsurance-manager` | ✓ | — |
| **Compliance** | Compliance Officer | `openinsure-compliance` | ✓ | ✓ |
| **Delegated Authority** | DA Manager | `openinsure-da-manager` | ✓ | — |
| **Product & Tech** | Product Manager | `openinsure-product-manager` | ✓ | ✓ |
| | Platform Admin | `openinsure-platform-admin` | ✓ | ✓ |
| | Operations | `openinsure-operations` | ✓ | ✓ |
| **External** | Broker | `openinsure-broker` | ✓ | ✓ |
| | MGA External | `openinsure-mga-external` | ✓ | — |
| | Policyholder | `openinsure-policyholder` | ✓ | ✓ |
| | Reinsurer | `openinsure-reinsurer` | ✓ | — |
| | Auditor | `openinsure-auditor` | ✓ | ✓ |
| | Vendor | `openinsure-vendor` | ✓ | ✓ |

**Deployment type** (`OPENINSURE_DEPLOYMENT_TYPE`): `"carrier"` enables all 24 roles; `"mga"` enables 17 roles (excludes carrier-only roles like LOB Head, Chief Actuary, Reinsurance Manager).

### Authentication

`get_current_user()` in `src/openinsure/rbac/auth.py` resolves identity via:

1. **Dev mode** (`require_auth=False`): Returns default CUO user — no auth needed
2. **API Key** (`X-API-Key` header): Validates against `settings.api_key`
3. **JWT Bearer** (`Authorization: Bearer <token>`): Decodes JWT claims (`sub`, `email`, `roles`)

Protect endpoints with role checks:

```python
from openinsure.rbac.auth import require_roles
from openinsure.rbac.roles import Role

@router.post("/", dependencies=[Depends(require_roles(Role.CUO, Role.SENIOR_UNDERWRITER))])
async def my_endpoint(...):
    ...
```

### Authority Engine

The authority engine (`src/openinsure/rbac/authority.py`) determines action authorization:

| Decision | Meaning |
|----------|---------|
| `AUTO_EXECUTE` | Agent executes autonomously |
| `RECOMMEND` | Agent recommends, human confirms |
| `REQUIRE_APPROVAL` | Human must approve |
| `ESCALATE` | Route to higher authority |

**Underwriting escalation chain:** UW Analyst → Senior Underwriter → LOB Head → CUO → CEO

**Default authority thresholds (quoting):**

| Level | Max Premium |
|-------|-------------|
| Auto-bind | $50K |
| Senior UW | $250K |
| LOB Head | $1M |
| CUO/Committee | Unlimited |

---

## Deployment

### Local Development

```bash
# Backend (hot-reload)
uvicorn openinsure.main:app --reload --port 8000

# Dashboard (HMR)
cd dashboard && npm run dev
```

### Azure Infrastructure (Bicep)

Deploy all Azure resources via Bicep IaC in `infra/`:

```bash
# Deploy to dev
az deployment group create \
  --resource-group openinsure-dev-sc \
  --template-file infra/main.bicep \
  --parameters infra/parameters/dev.bicepparam

# Deploy to prod
az deployment group create \
  --resource-group openinsure-prod \
  --template-file infra/main.bicep \
  --parameters infra/parameters/prod.bicepparam
```

**Deployed resources (9 Bicep modules):**

| Module | Resource | Purpose |
|--------|----------|---------|
| `sql.bicep` | Azure SQL Database | Transactional data (Entra-only auth, TDE) |
| `cosmos.bicep` | Cosmos DB (NoSQL) | Knowledge graph, decision records |
| `search.bicep` | Azure AI Search | Hybrid vector + keyword search |
| `storage.bicep` | Blob Storage | Document repository |
| `servicebus.bicep` | Service Bus | Event messaging queues |
| `eventgrid.bicep` | Event Grid | Domain event publishing |
| `identity.bicep` | Managed Identity | Passwordless auth + RBAC assignments |
| `monitoring.bicep` | App Insights + Log Analytics | Telemetry |

### Container Deployment

```bash
# Build & push backend image
az acr build --registry <registry> --image openinsure-backend:latest --file Dockerfile .

# Build & push dashboard image
az acr build --registry <registry> --image openinsure-dashboard:latest --file dashboard/Dockerfile dashboard/

# Update Container Apps
az containerapp update --name openinsure-backend \
  --resource-group openinsure-dev-sc \
  --image <registry>.azurecr.io/openinsure-backend:latest

az containerapp update --name openinsure-dashboard \
  --resource-group openinsure-dev-sc \
  --image <registry>.azurecr.io/openinsure-dashboard:latest
```

### Foundry Agent Deployment

```bash
# Deploy/update all agents
python src/scripts/deploy_foundry_agents.py

# Seed knowledge to Cosmos DB
python src/scripts/seed_knowledge_graph.py

# Test agent workflow
python src/scripts/test_foundry_workflow.py
```

### CI/CD Pipeline

GitHub Actions (`.github/workflows/ci.yml`) runs on every push to `main` and every PR:

1. **Lint** — `ruff check src/ tests/`
2. **Format** — `ruff format --check src/ tests/`
3. **Type check** — `mypy src/openinsure/`
4. **Security** — `bandit -r src/openinsure/ -ll`
5. **Tests** — `pytest tests/ -v --cov=src/openinsure --cov-report=xml`
6. **Coverage upload** — Artifact for tracking

**Branch strategy:** `feat/<issue>-<name>`, `fix/...`, `docs/...` branching from `main`.

---

## API Reference

Swagger UI is available at `http://localhost:8000/docs` (local) or your deployed URL `/docs`.

### Key Endpoint Groups

| Group | Prefix | Methods | Description |
|-------|--------|---------|-------------|
| Health | `/health` | GET | Liveness/readiness checks |
| Submissions | `/api/v1/submissions` | GET, POST | Submission intake & listing |
| Policies | `/api/v1/policies` | GET, POST | Policy lifecycle |
| Claims | `/api/v1/claims` | GET, POST | FNOL & claims management |
| Products | `/api/v1/products` | GET, POST | Product catalog |
| Billing | `/api/v1/billing` | GET, POST | Invoices & payments |
| Compliance | `/api/v1/compliance` | GET, POST | Decision records & audit |
| Documents | `/api/v1/documents` | GET, POST | Document upload & retrieval |
| Knowledge | `/api/v1/knowledge` | GET, POST | Knowledge graph queries |
| Reinsurance | `/api/v1/reinsurance` | GET, POST | Treaty management |
| Actuarial | `/api/v1/actuarial` | GET | Loss triangles & analytics |
| MGA Oversight | `/api/v1/mga` | GET | Delegated authority monitoring |
| Renewals | `/api/v1/renewals` | GET, POST | Renewal workflow |
| Finance | `/api/v1/finance` | GET | Premium & claims analytics |

### Example: Create Submission

```bash
curl -X POST http://localhost:8000/api/v1/submissions \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "channel": "email",
    "line_of_business": "cyber",
    "applicant": {
      "name": "Acme Corp",
      "party_type": "organization",
      "tax_id": "12-3456789",
      "addresses": [{
        "address_type": "primary",
        "street": "123 Main St",
        "city": "Hartford",
        "state": "CT",
        "zip_code": "06103",
        "country": "US"
      }],
      "contacts": [{
        "contact_type": "primary",
        "name": "Jane Smith",
        "email": "jane@acme.com",
        "phone": "+1-555-0100"
      }]
    },
    "requested_effective_date": "2026-07-01",
    "requested_expiration_date": "2027-07-01",
    "cyber_risk_data": {
      "annual_revenue": 5000000,
      "employee_count": 50,
      "industry_sic_code": "7372",
      "security_maturity_score": 7.0,
      "has_mfa": true,
      "has_endpoint_protection": true,
      "has_backup_strategy": true,
      "prior_incidents": 0
    }
  }'
```

---

## Coding Standards

### Python

| Convention | Standard |
|-----------|----------|
| Framework | FastAPI with async/await |
| Validation | Pydantic v2 (`BaseModel`, `Field`) |
| Logging | `structlog` (structured JSON) |
| Retries | `tenacity` with exponential backoff |
| HTTP client | `httpx` (async) |
| Monetary values | `Decimal` (never `float`) |
| Entity IDs | `UUID` |
| Timestamps | `datetime` in UTC (ISO 8601) |
| Linter | `ruff` (120-char lines, Python 3.12 target) |
| Type checker | `mypy` (strict mode) |
| Security | `bandit`; no hardcoded creds; `# nosec` only on verified false positives |

### TypeScript / Dashboard

| Convention | Standard |
|-----------|----------|
| Framework | React 19 + TypeScript |
| Build tool | Vite 7 |
| Styling | Tailwind CSS v4 |
| State | React Context + `@tanstack/react-query` |
| HTTP | Axios with interceptors |
| Routing | React Router DOM v6 |
| Charts | Recharts |
| Linter | ESLint |

### Testing

| Convention | Standard |
|-----------|----------|
| Framework | pytest + pytest-asyncio |
| Coverage | ≥ 80% (`--cov-fail-under=80`) |
| Fixtures | Shared in `tests/conftest.py` |
| API tests | `TestClient` from FastAPI |
| Azure tests | `--azure` flag; mark with `@pytest.mark.azure` |
| Test structure | `tests/unit/`, `tests/integration/`, `tests/e2e/` |

### Insurance Domain Conventions

| Convention | Standard |
|-----------|----------|
| Monetary values | `Decimal` with 2 decimal places |
| Percentages | `Decimal` with 4 decimal places |
| Risk scores | `float` 0.0–10.0 |
| Confidence | `float` 0.0–1.0 |
| Every AI decision | Must produce `DecisionRecord` |
| SIC codes | Standard Industry Classification |
| Territories | US state codes |

### Security

- **No hardcoded credentials** — use `DefaultAzureCredential` everywhere
- **Managed Identity** for all Azure service connections
- **Entra-only auth** on Azure SQL (no SQL login/password)
- **`bandit`** scans on every PR; `# nosec` requires justification comment
- **CORS** — environment-aware origins, no wildcards in production
- **API authentication** — API key or JWT Bearer on all `/api/v1/*` endpoints

---

## Further Reading

- `docs/architecture/architecture-spec-v01.md` — Detailed system architecture
- `docs/architecture/ADR.md` — Architectural Decision Records
- `docs/architecture/operating-model-v02.md` — Operating model & authority matrix
- `docs/architecture/overview.md` — High-level architecture diagrams
- `docs/CAPABILITIES.md` — Full capabilities list for stakeholders
- `CONTRIBUTING.md` — Contribution process & branch strategy
- `SECURITY.md` — Security policy & vulnerability reporting
- `CHANGELOG.md` — Version history
