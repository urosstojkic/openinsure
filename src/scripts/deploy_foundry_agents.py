"""Deploy OpenInsure agents to Microsoft Foundry Agent Service.

Uses the new create_version() API with PromptAgentDefinition so agents are
visible in both the classic and new Microsoft Foundry portal experiences.

Requires: azure-ai-projects>=2.0.0, azure-identity

Usage:
    python src/scripts/deploy_foundry_agents.py
"""

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition
from azure.identity import DefaultAzureCredential

PROJECT_ENDPOINT = "https://uros-ai-foundry-demo-resource.services.ai.azure.com/api/projects/uros-ai-foundry-demo"

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
]


def main() -> None:
    client = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=DefaultAzureCredential())

    print("Deploying OpenInsure agents to Microsoft Foundry...\n")
    for name, instructions in AGENTS:
        try:
            agent = client.agents.create_version(
                agent_name=name,
                definition=PromptAgentDefinition(
                    model="gpt-5.1",
                    instructions=instructions,
                ),
            )
            print(f"  ✓ {name} (version {agent.version})")
        except Exception as e:
            print(f"  ✗ {name}: {e}")

    print("\nVerifying agents:")
    for a in client.agents.list():
        if a.name and a.name.startswith("openinsure"):
            print(f"  {a.name}")

    print("\nDone. Agents visible at: https://ai.azure.com")


if __name__ == "__main__":
    main()
