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
    # Tool handlers (stubs — wire to real services in production)
    # ------------------------------------------------------------------

    async def _handle_getSubmission(self, args: dict[str, Any]) -> dict[str, Any]:
        return {
            "submissionId": args["submissionId"],
            "status": "received",
            "receivedAt": _now_iso(),
            "applicant": {"name": "Acme Corp", "industry": "Technology"},
            "requestedCoverages": ["BREACH-RESP", "THIRD-PARTY"],
        }

    async def _handle_createQuote(self, args: dict[str, Any]) -> dict[str, Any]:
        return {
            "quoteId": str(uuid4()),
            "submissionId": args["submissionId"],
            "status": "quoted",
            "premium": 12500.00,
            "currency": "USD",
            "coverages": args.get("coverages", ["BREACH-RESP", "THIRD-PARTY"]),
            "effectiveDate": args.get("effectiveDate", "2025-01-01"),
            "expirationDate": "2026-01-01",
            "createdAt": _now_iso(),
        }

    async def _handle_bindPolicy(self, args: dict[str, Any]) -> dict[str, Any]:
        return {
            "policyId": f"POL-{uuid4().hex[:8].upper()}",
            "quoteId": args["quoteId"],
            "status": "bound",
            "paymentMethod": args.get("paymentMethod", "invoice"),
            "boundAt": _now_iso(),
        }

    async def _handle_reportClaim(self, args: dict[str, Any]) -> dict[str, Any]:
        return {
            "claimId": f"CLM-{uuid4().hex[:8].upper()}",
            "policyId": args["policyId"],
            "status": "fnol_received",
            "lossDate": args["lossDate"],
            "description": args["description"],
            "estimatedAmount": args.get("estimatedAmount"),
            "reportedAt": _now_iso(),
        }

    async def _handle_getPortfolioMetrics(self, args: dict[str, Any]) -> dict[str, Any]:
        return {
            "asOfDate": args.get("asOfDate", _now_iso()[:10]),
            "lineOfBusiness": args.get("lineOfBusiness", "all"),
            "metrics": {
                "grossWrittenPremium": 15_400_000,
                "lossRatio": 0.62,
                "combinedRatio": 0.94,
                "policiesInForce": 1247,
                "openClaims": 83,
                "averagePremium": 12_350,
            },
        }

    async def _handle_runComplianceCheck(self, args: dict[str, Any]) -> dict[str, Any]:
        checks = args.get(
            "checks",
            [
                "decision_record_exists",
                "human_oversight_recorded",
                "bias_check_passed",
                "explanation_available",
            ],
        )
        return {
            "decisionId": args["decisionId"],
            "checkedAt": _now_iso(),
            "results": {check: {"status": "pass", "detail": f"{check} verified"} for check in checks},
            "overallStatus": "compliant",
        }

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
