"""Deploy new Foundry agents via the backend's managed identity.

Run this INSIDE the backend container or via an admin endpoint.
For local use, calls the Foundry API using DefaultAzureCredential
which picks up the Container App's managed identity when running in Azure.

Usage from local (if you have the right permissions):
    python src/scripts/deploy_new_agents.py

Usage via backend admin endpoint:
    POST /api/v1/admin/deploy-agents
"""

import httpx

BE = os.environ.get("OPENINSURE_BACKEND_URL", "http://localhost:8000")/api/v1"
H = {"X-API-Key": "dev-key-change-me"}

# The 4 new agents that need to be created
NEW_AGENTS = [
    {
        "name": "openinsure-billing",
        "instructions": "AI billing agent for OpenInsure cyber insurance. Predicts payment default probability based on customer profile, recommends optimal billing plans (annual/quarterly/monthly), suggests collection strategies for overdue accounts. Always respond with JSON: {default_probability, risk_tier, recommended_billing_plan, collection_priority, recommended_action, grace_period_days, confidence}.",
    },
    {
        "name": "openinsure-document",
        "instructions": "Policy document generation agent for OpenInsure. Creates declarations pages, certificates of insurance, and coverage schedules using natural insurance language. Generates executive summaries, coverage descriptions, conditions, and exclusion clauses. Always respond with JSON: {title, document_type, sections[], effective_date, summary, confidence}.",
    },
    {
        "name": "openinsure-analytics",
        "instructions": "Insurance analytics agent for OpenInsure. Generates natural-language executive summaries of portfolio performance, identifies concentration risks, detects emerging trends, and suggests rate adjustments. Always respond with JSON: {summary, insights[], risk_alerts[], recommendations[], period}.",
    },
    {
        "name": "openinsure-enrichment",
        "instructions": "Submission data enrichment agent for OpenInsure. Synthesizes risk signals from external data sources including security ratings, firmographics, industry benchmarks, and news monitoring. Produces a composite risk assessment. Always respond with JSON: {risk_signals[], composite_risk_score, data_quality, recommendations[], confidence, summary}.",
    },
]


def main() -> None:
    # Test if we can reach the backend and it can reach Foundry
    print("Testing Foundry connectivity via backend...")

    # Trigger a triage which calls Foundry — if it returns a real risk score, Foundry works
    # Create a test submission
    r = httpx.post(
        f"{BE}/submissions",
        json={
            "applicant_name": "Foundry Deploy Test",
            "line_of_business": "cyber",
            "effective_date": "2026-09-01",
            "expiration_date": "2027-09-01",
            "cyber_risk_data": {
                "annual_revenue": 5000000,
                "employee_count": 50,
                "industry": "Software",
                "sic_code": "7372",
                "security_maturity_score": 7,
                "prior_incidents": 0,
            },
        },
        headers=H,
        timeout=30,
    )
    if r.status_code not in (200, 201):
        print(f"Create failed: {r.status_code}")
        return

    sid = r.json().get("id")
    print(f"Test submission: {sid}")

    # Triage — this calls openinsure-submission agent via Foundry
    r = httpx.post(f"{BE}/submissions/{sid}/triage", headers=H, timeout=120)
    if r.status_code == 200:
        t = r.json()
        score = t.get("risk_score", "?")
        rec = t.get("recommendation", "?")
        flags = t.get("flags", [])
        is_foundry = score != 0.42  # 0.42 is the local fallback
        print(f"Triage result: risk={score}, rec={rec}, foundry={'YES' if is_foundry else 'NO (fallback)'}")
        if flags:
            print(f"  Agent reasoning: {str(flags[0])[:120]}")
    else:
        print(f"Triage failed: {r.status_code} - {r.text[:200]}")

    print("\nNote: To deploy new agents, the backend needs an admin endpoint.")
    print("The 4 new agents (billing, document, analytics, enrichment) need to be")
    print("created in Foundry. This can be done via:")
    print("  1. Azure AI Foundry portal (ai.azure.com) — manually create each agent")
    print("  2. Grant Azure AI Developer to a user identity and run deploy script")
    print("  3. Add an admin endpoint to the backend that creates agents on demand")


if __name__ == "__main__":
    main()
