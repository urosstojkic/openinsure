"""Test the OpenInsure multi-agent workflow in Microsoft Foundry.

Runs a complete new business submission through all agents.
"""

import json
from azure.ai.projects import AIProjectClient
from azure.identity import AzureCliCredential

PROJECT_ENDPOINT = "https://uros-ai-foundry-demo-resource.services.ai.azure.com/api/projects/uros-ai-foundry-demo"
client = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=AzureCliCredential())

# Get agent IDs
agents = {}
for a in client.agents.list_agents():
    if a.name and a.name.startswith("openinsure"):
        agents[a.name] = a.id
print(f"Loaded {len(agents)} agents\n")

# Sample cyber insurance submission
submission = """
New cyber insurance submission from Acme Cyber Corp:
- Company: Acme Cyber Corp
- Industry: SIC 7372 (Computer Services)
- Annual Revenue: $5,000,000
- Employees: 50
- Security Maturity Score: 7/10
- Has MFA: Yes
- Has Endpoint Protection: Yes
- Has Backup Strategy: Yes
- Has Incident Response Plan: No
- Prior Cyber Incidents: 0
- Requested Coverage: $1M limit, $10K deductible
- Effective Date: 2026-07-01
"""

def run_agent(agent_name: str, message: str) -> str:
    """Run a single agent and return its response."""
    agent_id = agents[agent_name]
    thread = client.agents.threads.create()
    client.agents.messages.create(thread_id=thread.id, role="user", content=message)
    run = client.agents.runs.create_and_process(thread_id=thread.id, agent_id=agent_id)
    
    if run.status == "failed":
        return f"FAILED: {run.last_error}"
    
    messages = list(client.agents.messages.list(thread_id=thread.id))
    for msg in messages:
        if msg.role == "assistant":
            for content in msg.content:
                if hasattr(content, "text"):
                    return content.text.value
    return "No response"


print("=" * 60)
print("OPENINSURE NEW BUSINESS WORKFLOW")
print("=" * 60)

# Step 1: Submission Agent — Intake & Triage
print("\n--- Step 1: Submission Agent (Intake & Triage) ---")
triage_result = run_agent("openinsure-submission", f"Triage this cyber insurance submission and provide risk score, appetite match, and priority:\n{submission}")
print(triage_result[:500])

# Step 2: Underwriting Agent — Risk Assessment & Pricing
print("\n--- Step 2: Underwriting Agent (Risk Assessment & Pricing) ---")
uw_result = run_agent("openinsure-underwriting", f"Assess risk and generate pricing for this cyber submission. Previous triage result: {triage_result[:300]}\n\nSubmission details:\n{submission}")
print(uw_result[:500])

# Step 3: Policy Agent — Bind Decision
print("\n--- Step 3: Policy Agent (Bind Decision) ---")
policy_result = run_agent("openinsure-policy", f"Based on the underwriting assessment, determine if this policy can be bound. Underwriting result: {uw_result[:300]}\n\nSubmission: {submission}")
print(policy_result[:500])

# Step 4: Compliance Agent — Audit
print("\n--- Step 4: Compliance Agent (Audit & Validation) ---")
compliance_result = run_agent("openinsure-compliance", f"Review the complete workflow for EU AI Act compliance. Triage: {triage_result[:200]}\nUnderwriting: {uw_result[:200]}\nPolicy: {policy_result[:200]}")
print(compliance_result[:500])

print("\n" + "=" * 60)
print("WORKFLOW COMPLETE")
print("=" * 60)
