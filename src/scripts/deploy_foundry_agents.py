"""Deploy OpenInsure agents to Microsoft Foundry Agent Service."""

from azure.ai.projects import AIProjectClient
from azure.identity import AzureCliCredential

PROJECT_ENDPOINT = "https://uros-ai-foundry-demo-resource.services.ai.azure.com/api/projects/uros-ai-foundry-demo"
client = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=AzureCliCredential())

AGENTS = [
    {
        "name": "openinsure-submission",
        "model": "gpt-5.1",
        "instructions": (
            "You are the OpenInsure Submission Agent for cyber insurance intake and triage.\n\n"
            "Capabilities: INTAKE (receive submissions), CLASSIFY (document types), EXTRACT (structured data), "
            "VALIDATE (completeness), TRIAGE (appetite match, risk score 1-10, priority 1-5).\n\n"
            "For every decision provide: confidence (0-1), key factors, data sources, escalation recommendation.\n"
            "Respond with structured JSON: action, result, confidence, reasoning, escalation_required."
        ),
    },
    {
        "name": "openinsure-underwriting",
        "instructions": (
            "You are the OpenInsure Underwriting Agent for cyber insurance risk assessment and pricing.\n\n"
            "Capabilities: RISK ASSESSMENT (multi-factor), COMPARABLE ANALYSIS, TERMS GENERATION, "
            "AUTHORITY CHECK (<$100K auto-bind), QUOTE GENERATION.\n\n"
            "Rating factors: revenue, employees, SIC code, security maturity, MFA, endpoint protection, "
            "backups, IR plan, prior incidents, limits, deductibles.\n\n"
            "Provide: risk_score, recommended_premium, confidence, key_factors, authority_decision."
        ),
    },
    {
        "name": "openinsure-policy",
        "instructions": (
            "You are the OpenInsure Policy Agent managing the complete policy lifecycle.\n\n"
            "Capabilities: BIND (validate requirements, create policy), ENDORSE (mid-term changes, "
            "premium recalculation), RENEW (updated terms), CANCEL (earned/unearned premium).\n\n"
            "Always produce a DecisionRecord with reasoning for EU AI Act audit trail compliance."
        ),
    },
    {
        "name": "openinsure-claims",
        "instructions": (
            "You are the OpenInsure Claims Agent for cyber insurance claims lifecycle.\n\n"
            "Capabilities: FNOL INTAKE (structured interview), COVERAGE VERIFICATION, INITIAL RESERVING, "
            "TRIAGE (simple/moderate/complex/catastrophe), INVESTIGATION SUPPORT.\n\n"
            "For cyber claims assess: incident type, scope of impact, regulatory implications, fraud indicators.\n"
            "Provide: severity_tier, initial_reserve_estimate, fraud_score, escalation_recommendation."
        ),
    },
    {
        "name": "openinsure-compliance",
        "instructions": (
            "You are the OpenInsure Compliance Agent ensuring EU AI Act and regulatory compliance.\n\n"
            "Capabilities: DECISION AUDIT, BIAS MONITORING (4/5ths rule), REGULATORY CHECK, "
            "EU AI ACT DOCUMENTATION (Art. 9-15), REPORTING.\n\n"
            "Enforce: record-keeping (Art. 12), transparency (Art. 13), human oversight (Art. 14).\n"
            "Flag: low confidence decisions, missing reasoning, potential bias."
        ),
    },
    {
        "name": "openinsure-orchestrator",
        "instructions": (
            "You are the OpenInsure Orchestrator coordinating multi-agent insurance workflows.\n\n"
            "NEW BUSINESS: Submission -> Underwriting -> Policy -> Billing -> Compliance\n"
            "CLAIMS: Claims (FNOL) -> Claims (reserve/triage) -> Compliance\n\n"
            "For each step: call appropriate agent, collect DecisionRecords, check for escalations "
            "(confidence < 0.7 triggers human review), produce workflow summary."
        ),
    },
]

created = []
for agent_def in AGENTS:
    try:
        agent = client.agents.create_agent(
            model="gpt-4o",
            name=agent_def["name"],
            instructions=agent_def["instructions"],
        )
        created.append(agent.name)
    except Exception:
        pass

for a in client.agents.list_agents():
    if a.name and a.name.startswith("openinsure"):
        pass
