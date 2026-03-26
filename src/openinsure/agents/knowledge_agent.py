"""Knowledge graph agent for OpenInsure.

Provides an agent interface to the insurance knowledge graph: querying
underwriting guidelines, regulatory requirements, coverage rules, and
general insurance domain knowledge.
"""

from typing import Any

import structlog

from openinsure.agents.base import AgentCapability, AgentConfig, InsuranceAgent
from openinsure.domain.limits import PLATFORM_LIMITS
from openinsure.infrastructure.knowledge_store import (
    CLAIMS_PRECEDENTS,
    COMPLIANCE_RULES,
    COVERAGE_RULES,
    REGULATORY_REQUIREMENTS,
)

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Static knowledge store (production uses Cosmos DB Gremlin API)
#
# Maps below adapt the knowledge_store constants to the shape the agent
# queries expect.  The canonical data lives in
# ``infrastructure.knowledge_store``.
# ---------------------------------------------------------------------------

UNDERWRITING_GUIDELINES: dict[str, dict[str, Any]] = {
    "cyber": {
        "lob": "cyber",
        "min_revenue": "1000000",
        "max_revenue": "5000000000",
        "excluded_industries": ["banking", "gambling"],
        "required_controls": [
            "mfa",
            "endpoint_protection",
            "backup_strategy",
            "incident_response_plan",
        ],
        "max_prior_incidents": 5,
        "authority_tiers": {
            "auto_bind": "500000",
            "senior_underwriter": "2000000",
            "committee": "10000000",
        },
        "minimum_premium": "5000",
    },
    "general_liability": {
        "lob": "general_liability",
        "min_revenue": "500000",
        "max_revenue": "2000000000",
        "excluded_industries": [],
        "required_controls": [],
        "authority_tiers": {
            "auto_bind": "250000",
            "senior_underwriter": "1000000",
            "committee": "5000000",
        },
        "minimum_premium": "2500",
    },
    "property": {
        "lob": "property",
        "min_insured_value": "100000",
        "max_insured_value": "500000000",
        "excluded_industries": [],
        "required_controls": ["sprinkler_system"],
        "authority_tiers": {
            "auto_bind": "1000000",
            "senior_underwriter": "5000000",
            "committee": "25000000",
        },
        "minimum_premium": "3000",
    },
}


class KnowledgeAgent(InsuranceAgent):
    """Knowledge graph query and update agent.

    Supported task types dispatched by :meth:`process`:
    - ``query`` – free-form knowledge graph query.
    - ``get_guidelines`` – retrieve underwriting guidelines for a LOB.
    - ``get_regulatory`` – retrieve regulatory requirements by jurisdiction.
    - ``get_coverage_rules`` – retrieve coverage / exclusion rules.
    - ``update`` – (stub) update knowledge graph entries.
    """

    def __init__(self, config: AgentConfig | None = None):
        super().__init__(
            config
            or AgentConfig(
                agent_id="knowledge_agent",
                agent_version="0.1.0",
                authority_limit=PLATFORM_LIMITS.agents.knowledge_agent,
            )
        )

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------

    @property
    def capabilities(self) -> list[AgentCapability]:
        return [
            AgentCapability(
                name="query_knowledge",
                description="Query the insurance knowledge graph",
                required_inputs=["query"],
                produces=["results"],
            ),
            AgentCapability(
                name="update_knowledge",
                description="Update entries in the insurance knowledge graph",
                required_inputs=["entity_type", "entity_data"],
                produces=["update_result"],
            ),
            AgentCapability(
                name="get_guidelines",
                description="Retrieve underwriting guidelines for a line of business",
                required_inputs=["line_of_business"],
                produces=["guidelines"],
            ),
            AgentCapability(
                name="get_regulatory_requirements",
                description="Retrieve regulatory requirements for a jurisdiction",
                required_inputs=["jurisdiction"],
                produces=["requirements"],
            ),
            AgentCapability(
                name="get_claims_precedents",
                description="Retrieve claims precedents by claim type for adjuster guidance",
                required_inputs=["claim_type"],
                produces=["precedents"],
            ),
            AgentCapability(
                name="get_compliance_rules",
                description="Retrieve compliance framework rules (EU AI Act, GDPR, NAIC)",
                required_inputs=["framework"],
                produces=["rules"],
            ),
        ]

    # ------------------------------------------------------------------
    # Main processing entry-point
    # ------------------------------------------------------------------

    async def process(self, task: dict[str, Any]) -> dict[str, Any]:
        # Try Cosmos DB knowledge store first
        from openinsure.infrastructure.factory import get_knowledge_store

        store = get_knowledge_store()
        if store:
            result = await self._process_with_store(store, task)
            result.setdefault("ai_mode", "static_knowledge")
            return result

        # Fall back to static dict logic
        task_type = task.get("type", "query")
        handler = {
            "query": self._query,
            "get_guidelines": self._get_guidelines,
            "get_regulatory": self._get_regulatory,
            "get_coverage_rules": self._get_coverage_rules,
            "get_claims_precedents": self._get_claims_precedents,
            "get_compliance_rules": self._get_compliance_rules,
            "update": self._update,
        }.get(task_type)

        if handler is None:
            raise ValueError(f"Unknown knowledge task type: {task_type}")

        self.logger.info("knowledge.task.dispatch", task_type=task_type)
        result = await handler(task)
        result["ai_mode"] = "static_knowledge"
        return result

    # ------------------------------------------------------------------
    # Cosmos DB store dispatch
    # ------------------------------------------------------------------

    async def _process_with_store(self, store: Any, task: dict[str, Any]) -> dict[str, Any]:
        """Process task using the Cosmos DB knowledge store."""
        task_type = task.get("type", "query")
        self.logger.info("knowledge.task.dispatch", task_type=task_type, backend="cosmos")

        if task_type == "get_guidelines":
            lob = task.get("line_of_business", "")
            docs = store.query_guidelines(lob)
            found = bool(docs)
            return {
                "found": found,
                "line_of_business": lob,
                "guidelines": docs[0] if docs else None,
                "confidence": 0.95 if found else 0.3,
                "reasoning": {"step": "get_guidelines", "lob": lob, "found": found},
                "data_sources": ["cosmos_knowledge_graph"],
                "knowledge_queries": [f"guidelines/{lob}"],
            }

        if task_type == "get_regulatory":
            jurisdiction = task.get("jurisdiction", "")
            docs = store.query_regulatory(jurisdiction)
            found = bool(docs)
            return {
                "found": found,
                "jurisdiction": jurisdiction,
                "requirements": docs[0] if docs else None,
                "confidence": 0.95 if found else 0.3,
                "reasoning": {"step": "get_regulatory", "jurisdiction": jurisdiction, "found": found},
                "data_sources": ["cosmos_knowledge_graph"],
                "knowledge_queries": [f"regulatory/{jurisdiction}"],
            }

        if task_type == "query":
            query = task.get("query", "")
            entity_type = task.get("entity_type")
            results = store.search_knowledge(query, entity_type=entity_type)
            return {
                "query": query,
                "results": results,
                "result_count": len(results),
                "confidence": 0.9 if results else 0.3,
                "reasoning": {"step": "query", "query": query, "stores_searched": ["cosmos"]},
                "data_sources": ["cosmos_knowledge_graph"],
                "knowledge_queries": [query],
            }

        if task_type == "update":
            entity_type = task.get("entity_type")
            entity_data = task.get("entity_data", {})
            if not entity_type:
                raise ValueError("entity_type is required for knowledge updates")
            doc = {"entityType": entity_type, **entity_data}
            if "id" not in doc:
                doc["id"] = f"{entity_type}-{hash(str(entity_data))}"
            store.upsert_document(doc)
            return {
                "updated": True,
                "entity_type": entity_type,
                "fields_updated": list(entity_data.keys()),
                "confidence": 0.90,
                "reasoning": {"step": "update", "entity_type": entity_type},
                "data_sources": ["cosmos_knowledge_graph"],
                "knowledge_queries": [f"update/{entity_type}"],
            }

        # For get_coverage_rules, use Cosmos with static fallback
        if task_type == "get_coverage_rules":
            coverage_code = task.get("coverage_code", "")
            docs = store.query_by_type("coverage_rule")
            if coverage_code:
                docs = [d for d in docs if d.get("coverage_code") == coverage_code]
            if docs:
                return {
                    "found": True,
                    "coverage_code": coverage_code,
                    "rules": docs[0] if coverage_code else docs,
                    "confidence": 0.95,
                    "reasoning": {"step": "get_coverage_rules", "code": coverage_code, "found": True},
                    "data_sources": ["cosmos_knowledge_graph"],
                    "knowledge_queries": [f"coverage_rules/{coverage_code}"],
                }
            # Fall through to static

        # For get_claims_precedents, search Cosmos
        if task_type == "get_claims_precedents":
            claim_type = task.get("claim_type", "")
            docs = store.query_by_type("claims_precedent")
            if claim_type:
                docs = [d for d in docs if d.get("claim_type") == claim_type]
            return {
                "found": bool(docs),
                "claim_type": claim_type,
                "precedents": docs,
                "result_count": len(docs),
                "confidence": 0.9 if docs else 0.3,
                "reasoning": {"step": "get_claims_precedents", "claim_type": claim_type},
                "data_sources": ["cosmos_knowledge_graph"],
                "knowledge_queries": [f"claims_precedents/{claim_type}"],
            }

        # For get_compliance_rules, search Cosmos
        if task_type == "get_compliance_rules":
            framework = task.get("framework", "")
            docs = store.query_by_type("compliance_rule")
            if framework:
                docs = [d for d in docs if d.get("framework") == framework]
            return {
                "found": bool(docs),
                "framework": framework,
                "rules": docs,
                "result_count": len(docs),
                "confidence": 0.9 if docs else 0.3,
                "reasoning": {"step": "get_compliance_rules", "framework": framework},
                "data_sources": ["cosmos_knowledge_graph"],
                "knowledge_queries": [f"compliance_rules/{framework}"],
            }

        # Unknown types — fall through to static handlers
        handler = {
            "get_coverage_rules": self._get_coverage_rules,
        }.get(task_type)
        if handler:
            return await handler(task)
        raise ValueError(f"Unknown knowledge task type: {task_type}")

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    async def _query(self, task: dict[str, Any]) -> dict[str, Any]:
        """Free-form knowledge graph query."""
        query = task.get("query", "")
        entity_type = task.get("entity_type")

        results: list[dict[str, Any]] = []

        # Search across all knowledge stores
        if not entity_type or entity_type == "guidelines":
            for lob, gl in UNDERWRITING_GUIDELINES.items():
                if query.lower() in str(gl).lower():
                    results.append({"type": "guideline", "lob": lob, "data": gl})

        if not entity_type or entity_type == "regulatory":
            for jur, req in REGULATORY_REQUIREMENTS.items():
                if query.lower() in str(req).lower():
                    results.append({"type": "regulatory", "jurisdiction": jur, "data": req})

        if not entity_type or entity_type == "coverage":
            for code, rule in COVERAGE_RULES.items():
                if query.lower() in str(rule).lower():
                    results.append({"type": "coverage_rule", "code": code, "data": rule})

        self.logger.info("knowledge.query", query=query, results=len(results))

        return {
            "query": query,
            "results": results,
            "result_count": len(results),
            "confidence": 0.9 if results else 0.3,
            "reasoning": {
                "step": "query",
                "query": query,
                "stores_searched": ["guidelines", "regulatory", "coverage_rules"],
            },
            "data_sources": ["knowledge_graph"],
            "knowledge_queries": [query],
        }

    # ------------------------------------------------------------------
    # Guidelines
    # ------------------------------------------------------------------

    async def _get_guidelines(self, task: dict[str, Any]) -> dict[str, Any]:
        """Retrieve underwriting guidelines for a LOB."""
        lob = task.get("line_of_business", "")
        guidelines = UNDERWRITING_GUIDELINES.get(lob)

        if guidelines is None:
            return {
                "found": False,
                "line_of_business": lob,
                "guidelines": None,
                "confidence": 0.3,
                "reasoning": {"step": "get_guidelines", "lob": lob, "found": False},
                "data_sources": ["knowledge_graph"],
                "knowledge_queries": [f"guidelines/{lob}"],
            }

        self.logger.info("knowledge.guidelines.retrieved", lob=lob)
        return {
            "found": True,
            "line_of_business": lob,
            "guidelines": guidelines,
            "confidence": 0.95,
            "reasoning": {"step": "get_guidelines", "lob": lob, "found": True},
            "data_sources": ["knowledge_graph"],
            "knowledge_queries": [f"guidelines/{lob}"],
        }

    # ------------------------------------------------------------------
    # Regulatory
    # ------------------------------------------------------------------

    async def _get_regulatory(self, task: dict[str, Any]) -> dict[str, Any]:
        """Retrieve regulatory requirements for a jurisdiction."""
        jurisdiction = task.get("jurisdiction", "")
        reqs = REGULATORY_REQUIREMENTS.get(jurisdiction)

        if reqs is None:
            return {
                "found": False,
                "jurisdiction": jurisdiction,
                "requirements": None,
                "confidence": 0.3,
                "reasoning": {
                    "step": "get_regulatory",
                    "jurisdiction": jurisdiction,
                    "found": False,
                },
                "data_sources": ["knowledge_graph"],
                "knowledge_queries": [f"regulatory/{jurisdiction}"],
            }

        self.logger.info("knowledge.regulatory.retrieved", jurisdiction=jurisdiction)
        return {
            "found": True,
            "jurisdiction": jurisdiction,
            "requirements": reqs,
            "confidence": 0.95,
            "reasoning": {
                "step": "get_regulatory",
                "jurisdiction": jurisdiction,
                "found": True,
            },
            "data_sources": ["knowledge_graph"],
            "knowledge_queries": [f"regulatory/{jurisdiction}"],
        }

    # ------------------------------------------------------------------
    # Coverage rules
    # ------------------------------------------------------------------

    async def _get_coverage_rules(self, task: dict[str, Any]) -> dict[str, Any]:
        """Retrieve coverage and exclusion rules."""
        coverage_code = task.get("coverage_code", "")
        rules = COVERAGE_RULES.get(coverage_code)

        if rules is None:
            # Return all rules if no specific code requested
            all_rules = list(COVERAGE_RULES.values()) if not coverage_code else []
            return {
                "found": bool(all_rules),
                "coverage_code": coverage_code,
                "rules": all_rules if all_rules else None,
                "confidence": 0.8 if all_rules else 0.3,
                "reasoning": {
                    "step": "get_coverage_rules",
                    "code": coverage_code,
                    "found": bool(all_rules),
                },
                "data_sources": ["knowledge_graph"],
                "knowledge_queries": [f"coverage_rules/{coverage_code}"],
            }

        self.logger.info("knowledge.coverage.retrieved", coverage_code=coverage_code)
        return {
            "found": True,
            "coverage_code": coverage_code,
            "rules": rules,
            "confidence": 0.95,
            "reasoning": {
                "step": "get_coverage_rules",
                "code": coverage_code,
                "found": True,
            },
            "data_sources": ["knowledge_graph"],
            "knowledge_queries": [f"coverage_rules/{coverage_code}"],
        }

    # ------------------------------------------------------------------
    # Claims precedents
    # ------------------------------------------------------------------

    async def _get_claims_precedents(self, task: dict[str, Any]) -> dict[str, Any]:
        """Retrieve claims precedents by claim type."""
        claim_type = task.get("claim_type", "")
        precedent = CLAIMS_PRECEDENTS.get(claim_type)

        if precedent is None:
            # Return all if no specific type
            all_precedents = list(CLAIMS_PRECEDENTS.values()) if not claim_type else []
            return {
                "found": bool(all_precedents),
                "claim_type": claim_type,
                "precedents": all_precedents,
                "result_count": len(all_precedents),
                "confidence": 0.8 if all_precedents else 0.3,
                "reasoning": {"step": "get_claims_precedents", "claim_type": claim_type},
                "data_sources": ["knowledge_graph"],
                "knowledge_queries": [f"claims_precedents/{claim_type}"],
            }

        self.logger.info("knowledge.claims_precedent.retrieved", claim_type=claim_type)
        return {
            "found": True,
            "claim_type": claim_type,
            "precedents": [precedent],
            "result_count": 1,
            "confidence": 0.95,
            "reasoning": {"step": "get_claims_precedents", "claim_type": claim_type, "found": True},
            "data_sources": ["knowledge_graph"],
            "knowledge_queries": [f"claims_precedents/{claim_type}"],
        }

    # ------------------------------------------------------------------
    # Compliance rules
    # ------------------------------------------------------------------

    async def _get_compliance_rules(self, task: dict[str, Any]) -> dict[str, Any]:
        """Retrieve compliance framework rules."""
        framework = task.get("framework", "")
        rules = COMPLIANCE_RULES.get(framework)

        if rules is None:
            all_rules = list(COMPLIANCE_RULES.values()) if not framework else []
            return {
                "found": bool(all_rules),
                "framework": framework,
                "rules": all_rules,
                "result_count": len(all_rules),
                "confidence": 0.8 if all_rules else 0.3,
                "reasoning": {"step": "get_compliance_rules", "framework": framework},
                "data_sources": ["knowledge_graph"],
                "knowledge_queries": [f"compliance_rules/{framework}"],
            }

        self.logger.info("knowledge.compliance_rule.retrieved", framework=framework)
        return {
            "found": True,
            "framework": framework,
            "rules": [rules],
            "result_count": 1,
            "confidence": 0.95,
            "reasoning": {"step": "get_compliance_rules", "framework": framework, "found": True},
            "data_sources": ["knowledge_graph"],
            "knowledge_queries": [f"compliance_rules/{framework}"],
        }

    # ------------------------------------------------------------------
    # Update (stub)
    # ------------------------------------------------------------------

    async def _update(self, task: dict[str, Any]) -> dict[str, Any]:
        """Update knowledge graph entries.

        In production this writes to Cosmos DB via the Gremlin API.
        The stub validates the payload and returns a success response.
        """
        entity_type = task.get("entity_type")
        entity_data = task.get("entity_data", {})

        if not entity_type:
            raise ValueError("entity_type is required for knowledge updates")

        self.logger.info(
            "knowledge.update",
            entity_type=entity_type,
            fields=list(entity_data.keys()),
        )

        return {
            "updated": True,
            "entity_type": entity_type,
            "fields_updated": list(entity_data.keys()),
            "confidence": 0.90,
            "reasoning": {
                "step": "update",
                "entity_type": entity_type,
            },
            "data_sources": ["knowledge_graph"],
            "knowledge_queries": [f"update/{entity_type}"],
        }
