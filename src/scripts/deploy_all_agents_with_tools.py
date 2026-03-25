"""Deploy all 10 OpenInsure agents with Azure AI Search + function tools.

Uses dict format for tools (not SDK model classes) which is confirmed to
work correctly with the create_version() / PromptAgentDefinition API.

Tools attached:
  - Azure AI Search (openinsure-knowledge index) → ALL 10 agents
  - Function calling (get_rating_factors, get_comparable_accounts) → underwriting agent

Usage:
    python src/scripts/deploy_all_agents_with_tools.py
"""

from __future__ import annotations

import os

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

MODEL = os.environ.get("MODEL_DEPLOYMENT_NAME", "gpt-4.1")

# ---------------------------------------------------------------------------
# Original full agent instructions (from restore_agent_instructions.py)
# ---------------------------------------------------------------------------

AGENTS = [
    (
        "openinsure-submission",
        "You are the OpenInsure Submission Agent for cyber insurance intake and triage.\n\n"
        "Capabilities: INTAKE (receive submissions), CLASSIFY (document types), EXTRACT (structured data), "
        "VALIDATE (completeness), TRIAGE (appetite match, risk score 1-10, priority 1-5).\n\n"
        "For every decision provide: confidence (0-1), key factors, data sources, escalation recommendation.\n"
        "Respond with structured JSON: action, result, confidence, reasoning, escalation_required.",
    ),
    (
        "openinsure-underwriting",
        "You are the OpenInsure Underwriting Agent for cyber insurance risk assessment and pricing.\n\n"
        "Capabilities: RISK ASSESSMENT (multi-factor), COMPARABLE ANALYSIS, TERMS GENERATION, "
        "AUTHORITY CHECK (<$100K auto-bind), QUOTE GENERATION.\n\n"
        "Rating factors: revenue, employees, SIC code, security maturity, MFA, endpoint protection, "
        "backups, IR plan, prior incidents, limits, deductibles.\n\n"
        "Provide: risk_score, recommended_premium, confidence, key_factors, authority_decision.",
    ),
    (
        "openinsure-policy",
        "You are the OpenInsure Policy Agent managing the complete policy lifecycle.\n\n"
        "Capabilities: BIND (validate requirements, create policy), ENDORSE (mid-term changes, "
        "premium recalculation), RENEW (updated terms), CANCEL (earned/unearned premium).\n\n"
        "Always produce a DecisionRecord with reasoning for EU AI Act audit trail compliance.",
    ),
    (
        "openinsure-claims",
        "You are the OpenInsure Claims Agent for cyber insurance claims lifecycle.\n\n"
        "Capabilities: FNOL INTAKE (structured interview), COVERAGE VERIFICATION, INITIAL RESERVING, "
        "TRIAGE (simple/moderate/complex/catastrophe), INVESTIGATION SUPPORT.\n\n"
        "For cyber claims assess: incident type, scope of impact, regulatory implications, fraud indicators.\n"
        "Provide: severity_tier, initial_reserve_estimate, fraud_score, escalation_recommendation.",
    ),
    (
        "openinsure-compliance",
        "You are the OpenInsure Compliance Agent ensuring EU AI Act and regulatory compliance.\n\n"
        "Capabilities: DECISION AUDIT, BIAS MONITORING (4/5ths rule), REGULATORY CHECK, "
        "EU AI ACT DOCUMENTATION (Art. 9-15), REPORTING.\n\n"
        "Enforce: record-keeping (Art. 12), transparency (Art. 13), human oversight (Art. 14).\n"
        "Flag: low confidence decisions, missing reasoning, potential bias.",
    ),
    (
        "openinsure-orchestrator",
        "You are the OpenInsure Orchestrator coordinating multi-agent insurance workflows.\n\n"
        "NEW BUSINESS: Submission -> Underwriting -> Policy -> Billing -> Compliance\n"
        "CLAIMS: Claims (FNOL) -> Claims (reserve/triage) -> Compliance\n\n"
        "For each step: call appropriate agent, collect DecisionRecords, check for escalations "
        "(confidence < 0.7 triggers human review), produce workflow summary.",
    ),
    (
        "openinsure-billing",
        "You are the OpenInsure Billing Agent for commercial insurance.\n\n"
        "Capabilities: INVOICE GENERATION (on policy bind), PAYMENT RISK ASSESSMENT "
        "(predict defaults based on industry, size, payment history, claims frequency), "
        "COLLECTION STRATEGY (recommend actions: reminder, demand, cancellation notice, cancel), "
        "INSTALLMENT PLANNING (full_pay, quarterly, monthly).\n\n"
        "Provide: default_probability, risk_tier, recommended_billing_plan, collection_priority, "
        "recommended_action, grace_period_days, reasoning, confidence.",
    ),
    (
        "openinsure-document",
        "You are the OpenInsure Document Generation Agent for insurance policies.\n\n"
        "Capabilities: DECLARATIONS PAGE, CERTIFICATE OF INSURANCE, COVERAGE SCHEDULE generation "
        "from structured policy and submission data. Produces professional insurance language "
        "for executive summaries, coverage descriptions, conditions, and exclusions.\n\n"
        "Handle conditional sections (e.g., ransomware sublimit rider).\n"
        "Provide: title, document_type, sections (heading, content, data), effective_date, "
        "summary, confidence.",
    ),
    (
        "openinsure-analytics",
        "You are the OpenInsure Analytics Agent for insurance portfolio analysis.\n\n"
        "Capabilities: EXECUTIVE SUMMARIES (natural language), TREND IDENTIFICATION, "
        "ANOMALY DETECTION, CONCENTRATION RISK analysis across the book of business. "
        "Analyze submission pipelines, claims patterns, loss ratios, and underwriting profitability.\n\n"
        "Produce actionable insights with severity ratings and strategic recommendations.\n"
        "Provide: executive_summary, insights (category, title, summary, severity), "
        "recommendations, confidence.",
    ),
    (
        "openinsure-enrichment",
        "You are the OpenInsure Data Enrichment Agent for cyber insurance submissions.\n\n"
        "Capabilities: RISK SIGNAL SYNTHESIS from third-party data sources including OSINT, "
        "vulnerability databases, breach history, financial stability indicators, and "
        "industry benchmarks. Assess data quality and produce composite risk scores "
        "with sourced evidence for underwriting decisions.\n\n"
        "Provide: risk_signals (signal, severity, source), composite_risk_score, "
        "data_quality, recommendations, confidence, summary.",
    ),
]

# ---------------------------------------------------------------------------
# Function tool definitions (underwriting agent only) — dict format
# ---------------------------------------------------------------------------

# NOTE: The PromptAgent API requires "name" at the tool root level in addition
# to inside "function".  Without it the server returns a ValidationError.
FUNC_GET_RATING_FACTORS = {
    "type": "function",
    "name": "get_rating_factors",
    "function": {
        "name": "get_rating_factors",
        "description": (
            "Get cyber insurance rating factors for a line of business. "
            "Returns base rates, industry multipliers, and security control requirements."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "lob": {
                    "type": "string",
                    "description": "Line of business (e.g., 'cyber', 'property')",
                },
            },
            "required": ["lob"],
        },
    },
}

FUNC_GET_COMPARABLE_ACCOUNTS = {
    "type": "function",
    "name": "get_comparable_accounts",
    "function": {
        "name": "get_comparable_accounts",
        "description": (
            "Find similar historical accounts for pricing comparison. "
            "Matches by industry, revenue, employee count, and security maturity."
        ),
        "parameters": {
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
    },
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def discover_search_connection(client: AIProjectClient) -> str | None:
    """Find an Azure AI Search connection in the project."""
    try:
        for conn in client.connections.list():
            conn_type = str(getattr(conn, "connection_type", "")).lower()
            conn_name = str(getattr(conn, "name", "")).lower()
            if "search" in conn_type or "search" in conn_name:
                print(f"  Found search connection: {conn.id} ({conn_name})")
                return conn.id
    except Exception as e:
        print(f"  Warning: Could not list connections: {e}")
    return None


def build_search_tool(connection_id: str) -> dict:
    """Build Azure AI Search tool definition as a plain dict."""
    return {
        "type": "azure_ai_search",
        "azure_ai_search": {
            "indexes": [
                {
                    "index_connection_id": connection_id,
                    "index_name": "openinsure-knowledge",
                }
            ]
        },
    }


def build_tools(agent_name: str, search_connection_id: str | None) -> list[dict]:
    """Build the full tool list for a specific agent."""
    tools: list[dict] = []

    # AI Search on ALL agents
    if search_connection_id:
        tools.append(build_search_tool(search_connection_id))

    # Function calling on underwriting agent only
    if agent_name == "openinsure-underwriting":
        tools.append(FUNC_GET_RATING_FACTORS)
        tools.append(FUNC_GET_COMPARABLE_ACCOUNTS)

    return tools


def describe_tools(tools: list[dict]) -> str:
    """Human-readable summary of tools attached."""
    if not tools:
        return "none"
    labels: list[str] = []
    func_names: list[str] = []
    for t in tools:
        t_type = t.get("type", "unknown")
        if t_type == "azure_ai_search":
            labels.append("ai_search")
        elif t_type == "function":
            func_names.append(t["function"]["name"])
        else:
            labels.append(t_type)
    if func_names:
        labels.append(f"function({', '.join(func_names)})")
    return ", ".join(labels)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    credential = DefaultAzureCredential()
    client = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=credential)

    print("=" * 60)
    print("Deploy All OpenInsure Agents with Tools")
    print("=" * 60)
    print(f"  Endpoint : {PROJECT_ENDPOINT}")
    print(f"  Model    : {MODEL}")
    print()

    # Discover AI Search connection
    print("Discovering Azure AI Search connection...")
    search_connection_id = discover_search_connection(client)
    if search_connection_id:
        print("  => Will attach AI Search to all agents")
    else:
        print("  => No search connection found — deploying without AI Search")
    print()

    # Deploy each agent
    print(f"Deploying {len(AGENTS)} agents...\n")
    succeeded = 0
    failed = 0

    for name, instructions in AGENTS:
        tools = build_tools(name, search_connection_id)
        tool_desc = describe_tools(tools)
        try:
            agent = client.agents.create_version(
                agent_name=name,
                definition=PromptAgentDefinition(
                    model=MODEL,
                    instructions=instructions,
                    tools=tools if tools else None,
                ),
            )
            print(f"  OK  {name} v{agent.version} [tools: {tool_desc}]")
            succeeded += 1
        except Exception as e:
            print(f"  FAIL {name}: {e}")
            failed += 1

    # Verify
    print(f"\nResults: {succeeded} succeeded, {failed} failed\n")
    print("Deployed agents:")
    for a in client.agents.list():
        if a.name and a.name.startswith("openinsure"):
            print(f"  {a.name}")

    print("\nDone. Verify at: https://ai.azure.com")


if __name__ == "__main__":
    main()
