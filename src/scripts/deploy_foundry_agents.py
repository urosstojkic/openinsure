"""Deploy OpenInsure agents to Microsoft Foundry Agent Service.

Uses the new create_version() API with PromptAgentDefinition so agents are
visible in both the classic and new Microsoft Foundry portal experiences.

Each agent is deployed with the appropriate tool set:
  - Azure AI Search  → all agents (if a search connection exists)
  - Web Search       → enrichment agent
  - Memory           → underwriting + claims agents
  - Function Calling → underwriting agent (rating factors, comparable accounts)

Requires: azure-ai-projects>=2.0.0, azure-identity

Usage:
    python src/scripts/deploy_foundry_agents.py

Environment variables (optional overrides):
    PROJECT_ENDPOINT        – Foundry project endpoint URL
    MODEL_DEPLOYMENT_NAME   – Model deployment name (default: gpt-5.1)
"""

from __future__ import annotations

import os

from azure.ai.agents.models import (
    AISearchIndexResource,
    AzureAISearchToolDefinition,
    AzureAISearchToolResource,
    FunctionDefinition,
    FunctionToolDefinition,
)
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition
from azure.identity import DefaultAzureCredential

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_ENDPOINT = os.environ.get(
    "PROJECT_ENDPOINT",
    "https://uros-ai-foundry-demo-resource.services.ai.azure.com/api/projects/uros-ai-foundry-demo",
)

MODEL_DEPLOYMENT_NAME = os.environ.get("MODEL_DEPLOYMENT_NAME", "gpt-4.1")

# ---------------------------------------------------------------------------
# Agent definitions  (name, instructions)
# ---------------------------------------------------------------------------

AGENTS = [
    (
        "openinsure-submission",
        "Cyber insurance submission intake and triage. Classifies documents, extracts structured data, "
        "validates completeness, checks appetite, scores risk (1-10), assigns priority. "
        "Responds with structured JSON: appetite_match, risk_score, priority, confidence, reasoning.",
    ),
    (
        "openinsure-underwriting",
        "Cyber insurance underwriting and pricing. Multi-factor risk assessment, comparable analysis, "
        "terms generation, authority check (<$100K auto-bind). Rating factors: revenue, employees, SIC code, "
        "security maturity, controls, incidents. Provides: risk_score, recommended_premium, confidence, key_factors.",
    ),
    (
        "openinsure-policy",
        "Policy lifecycle management: bind, endorse, renew, cancel. Validates requirements, recalculates "
        "premiums, generates documents. Produces EU AI Act compliant DecisionRecords with full reasoning chains.",
    ),
    (
        "openinsure-claims",
        "Cyber claims lifecycle: FNOL intake, coverage verification, initial reserving, triage "
        "(simple/moderate/complex/catastrophe), fraud scoring. Provides: severity_tier, reserve_estimate, "
        "fraud_score, escalation_recommendation.",
    ),
    (
        "openinsure-compliance",
        "EU AI Act compliance agent. Decision audit, bias monitoring (4/5ths rule), regulatory checks, "
        "Art. 9-15 documentation generation. Flags low confidence decisions, missing reasoning, potential bias.",
    ),
    (
        "openinsure-orchestrator",
        "Multi-agent workflow orchestrator. New Business: Submission->Underwriting->Policy->Billing->Compliance. "
        "Claims: FNOL->Reserve/Triage->Compliance. Collects DecisionRecords, checks escalations (confidence<0.7).",
    ),
    (
        "openinsure-billing",
        "AI-native billing agent for commercial insurance. Auto-generates invoices on policy bind, "
        "predicts payment defaults based on customer profile (industry, size, payment history, claims frequency), "
        "assigns payment risk scores, recommends collection actions (reminder→demand→cancellation notice→cancel), "
        "and suggests optimal installment schedules (full_pay/quarterly/monthly). "
        "Responds with: default_probability, risk_tier, recommended_billing_plan, collection_priority, "
        "recommended_action, grace_period_days, reasoning, confidence.",
    ),
    (
        "openinsure-document",
        "AI-native document generation agent for insurance policies. Generates declarations pages, "
        "certificates of insurance, and coverage schedules from structured policy and submission data. "
        "Produces professional insurance language for executive summaries, coverage descriptions, "
        "conditions, and exclusions. Handles conditional sections (e.g., ransomware sublimit rider). "
        "Responds with: title, document_type, sections (heading, content, data), effective_date, "
        "summary, confidence.",
    ),
    (
        "openinsure-analytics",
        "Insurance portfolio analytics agent. Generates executive summaries, identifies trends, "
        "anomalies, and concentration risks across the book of business. Analyzes submission pipelines, "
        "claims patterns, loss ratios, and underwriting profitability. Produces actionable insights "
        "with severity ratings and strategic recommendations for portfolio management. "
        "Responds with: executive_summary, insights (category, title, summary, severity), "
        "recommendations, confidence.",
    ),
    (
        "openinsure-enrichment",
        "External data enrichment agent for cyber insurance submissions. Synthesizes risk signals "
        "from third-party data sources including OSINT, vulnerability databases, breach history, "
        "financial stability indicators, and industry benchmarks. Assesses data quality and "
        "produces composite risk scores with sourced evidence for underwriting decisions. "
        "Responds with: risk_signals (signal, severity, source), composite_risk_score, "
        "data_quality, recommendations, confidence, summary.",
    ),
]

# ---------------------------------------------------------------------------
# Function definitions (underwriting agent)
# ---------------------------------------------------------------------------

get_rating_factors = FunctionDefinition(
    name="get_rating_factors",
    description=(
        "Get cyber insurance rating factors for a line of business. "
        "Returns base rates, industry multipliers, and security control requirements."
    ),
    parameters={
        "type": "object",
        "properties": {
            "lob": {
                "type": "string",
                "description": "Line of business (e.g., 'cyber', 'property')",
            },
        },
        "required": ["lob"],
    },
)

get_comparable_accounts = FunctionDefinition(
    name="get_comparable_accounts",
    description=(
        "Find similar historical accounts for pricing comparison. "
        "Matches by industry, revenue, employee count, and security maturity."
    ),
    parameters={
        "type": "object",
        "properties": {
            "industry_sic": {
                "type": "string",
                "description": "SIC code prefix (e.g., '7371')",
            },
            "annual_revenue": {
                "type": "number",
                "description": "Annual revenue in USD",
            },
            "employee_count": {
                "type": "integer",
                "description": "Number of employees",
            },
        },
        "required": ["industry_sic"],
    },
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _discover_search_connection(client: AIProjectClient) -> str | None:
    """Try to find an Azure AI Search connection in the project."""
    try:
        connections = client.connections.list()
        for conn in connections:
            if hasattr(conn, "connection_type") and "search" in str(getattr(conn, "connection_type", "")).lower():
                return conn.id
            # Also check by name pattern
            if hasattr(conn, "name") and "search" in str(getattr(conn, "name", "")).lower():
                return conn.id
    except Exception as e:
        print(f"  ⚠ Could not list connections: {e}")
    return None


def _build_tools(agent_name: str, search_connection_id: str | None) -> list:
    """Build tool list for a specific agent."""
    tools: list = []

    # Azure AI Search for all agents (if connection available)
    if search_connection_id:
        tools.append(
            AzureAISearchToolDefinition(
                azure_ai_search=AzureAISearchToolResource(
                    index_list=[
                        AISearchIndexResource(
                            index_connection_id=search_connection_id,
                            index_name="openinsure-knowledge",
                        )
                    ]
                )
            )
        )

    # Agent-specific tools
    if agent_name == "openinsure-enrichment":
        pass  # tools.append(WebSearchPreviewToolDefinition()) — not available in current SDK

    if agent_name in ("openinsure-underwriting", "openinsure-claims"):
        pass  # tools.append(MemoryToolDefinition()) — not available in current SDK

    if agent_name == "openinsure-underwriting":
        tools.append(FunctionToolDefinition(function=get_rating_factors))
        tools.append(FunctionToolDefinition(function=get_comparable_accounts))

    return tools


def _describe_tools(tools: list) -> str:
    """Return a human-readable summary of the tools attached to an agent."""
    if not tools:
        return "none"
    labels: list[str] = []
    func_names: list[str] = []
    for t in tools:
        if isinstance(t, AzureAISearchToolDefinition):
            labels.append("ai_search")
        elif isinstance(t, FunctionToolDefinition):
            func_names.append(t.function.name)
        else:
            labels.append(type(t).__name__)
    if func_names:
        labels.append(f"function({', '.join(func_names)})")
    return ", ".join(labels)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    credential = DefaultAzureCredential()
    client = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=credential)

    # Discover search connection
    search_connection_id = _discover_search_connection(client)

    print("Deploying OpenInsure agents to Microsoft Foundry...")
    print(f"  Endpoint: {PROJECT_ENDPOINT}")
    print(f"  Model: {MODEL_DEPLOYMENT_NAME}")
    if search_connection_id:
        print(f"  Search connection: {search_connection_id}")
    else:
        print("  Search connection: not found — deploying without AI Search")
    print()

    for name, instructions in AGENTS:
        tools = _build_tools(name, search_connection_id)
        try:
            agent = client.agents.create_version(
                agent_name=name,
                definition=PromptAgentDefinition(
                    model=MODEL_DEPLOYMENT_NAME,
                    instructions=instructions,
                    tools=tools if tools else None,
                ),
            )
            tool_desc = _describe_tools(tools)
            print(f"  ✓ {name} v{agent.version} [tools: {tool_desc}]")
        except Exception as e:
            print(f"  ✗ {name}: {e}")

    print("\nVerifying agents:")
    for a in client.agents.list():
        if a.name and a.name.startswith("openinsure"):
            print(f"  {a.name}")

    print("\nDone. Agents visible at: https://ai.azure.com")


if __name__ == "__main__":
    main()
