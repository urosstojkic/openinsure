"""Migrate OpenInsure agents to new Microsoft Foundry Agent Service API.

Uses create_version() with PromptAgentDefinition so agents are visible
in the new Microsoft Foundry portal (not just classic).
"""

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition
from azure.identity import AzureCliCredential

PROJECT = "https://uros-ai-foundry-demo-resource.services.ai.azure.com/api/projects/uros-ai-foundry-demo"
client = AIProjectClient(endpoint=PROJECT, credential=AzureCliCredential())

# Delete old classic agents via the new list API
print("Cleaning old agents...")
for a in client.agents.list():
    if a.name and a.name.startswith("openinsure"):
        try:
            client.agents.delete(agent_name=a.name)
            print(f"  Deleted: {a.name}")
        except Exception as e:
            print(f"  Skip {a.name}: {e}")

AGENTS = [
    ("openinsure-submission", "Cyber insurance submission intake and triage. Classifies documents, extracts structured data, validates completeness, checks appetite, scores risk (1-10), assigns priority. Responds with structured JSON."),
    ("openinsure-underwriting", "Cyber insurance underwriting and pricing. Multi-factor risk assessment, comparable analysis, terms generation, authority check (<$100K auto-bind). Provides risk_score, premium, confidence, authority_decision."),
    ("openinsure-policy", "Policy lifecycle management: bind, endorse, renew, cancel. Validates requirements, recalculates premiums, generates documents. Produces EU AI Act compliant DecisionRecords."),
    ("openinsure-claims", "Cyber claims lifecycle: FNOL intake, coverage verification, initial reserving, triage, fraud scoring. Provides severity_tier, reserve_estimate, fraud_score, escalation_recommendation."),
    ("openinsure-compliance", "EU AI Act compliance agent. Decision audit, bias monitoring (4/5ths rule), regulatory checks, Art. 9-15 documentation. Flags low confidence, missing reasoning, potential bias."),
    ("openinsure-orchestrator", "Multi-agent workflow orchestrator. New Business: Submission->Underwriting->Policy->Billing->Compliance. Claims: FNOL->Reserve->Compliance. Collects DecisionRecords, checks escalations."),
]

print("\nCreating agents with new API (create_version)...")
for name, instructions in AGENTS:
    try:
        agent = client.agents.create_version(
            agent_name=name,
            definition=PromptAgentDefinition(
                model="gpt-5.1",
                instructions=instructions,
            ),
        )
        print(f"  Created: {name} (version {agent.version})")
    except Exception as e:
        print(f"  Error {name}: {e}")

print("\nDone. Agents should now be visible in the new Microsoft Foundry portal.")
