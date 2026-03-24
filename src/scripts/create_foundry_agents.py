"""Create the 4 new Foundry agents using your personal account credentials."""

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

ENDPOINT = "https://uros-ai-foundry-demo-resource.services.ai.azure.com/api/projects/uros-ai-foundry-demo"

NEW_AGENTS = [
    (
        "openinsure-billing",
        "AI-native billing agent for OpenInsure cyber insurance. "
        "Predicts payment default probability, recommends billing plans (annual/quarterly/monthly), "
        "suggests collection strategies. Respond with JSON containing: "
        "default_probability, risk_tier, recommended_billing_plan, collection_priority, "
        "recommended_action, grace_period_days, confidence, reasoning.",
    ),
    (
        "openinsure-document",
        "Document generation agent for OpenInsure insurance policies. "
        "Creates declarations pages, certificates of insurance, and coverage schedules "
        "in professional insurance language. Generates executive summaries, "
        "coverage descriptions, conditions, exclusions. Respond with JSON containing: "
        "title, document_type, sections (list of heading+content), summary, confidence.",
    ),
    (
        "openinsure-analytics",
        "Insurance portfolio analytics agent for OpenInsure. "
        "Generates natural-language executive summaries, identifies concentration risks, "
        "detects emerging trends, suggests rate adjustments. Respond with JSON containing: "
        "summary, insights (list with category/title/detail/severity), "
        "recommendations, confidence.",
    ),
    (
        "openinsure-enrichment",
        "Submission data enrichment agent for OpenInsure. "
        "Synthesizes risk signals from external data: security ratings, firmographics, "
        "industry benchmarks, news monitoring. Produces composite risk assessment. "
        "Respond with JSON containing: risk_signals (list with source/signal/impact), "
        "composite_risk_score (1-10), data_quality, recommendations, confidence.",
    ),
]


def main() -> None:
    client = AIProjectClient(endpoint=ENDPOINT, credential=DefaultAzureCredential())

    # List existing
    print("Existing agents in Foundry:")
    existing = set()
    for agent in client.agents.list_agents():
        existing.add(agent.name)
        print(f"  {agent.name}: {agent.id}")

    # Create new
    print()
    for name, instructions in NEW_AGENTS:
        if name in existing:
            print(f"ALREADY EXISTS: {name}")
            continue
        try:
            agent = client.agents.create_agent(model="gpt-4o", name=name, instructions=instructions)
            print(f"CREATED: {name} ({agent.id})")
        except Exception as e:
            print(f"FAILED: {name} — {e}")

    # Final count
    print()
    print("All agents after deploy:")
    for agent in client.agents.list_agents():
        print(f"  {agent.name}: {agent.id}")


if __name__ == "__main__":
    main()
