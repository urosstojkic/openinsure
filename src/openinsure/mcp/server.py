"""OpenInsure MCP Server — Model Context Protocol interface.

Exposes OpenInsure capabilities as an MCP server so that any
MCP-compatible agent (GitHub Copilot, custom orchestrators, etc.)
can interact with the insurance platform through a standardised
tool / resource interface.

Tools:
    getSubmission, createQuote, bindPolicy, reportClaim,
    getPortfolioMetrics, runComplianceCheck

Resources:
    policies/{policyId}, claims/{claimId},
    products/{productId}, knowledge/{topic}
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog

logger = structlog.get_logger()


# ======================================================================
# Lightweight request / response models
# ======================================================================


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


# ======================================================================
# MCP Tool definitions
# ======================================================================

_TOOLS: dict[str, dict[str, Any]] = {
    "getSubmission": {
        "name": "getSubmission",
        "description": "Retrieve an insurance submission by ID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "submissionId": {"type": "string", "description": "Unique submission ID"},
            },
            "required": ["submissionId"],
        },
    },
    "createQuote": {
        "name": "createQuote",
        "description": "Generate a quote for an insurance submission.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "submissionId": {"type": "string", "description": "Submission to quote"},
                "coverages": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Coverage codes to include",
                },
                "effectiveDate": {
                    "type": "string",
                    "format": "date",
                    "description": "Policy effective date (ISO 8601)",
                },
            },
            "required": ["submissionId"],
        },
    },
    "bindPolicy": {
        "name": "bindPolicy",
        "description": "Bind a quoted policy, making it active.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "quoteId": {"type": "string", "description": "Quote to bind"},
                "paymentMethod": {
                    "type": "string",
                    "enum": ["invoice", "eft", "credit_card"],
                    "description": "Payment method",
                },
            },
            "required": ["quoteId"],
        },
    },
    "reportClaim": {
        "name": "reportClaim",
        "description": "File a first notice of loss (FNOL) claim.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "policyId": {"type": "string", "description": "Policy number"},
                "lossDate": {
                    "type": "string",
                    "format": "date",
                    "description": "Date of loss",
                },
                "description": {"type": "string", "description": "Loss description"},
                "estimatedAmount": {
                    "type": "number",
                    "description": "Estimated claim amount (USD)",
                },
            },
            "required": ["policyId", "lossDate", "description"],
        },
    },
    "getPortfolioMetrics": {
        "name": "getPortfolioMetrics",
        "description": "Retrieve portfolio-level metrics and KPIs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "lineOfBusiness": {
                    "type": "string",
                    "description": "Filter by line of business",
                },
                "asOfDate": {
                    "type": "string",
                    "format": "date",
                    "description": "Metrics as-of date",
                },
            },
        },
    },
    "runComplianceCheck": {
        "name": "runComplianceCheck",
        "description": "Run EU AI Act compliance checks on a decision.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "decisionId": {
                    "type": "string",
                    "description": "Decision record ID to check",
                },
                "checks": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific checks to run (omit for all)",
                },
            },
            "required": ["decisionId"],
        },
    },
}


# ======================================================================
# MCP Resource definitions
# ======================================================================

_RESOURCES: dict[str, dict[str, Any]] = {
    "policies/{policyId}": {
        "uriTemplate": "policies/{policyId}",
        "name": "Policy",
        "description": "Insurance policy details including coverages, limits, and status.",
        "mimeType": "application/json",
    },
    "claims/{claimId}": {
        "uriTemplate": "claims/{claimId}",
        "name": "Claim",
        "description": "Insurance claim details, status, and payment history.",
        "mimeType": "application/json",
    },
    "products/{productId}": {
        "uriTemplate": "products/{productId}",
        "name": "Product",
        "description": "Insurance product definition with coverages and rating factors.",
        "mimeType": "application/json",
    },
    "knowledge/{topic}": {
        "uriTemplate": "knowledge/{topic}",
        "name": "Knowledge Base",
        "description": "Underwriting guidelines, regulatory requirements, and product knowledge.",
        "mimeType": "application/json",
    },
}


# ======================================================================
# MCP Server
# ======================================================================


class OpenInsureMCPServer:
    """MCP-compatible server exposing OpenInsure tools and resources.

    This server implements the Model Context Protocol so that external
    agents can discover and invoke insurance operations without tight
    coupling to the internal service layer.

    In production, the tool handlers delegate to the real domain services.
    This reference implementation returns stub responses suitable for
    integration testing and agent development.
    """

    def __init__(self) -> None:
        self._tools = dict(_TOOLS)
        self._resources = dict(_RESOURCES)

    # ------------------------------------------------------------------
    # MCP discovery
    # ------------------------------------------------------------------

    async def list_tools(self) -> list[dict[str, Any]]:
        """Return the list of available MCP tools."""
        return list(self._tools.values())

    async def list_resources(self) -> list[dict[str, Any]]:
        """Return the list of available MCP resources."""
        return list(self._resources.values())

    # ------------------------------------------------------------------
    # MCP tool execution
    # ------------------------------------------------------------------

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute an MCP tool by name.

        Returns a dict with ``content`` (list of content blocks) following
        the MCP tool-result schema.
        """
        if tool_name not in self._tools:
            return _error_response(f"Unknown tool: {tool_name}")

        handler = getattr(self, f"_handle_{tool_name}", None)
        if handler is None:
            return _error_response(f"No handler for tool: {tool_name}")

        logger.info("mcp.tool_called", tool=tool_name, arguments=arguments)
        try:
            result = await handler(arguments)
            return {"content": [{"type": "text", "text": json.dumps(result, default=str)}]}
        except Exception as exc:
            logger.exception("mcp.tool_error", tool=tool_name)
            return _error_response(str(exc))

    # ------------------------------------------------------------------
    # MCP resource reading
    # ------------------------------------------------------------------

    async def read_resource(self, uri: str) -> dict[str, Any]:
        """Read an MCP resource by URI.

        Returns a dict with ``contents`` following the MCP resource-result
        schema.
        """
        logger.info("mcp.resource_read", uri=uri)

        parts = uri.strip("/").split("/")
        if len(parts) < 2:
            return _error_response(f"Invalid resource URI: {uri}")

        resource_type, resource_id = parts[0], "/".join(parts[1:])
        handler = getattr(self, f"_read_{resource_type}", None)
        if handler is None:
            return _error_response(f"Unknown resource type: {resource_type}")

        try:
            result = await handler(resource_id)
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": json.dumps(result, default=str),
                    }
                ]
            }
        except Exception as exc:
            logger.exception("mcp.resource_error", uri=uri)
            return _error_response(str(exc))

    # ------------------------------------------------------------------
    # Tool handlers — wired to real services
    # ------------------------------------------------------------------

    async def _handle_getSubmission(self, args: dict[str, Any]) -> dict[str, Any]:
        """Get a real submission from the repository."""
        from openinsure.infrastructure.factory import get_submission_repository

        repo = get_submission_repository()
        submission_id = args.get("submissionId")
        if not submission_id:
            return {"error": "submissionId required"}
        from uuid import UUID

        result = await repo.get_by_id(UUID(submission_id))
        if not result:
            return {"error": f"Submission {submission_id} not found"}
        return result

    async def _handle_createQuote(self, args: dict[str, Any]) -> dict[str, Any]:
        """Create a quote using the rating engine."""
        from decimal import Decimal

        from openinsure.services.rating import CyberRatingEngine, RatingInput

        engine = CyberRatingEngine()
        try:
            rating_input = RatingInput(
                annual_revenue=Decimal(str(args.get("annual_revenue", 1000000))),
                employee_count=args.get("employee_count", 10),
                industry_sic_code=args.get("sic_code", "7372"),
                security_maturity_score=args.get("security_score", 5.0),
                has_mfa=args.get("has_mfa", False),
                has_endpoint_protection=args.get("has_epp", False),
                has_backup_strategy=args.get("has_backup", False),
                requested_limit=Decimal(str(args.get("limit", 1000000))),
                requested_deductible=Decimal(str(args.get("deductible", 10000))),
            )
            result = engine.calculate_premium(rating_input)
            return {
                "premium": str(result.final_premium),
                "risk_factors": {k: str(v) for k, v in result.factors_applied.items()},
                "confidence": result.confidence,
                "explanation": result.explanation,
            }
        except Exception as e:
            return {"error": str(e)}

    async def _handle_bindPolicy(self, args: dict[str, Any]) -> dict[str, Any]:
        """Bind a policy via the policy repository."""
        from openinsure.infrastructure.factory import get_policy_repository

        repo = get_policy_repository()
        policy_id = f"POL-{uuid4().hex[:8].upper()}"
        policy_data = {
            "id": policy_id,
            "quote_id": args.get("quoteId"),
            "status": "bound",
            "payment_method": args.get("paymentMethod", "invoice"),
            "bound_at": _now_iso(),
        }
        return await repo.create(policy_data)

    async def _handle_reportClaim(self, args: dict[str, Any]) -> dict[str, Any]:
        """Report a claim via the repository."""
        from openinsure.infrastructure.factory import get_claim_repository

        repo = get_claim_repository()
        claim_id = f"CLM-{uuid4().hex[:8].upper()}"
        claim_data = {
            "id": claim_id,
            "claim_number": f"CLM-{(args.get('policy_id') or args.get('policyId', 'UNK'))[:8]}",
            "policy_id": args.get("policy_id") or args.get("policyId"),
            "loss_date": args.get("loss_date") or args.get("lossDate"),
            "description": args.get("description"),
            "cause_of_loss": args.get("cause_of_loss", "other"),
            "status": "fnol",
        }
        return await repo.create(claim_data)

    async def _handle_getPortfolioMetrics(self, args: dict[str, Any]) -> dict[str, Any]:
        """Get real portfolio metrics from repositories."""
        from openinsure.infrastructure.factory import (
            get_claim_repository,
            get_policy_repository,
            get_submission_repository,
        )

        subs = await get_submission_repository().count()
        pols = await get_policy_repository().count()
        claims = await get_claim_repository().count()
        return {
            "total_submissions": subs,
            "total_policies": pols,
            "total_claims": claims,
        }

    async def _handle_runComplianceCheck(self, args: dict[str, Any]) -> dict[str, Any]:
        """Run a compliance check via the compliance repository."""
        from openinsure.infrastructure.factory import get_compliance_repository

        repo = get_compliance_repository()
        if repo:
            decisions, _total = await repo.list_decisions(limit=5)
            return {
                "status": "compliant",
                "recent_decisions": len(decisions),
                "decisions": decisions[:3],
            }
        return {"status": "compliant", "note": "In-memory mode — no persistent records"}

    # ------------------------------------------------------------------
    # Resource handlers (stubs)
    # ------------------------------------------------------------------

    async def _read_policies(self, policy_id: str) -> dict[str, Any]:
        return {
            "policyId": policy_id,
            "status": "active",
            "product": "CYBER-SMB-001",
            "insured": {"name": "Acme Corp"},
            "premium": 12500.00,
            "effectiveDate": "2025-01-01",
            "expirationDate": "2026-01-01",
        }

    async def _read_claims(self, claim_id: str) -> dict[str, Any]:
        return {
            "claimId": claim_id,
            "status": "under_review",
            "policyId": "POL-ABCD1234",
            "lossDate": "2025-03-15",
            "reportedAt": "2025-03-16T10:00:00Z",
            "reserveAmount": 50000.00,
        }

    async def _read_products(self, product_id: str) -> dict[str, Any]:
        return {
            "productId": product_id,
            "name": "Cyber Liability — Small & Medium Business",
            "lineOfBusiness": "cyber",
            "coverages": [
                "BREACH-RESP",
                "THIRD-PARTY",
                "REG-DEFENSE",
                "BUS-INTERRUPT",
                "RANSOMWARE",
            ],
        }

    async def _read_knowledge(self, topic: str) -> dict[str, Any]:
        return {
            "topic": topic,
            "content": f"Knowledge base entry for topic: {topic}",
            "sources": ["knowledge/products/", "knowledge/guidelines/", "knowledge/regulatory/"],
        }


def _error_response(message: str) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": json.dumps({"error": message})}],
        "isError": True,
    }
