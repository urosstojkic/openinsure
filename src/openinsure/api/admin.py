"""Admin endpoints for platform management."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter

router = APIRouter()
logger = structlog.get_logger()

AGENT_DEFINITIONS: list[dict[str, str]] = [
    {
        "name": "openinsure-submission",
        "instructions": "Cyber insurance submission intake and triage. Classifies documents, extracts data, validates completeness, checks appetite, scores risk (1-10). Respond with JSON: {appetite_match, risk_score, risk_factors, recommendation, confidence, reasoning}.",
    },
    {
        "name": "openinsure-underwriting",
        "instructions": "Cyber insurance underwriting and pricing. Multi-factor risk assessment, rating calculation, terms generation. Respond with JSON: {risk_score, recommended_premium, rating_breakdown, confidence, conditions}.",
    },
    {
        "name": "openinsure-policy",
        "instructions": "Policy lifecycle management. Reviews underwriting terms, verifies coverages, validates terms. Respond with JSON: {recommendation, coverage_adequate, terms_complete, notes, confidence}.",
    },
    {
        "name": "openinsure-claims",
        "instructions": "Claims assessment for cyber insurance. Verifies coverage, estimates severity and reserves, detects fraud, identifies subrogation. Respond with JSON: {coverage_confirmed, severity_tier, initial_reserve, fraud_score, subrogation_potential, confidence}.",
    },
    {
        "name": "openinsure-compliance",
        "instructions": "EU AI Act compliance auditing. Reviews AI decisions for Art.9-14 compliance. Respond with JSON: {compliant, issues, recommendations}.",
    },
    {
        "name": "openinsure-orchestrator",
        "instructions": "Multi-agent workflow orchestrator. Coordinates submission processing, determines routing (standard/expedited/referral). Respond with JSON: {processing_path, priority, notes, confidence}.",
    },
    {
        "name": "openinsure-billing",
        "instructions": "AI billing agent. Predicts payment defaults, recommends billing plans, suggests collection strategies. Respond with JSON: {default_probability, risk_tier, recommended_billing_plan, collection_priority, confidence}.",
    },
    {
        "name": "openinsure-document",
        "instructions": "Policy document generation. Creates declarations, certificates, coverage schedules in natural insurance language. Respond with JSON: {title, sections[], summary, confidence}.",
    },
    {
        "name": "openinsure-analytics",
        "instructions": "Insurance analytics. Generates NL executive summaries, identifies concentration risks, suggests rate adjustments. Respond with JSON: {summary, insights[], risk_alerts[], recommendations[]}.",
    },
    {
        "name": "openinsure-enrichment",
        "instructions": "Data enrichment. Synthesizes risk signals from external sources (security ratings, firmographics). Respond with JSON: {risk_signals[], composite_risk_score, data_quality, recommendations[], confidence}.",
    },
]


@router.post("/deploy-agents")
async def deploy_foundry_agents() -> dict[str, Any]:
    """Deploy all OpenInsure agents to Microsoft Foundry.

    Uses the backend's managed identity which has Azure AI Developer role.
    """
    try:
        from azure.ai.projects import AIProjectClient
        from azure.identity import DefaultAzureCredential

        from openinsure.config import get_settings

        settings = get_settings()
        if not settings.foundry_project_endpoint:
            return {"error": "FOUNDRY_PROJECT_ENDPOINT not configured"}

        client = AIProjectClient(
            endpoint=settings.foundry_project_endpoint,
            credential=DefaultAzureCredential(),
        )

        # List existing agents
        existing: dict[str, str] = {}
        try:
            for agent in client.agents.list_agents():
                existing[agent.name] = agent.id
        except (AttributeError, Exception):
            # SDK might not support list — try OpenAI path
            try:
                oai = client.get_openai_client()
                for agent in oai.beta.assistants.list().data:
                    existing[agent.name] = agent.id
            except Exception:
                logger.debug("admin.list_agents_unavailable")

        results: list[dict[str, str]] = []
        for defn in AGENT_DEFINITIONS:
            name = defn["name"]
            if name in existing:
                results.append({"name": name, "status": "already_exists", "id": existing[name]})
                continue
            # Create — try multiple SDK paths
            try:
                agent = client.agents.create_agent(
                    model="gpt-4o",
                    name=name,
                    instructions=defn["instructions"],
                )
                results.append({"name": name, "status": "created", "id": agent.id})
            except (AttributeError, Exception) as e1:
                try:
                    oai = client.get_openai_client()
                    agent = oai.beta.assistants.create(
                        model="gpt-4o",
                        name=name,
                        instructions=defn["instructions"],
                    )
                    results.append({"name": name, "status": "created_oai", "id": agent.id})
                except Exception as e2:
                    # Last resort: use Responses API to "register" the agent
                    # by invoking it once — Foundry auto-creates prompt agents
                    try:
                        oai = client.get_openai_client()
                        oai.responses.create(
                            input=[{"role": "user", "content": "Initialize agent. Respond with: ready"}],
                            extra_body={"agent_reference": {"name": name, "type": "agent_reference"}},
                        )
                        results.append({"name": name, "status": "created_via_invoke"})
                    except Exception as e3:
                        results.append(
                            {
                                "name": name,
                                "status": "all_methods_failed",
                                "error": f"agents: {str(e1)[:80]} | oai: {str(e2)[:80]} | invoke: {str(e3)[:80]}",
                            }
                        )

        logger.info("admin.deploy_agents", total=len(results), results=results)
        return {
            "total": len(results),
            "agents": results,
            "existing_before": len(existing),
        }

    except ImportError as e:
        return {"error": f"Missing SDK: {e}"}
    except Exception as e:
        return {"error": str(e)[:500]}
