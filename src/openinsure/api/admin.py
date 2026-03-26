"""Admin endpoints for platform management."""
# mypy: ignore-errors

from __future__ import annotations

import contextlib
from typing import Any

import structlog
from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter()
logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class AgentResult(BaseModel):
    name: str
    status: str
    id: str | None = None
    error: str | None = None


class DeployAgentsResponse(BaseModel):
    total: int = 0
    agents: list[AgentResult] = Field(default_factory=list)
    existing_before: int = 0
    error: str | None = None


class SeedKnowledgeResponse(BaseModel):
    total: int = 0
    seeded: dict[str, int] = Field(default_factory=dict)
    error: str | None = None


class SyncProductsResponse(BaseModel):
    total: int = 0
    synced: int = 0
    error: str | None = None
    model_config = {"extra": "allow"}


class SyncKnowledgeResponse(BaseModel):
    cosmos_docs: int = 0
    indexed: int = 0
    containers_scanned: int = 0
    error: str | None = None


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


@router.post("/deploy-agents", response_model=DeployAgentsResponse)
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
            for agent in client.agents.list_agents():  # type: ignore[attr-defined]
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
                        logger.exception(
                            "admin.deploy_agent_failed",
                            agent=name,
                            agents_err=str(e1),
                            oai_err=str(e2),
                            invoke_err=str(e3),
                        )
                        results.append(
                            {
                                "name": name,
                                "status": "all_methods_failed",
                                "error": "Agent creation failed — see server logs",
                            }
                        )

        logger.info("admin.deploy_agents", total=len(results), results=results)
        return {
            "total": len(results),
            "agents": results,
            "existing_before": len(existing),
        }

    except ImportError:
        logger.exception("admin.deploy_agents_missing_sdk")
        return {"error": "Required SDK not installed"}
    except Exception:
        logger.exception("admin.deploy_agents_failed")
        return {"error": "Internal server error"}


@router.post("/seed-knowledge", response_model=SeedKnowledgeResponse)
async def seed_knowledge() -> dict[str, Any]:
    """Seed Cosmos DB with knowledge base data from YAML files and in-memory store.

    Uses the backend's managed identity which has Cosmos DB access via the VNet.
    """
    try:
        from openinsure.config import get_settings
        from openinsure.infrastructure.knowledge_store import InMemoryKnowledgeStore

        settings = get_settings()
        if not settings.cosmos_endpoint:
            return {"error": "COSMOS_ENDPOINT not configured"}

        from azure.cosmos import CosmosClient
        from azure.identity import DefaultAzureCredential

        credential = DefaultAzureCredential()
        cosmos = CosmosClient(settings.cosmos_endpoint, credential=credential)
        db = cosmos.get_database_client(settings.cosmos_database_name or "openinsure-knowledge")

        # Ensure containers exist
        containers = [
            "guidelines",
            "rating_factors",
            "claims_precedents",
            "compliance_rules",
            "coverage_options",
            "industry_profiles",
            "jurisdiction_rules",
        ]
        for name in containers:
            with contextlib.suppress(Exception):
                db.create_container_if_not_exists(id=name, partition_key={"paths": ["/category"], "kind": "Hash"})

        # Load knowledge from in-memory store
        store = InMemoryKnowledgeStore()
        results: dict[str, int] = {}

        # Guidelines
        for lob in ["cyber", "general_liability", "property"]:
            data = store.get_guidelines(lob)
            if data:
                container = db.get_container_client("guidelines")
                doc = {"id": f"guidelines-{lob}", "category": "guidelines", "lob": lob, "content": data}
                container.upsert_item(doc)
                results[f"guidelines-{lob}"] = 1

        # Rating factors
        for lob in ["cyber", "general_liability", "property"]:
            data = store.get_rating_factors(lob)
            if data:
                container = db.get_container_client("rating_factors")
                doc = {"id": f"rating-{lob}", "category": "rating_factors", "lob": lob, "content": data}
                container.upsert_item(doc)
                results[f"rating-{lob}"] = 1

        # Claims precedents
        for ctype in ["ransomware", "data_breach", "business_interruption", "social_engineering"]:
            data = store.get_claims_precedents(ctype)
            if data:
                container = db.get_container_client("claims_precedents")
                doc = {
                    "id": f"precedent-{ctype}",
                    "category": "claims_precedents",
                    "claim_type": ctype,
                    "content": data,
                }
                container.upsert_item(doc)
                results[f"precedent-{ctype}"] = 1

        # Compliance rules
        for framework in ["eu_ai_act", "naic_model_bulletin", "gdpr"]:
            data = store.get_compliance_rules(framework)
            if data:
                container = db.get_container_client("compliance_rules")
                doc = {
                    "id": f"compliance-{framework}",
                    "category": "compliance_rules",
                    "framework": framework,
                    "content": data,
                }
                container.upsert_item(doc)
                results[f"compliance-{framework}"] = 1

        total = sum(results.values())
        logger.info("admin.seed_knowledge", total=total, results=results)
        return {"total": total, "seeded": results}

    except Exception:
        logger.exception("admin.seed_knowledge_failed")
        return {"error": "Internal server error"}


@router.post("/sync-products", response_model=SyncProductsResponse)
async def sync_products_to_knowledge() -> dict[str, Any]:
    """Sync ALL products from SQL to Cosmos DB and AI Search.

    This ensures Foundry agents have current product definitions including
    coverages, appetite rules, rating factors, and authority limits.
    Use after bulk product imports, infrastructure changes, or as a periodic job.
    """
    try:
        from openinsure.services.product_knowledge_sync import ProductKnowledgeSyncService

        svc = ProductKnowledgeSyncService()
        return await svc.sync_all_products()
    except Exception:
        logger.exception("admin.sync_products_failed")
        return {"error": "Internal server error"}


@router.post("/sync-knowledge", response_model=SyncKnowledgeResponse)
async def sync_knowledge_to_search() -> dict[str, Any]:
    """Sync knowledge from Cosmos DB to Azure AI Search.

    Reads all knowledge from Cosmos and pushes to AI Search index.
    This is the workaround for Cosmos DB indexer not supporting
    disableLocalAuth=true with managed identity.
    """
    try:
        from openinsure.config import get_settings

        settings = get_settings()
        if not settings.cosmos_endpoint:
            return {"error": "COSMOS_ENDPOINT not configured"}

        from azure.cosmos import CosmosClient
        from azure.identity import DefaultAzureCredential
        from azure.search.documents import SearchClient

        credential = DefaultAzureCredential()
        cosmos = CosmosClient(settings.cosmos_endpoint, credential=credential)
        db = cosmos.get_database_client(settings.cosmos_database_name or "openinsure-knowledge")

        # Read all knowledge from Cosmos
        docs = []
        containers = [
            "guidelines",
            "rating_factors",
            "claims_precedents",
            "compliance_rules",
            "coverage_options",
            "industry_profiles",
            "jurisdiction_rules",
        ]
        for container_name in containers:
            with contextlib.suppress(Exception):
                container = db.get_container_client(container_name)
                for item in container.read_all_items():
                    import json

                    content_str = json.dumps(item.get("content", item), default=str)
                    docs.append(
                        {
                            "id": item["id"],
                            "content": content_str[:30000],
                            "category": item.get("category", container_name),
                            "source": f"cosmos/{container_name}",
                            "tags": [container_name],
                        }
                    )

        if not docs:
            return {"error": "No documents found in Cosmos DB"}

        # Push to AI Search
        search_endpoint = settings.search_endpoint
        if not search_endpoint:
            return {"error": "SEARCH_ENDPOINT not configured", "cosmos_docs": len(docs)}

        search_client = SearchClient(
            endpoint=search_endpoint,
            index_name="openinsure-knowledge",
            credential=credential,
        )
        result = search_client.upload_documents(documents=docs)
        succeeded = sum(1 for r in result if r.succeeded)

        logger.info("admin.sync_knowledge", cosmos_docs=len(docs), indexed=succeeded)
        return {
            "cosmos_docs": len(docs),
            "indexed": succeeded,
            "containers_scanned": len(containers),
        }

    except Exception:
        logger.exception("admin.sync_knowledge_failed")
        return {"error": "Internal server error"}
