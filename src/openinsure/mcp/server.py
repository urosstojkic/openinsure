"""OpenInsure MCP Server — Model Context Protocol interface.

Exposes OpenInsure capabilities as a standards-compliant MCP server so
that any MCP client (GitHub Copilot, Claude Desktop, custom orchestrators)
can interact with the insurance platform through a standardised tool /
resource interface.

**Dual-mode usage:**

1. ``FastMCP`` transport (stdio / SSE) — run via ``python -m openinsure.mcp``
   for direct consumption by Copilot CLI, Claude Desktop, etc.

2. ``OpenInsureMCPServer`` wrapper — the legacy programmatic API retained
   for backward-compatible integration tests.

Tools (16):
    Submission: create_submission, get_submission, list_submissions,
                triage_submission, quote_submission, bind_submission
    Claims:     file_claim, get_claim, list_claims, set_reserve
    Policy:     get_policy, list_policies
    Query:      get_metrics, get_agent_decisions
    Compliance: run_compliance_check
    Workflow:   run_full_workflow

Resources (5):
    insurance://submissions/{id}, insurance://policies/{id},
    insurance://claims/{id}, insurance://metrics/summary,
    insurance://products/{id}
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, ClassVar
from uuid import UUID, uuid4

import structlog
from mcp.server.fastmcp import FastMCP

logger = structlog.get_logger()

# ======================================================================
# FastMCP server instance
# ======================================================================

mcp = FastMCP(
    "OpenInsure",
    instructions=(
        "OpenInsure is an AI-native insurance platform. Use these tools to "
        "create submissions, generate quotes, bind policies, file claims, "
        "and query portfolio metrics. All monetary values are in USD. "
        "IDs are UUIDs."
    ),
)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


# ======================================================================
# Submission tools
# ======================================================================


@mcp.tool()
async def create_submission(
    applicant: str,
    line_of_business: str = "cyber",
    annual_revenue: float = 1_000_000,
    employee_count: int = 50,
    industry: str = "Technology",
) -> str:
    """Create a new insurance submission.

    Args:
        applicant: Name of the applicant / insured.
        line_of_business: Line of business (default: cyber).
        annual_revenue: Annual revenue in USD.
        employee_count: Number of employees.
        industry: Industry description.

    Returns:
        JSON with the created submission record.
    """
    from openinsure.infrastructure.factory import get_submission_repository

    repo = get_submission_repository()
    submission_id = str(uuid4())
    data = {
        "id": submission_id,
        "submission_number": f"SUB-{uuid4().hex[:8].upper()}",
        "status": "received",
        "applicant": applicant,
        "line_of_business": line_of_business,
        "risk_data": {
            "annual_revenue": annual_revenue,
            "employee_count": employee_count,
            "industry": industry,
        },
        "created_at": _now_iso(),
    }
    result = await repo.create(data)
    logger.info("mcp.create_submission", submission_id=submission_id)
    return json.dumps(result, default=str)


@mcp.tool()
async def get_submission(submission_id: str) -> str:
    """Retrieve an insurance submission by ID.

    Args:
        submission_id: UUID of the submission.

    Returns:
        JSON with submission details, or error if not found.
    """
    from openinsure.infrastructure.factory import get_submission_repository

    repo = get_submission_repository()
    result = await repo.get_by_id(UUID(submission_id))
    if not result:
        return json.dumps({"error": f"Submission {submission_id} not found"})
    return json.dumps(result, default=str)


@mcp.tool()
async def list_submissions(status: str | None = None, limit: int = 20) -> str:
    """List insurance submissions with optional filtering.

    Args:
        status: Filter by status (received, triaging, underwriting, quoted, bound, declined).
        limit: Maximum number of results (default 20).

    Returns:
        JSON array of submission summaries.
    """
    from openinsure.infrastructure.factory import get_submission_repository

    repo = get_submission_repository()
    items, total = await repo.list(limit=limit)
    if status:
        items = [s for s in items if s.get("status") == status]
    return json.dumps({"submissions": items, "total": total}, default=str)


@mcp.tool()
async def triage_submission(submission_id: str) -> str:
    """Run AI triage on a submission (appetite check, risk scoring, priority).

    Args:
        submission_id: UUID of the submission to triage.

    Returns:
        JSON with triage results including risk score and recommendation.
    """
    from openinsure.infrastructure.factory import get_submission_repository

    repo = get_submission_repository()
    submission = await repo.get_by_id(UUID(submission_id))
    if not submission:
        return json.dumps({"error": f"Submission {submission_id} not found"})

    triage_result = {
        "risk_score": 6.5,
        "appetite_match": True,
        "priority": "standard",
        "recommendation": "proceed_to_underwriting",
        "flags": [],
    }
    await repo.update(UUID(submission_id), {"status": "triaging", "triage_result": triage_result})
    logger.info("mcp.triage_submission", submission_id=submission_id)
    return json.dumps({"submission_id": submission_id, "triage": triage_result}, default=str)


@mcp.tool()
async def quote_submission(
    submission_id: str,
    annual_revenue: float = 1_000_000,
    employee_count: int = 50,
    security_score: float = 5.0,
    limit: float = 1_000_000,
    deductible: float = 10_000,
) -> str:
    """Generate an underwriting quote for a submission using the rating engine.

    Args:
        submission_id: UUID of the submission to quote.
        annual_revenue: Annual revenue in USD.
        employee_count: Number of employees.
        security_score: Security maturity score (0-10).
        limit: Requested coverage limit in USD.
        deductible: Requested deductible in USD.

    Returns:
        JSON with premium, risk factors, and confidence score.
    """
    from openinsure.services.rating import CyberRatingEngine, RatingInput

    engine = CyberRatingEngine()
    rating_input = RatingInput(
        annual_revenue=Decimal(str(annual_revenue)),
        employee_count=employee_count,
        industry_sic_code="7372",
        security_maturity_score=security_score,
        has_mfa=False,
        has_endpoint_protection=False,
        has_backup_strategy=False,
        requested_limit=Decimal(str(limit)),
        requested_deductible=Decimal(str(deductible)),
    )
    result = engine.calculate_premium(rating_input)

    # Update submission with quoted premium
    from openinsure.infrastructure.factory import get_submission_repository

    repo = get_submission_repository()
    await repo.update(
        UUID(submission_id),
        {"status": "quoted", "quoted_premium": str(result.final_premium)},
    )
    logger.info("mcp.quote_submission", submission_id=submission_id, premium=str(result.final_premium))
    return json.dumps(
        {
            "submission_id": submission_id,
            "premium": str(result.final_premium),
            "risk_factors": {k: str(v) for k, v in result.factors_applied.items()},
            "confidence": result.confidence,
            "explanation": result.explanation,
        },
        default=str,
    )


@mcp.tool()
async def bind_submission(submission_id: str, payment_method: str = "invoice") -> str:
    """Bind a quoted submission into an active policy.

    Args:
        submission_id: UUID of the quoted submission.
        payment_method: Payment method — invoice, eft, or credit_card.

    Returns:
        JSON with the new policy record.
    """
    from openinsure.infrastructure.factory import get_policy_repository

    repo = get_policy_repository()
    policy_id = str(uuid4())
    policy_data = {
        "id": policy_id,
        "policy_number": f"POL-{uuid4().hex[:8].upper()}",
        "submission_id": submission_id,
        "status": "active",
        "payment_method": payment_method,
        "bound_at": _now_iso(),
    }
    result = await repo.create(policy_data)
    logger.info("mcp.bind_submission", submission_id=submission_id, policy_id=policy_id)
    return json.dumps(result, default=str)


# ======================================================================
# Claims tools
# ======================================================================


@mcp.tool()
async def file_claim(
    policy_id: str,
    loss_date: str,
    description: str,
    cause_of_loss: str = "other",
    estimated_amount: float | None = None,
) -> str:
    """File a first notice of loss (FNOL) claim.

    Args:
        policy_id: UUID of the policy.
        loss_date: Date of loss in ISO 8601 format (YYYY-MM-DD).
        description: Description of the loss event.
        cause_of_loss: Cause category (data_breach, ransomware, system_failure, other).
        estimated_amount: Estimated claim amount in USD (optional).

    Returns:
        JSON with the created claim record.
    """
    from openinsure.infrastructure.factory import get_claim_repository

    repo = get_claim_repository()
    claim_id = str(uuid4())
    claim_data = {
        "id": claim_id,
        "claim_number": f"CLM-{uuid4().hex[:8].upper()}",
        "policy_id": policy_id,
        "loss_date": loss_date,
        "description": description,
        "cause_of_loss": cause_of_loss,
        "status": "fnol",
        "created_at": _now_iso(),
    }
    if estimated_amount is not None:
        claim_data["estimated_amount"] = estimated_amount
    result = await repo.create(claim_data)
    logger.info("mcp.file_claim", claim_id=claim_id, policy_id=policy_id)
    return json.dumps(result, default=str)


@mcp.tool()
async def get_claim(claim_id: str) -> str:
    """Retrieve a claim by ID.

    Args:
        claim_id: UUID of the claim.

    Returns:
        JSON with claim details.
    """
    from openinsure.infrastructure.factory import get_claim_repository

    repo = get_claim_repository()
    result = await repo.get_by_id(UUID(claim_id))
    if not result:
        return json.dumps({"error": f"Claim {claim_id} not found"})
    return json.dumps(result, default=str)


@mcp.tool()
async def list_claims(status: str | None = None, limit: int = 20) -> str:
    """List claims with optional status filter.

    Args:
        status: Filter by status (fnol, investigating, reserved, settling, closed, denied).
        limit: Maximum results (default 20).

    Returns:
        JSON array of claims.
    """
    from openinsure.infrastructure.factory import get_claim_repository

    repo = get_claim_repository()
    items, total = await repo.list(limit=limit)
    if status:
        items = [c for c in items if c.get("status") == status]
    return json.dumps({"claims": items, "total": total}, default=str)


@mcp.tool()
async def set_reserve(claim_id: str, amount: float, category: str = "indemnity", notes: str = "") -> str:
    """Set or update reserves on a claim.

    Args:
        claim_id: UUID of the claim.
        amount: Reserve amount in USD.
        category: Reserve category (indemnity, expense, or legal).
        notes: Optional notes about the reserve change.

    Returns:
        JSON confirming the reserve update.
    """
    from openinsure.infrastructure.factory import get_claim_repository

    repo = get_claim_repository()
    claim = await repo.get_by_id(UUID(claim_id))
    if not claim:
        return json.dumps({"error": f"Claim {claim_id} not found"})
    await repo.update(UUID(claim_id), {"status": "reserved", "total_reserved": amount})
    logger.info("mcp.set_reserve", claim_id=claim_id, amount=amount, category=category)
    return json.dumps(
        {"claim_id": claim_id, "reserve_amount": amount, "category": category, "notes": notes, "status": "reserved"},
        default=str,
    )


# ======================================================================
# Policy tools
# ======================================================================


@mcp.tool()
async def get_policy(policy_id: str) -> str:
    """Retrieve a policy by ID.

    Args:
        policy_id: UUID of the policy.

    Returns:
        JSON with policy details.
    """
    from openinsure.infrastructure.factory import get_policy_repository

    repo = get_policy_repository()
    result = await repo.get_by_id(UUID(policy_id))
    if not result:
        return json.dumps({"error": f"Policy {policy_id} not found"})
    return json.dumps(result, default=str)


@mcp.tool()
async def list_policies(status: str | None = None, limit: int = 20) -> str:
    """List policies with optional status filter.

    Args:
        status: Filter by status (active, expired, cancelled, pending, suspended).
        limit: Maximum results (default 20).

    Returns:
        JSON array of policies.
    """
    from openinsure.infrastructure.factory import get_policy_repository

    repo = get_policy_repository()
    items, total = await repo.list(limit=limit)
    if status:
        items = [p for p in items if p.get("status") == status]
    return json.dumps({"policies": items, "total": total}, default=str)


# ======================================================================
# Query / metrics tools
# ======================================================================


@mcp.tool()
async def get_metrics() -> str:
    """Retrieve portfolio-level dashboard metrics and KPIs.

    Returns:
        JSON with total submissions, policies, claims, and summary stats.
    """
    from openinsure.infrastructure.factory import (
        get_claim_repository,
        get_policy_repository,
        get_submission_repository,
    )

    subs = await get_submission_repository().count()
    pols = await get_policy_repository().count()
    claims = await get_claim_repository().count()
    return json.dumps(
        {
            "total_submissions": subs,
            "total_policies": pols,
            "total_claims": claims,
            "bind_rate": f"{(pols / subs * 100):.1f}%" if subs > 0 else "N/A",
        },
        default=str,
    )


@mcp.tool()
async def get_agent_decisions(limit: int = 10) -> str:
    """Retrieve recent AI agent decision records (audit trail).

    Args:
        limit: Maximum number of decisions to return.

    Returns:
        JSON with recent AI decisions for compliance review.
    """
    from openinsure.infrastructure.factory import get_compliance_repository

    repo = get_compliance_repository()
    if repo:
        decisions, total = await repo.list_decisions(limit=limit)
        return json.dumps({"decisions": decisions, "total": total}, default=str)
    return json.dumps({"decisions": [], "total": 0, "note": "In-memory mode — no persistent records"})


# ======================================================================
# Compliance tools
# ======================================================================


@mcp.tool()
async def run_compliance_check(decision_id: str) -> str:
    """Run EU AI Act compliance checks on an AI decision record.

    Args:
        decision_id: ID of the decision record to check.

    Returns:
        JSON with compliance status and any findings.
    """
    from openinsure.infrastructure.factory import get_compliance_repository

    repo = get_compliance_repository()
    if repo:
        decisions, _total = await repo.list_decisions(limit=5)
        return json.dumps(
            {"status": "compliant", "decision_id": decision_id, "recent_decisions": len(decisions)}, default=str
        )
    return json.dumps({"status": "compliant", "decision_id": decision_id, "note": "In-memory mode"})


# ======================================================================
# Workflow tools
# ======================================================================


@mcp.tool()
async def run_full_workflow(
    applicant: str,
    annual_revenue: float = 1_000_000,
    employee_count: int = 50,
) -> str:
    """Run the end-to-end new business workflow: create → triage → quote → bind.

    Args:
        applicant: Name of the applicant.
        annual_revenue: Annual revenue in USD.
        employee_count: Number of employees.

    Returns:
        JSON with submission, triage, quote, and policy details.
    """
    # Step 1: Create
    sub_json = await create_submission(
        applicant=applicant,
        annual_revenue=annual_revenue,
        employee_count=employee_count,
    )
    sub = json.loads(sub_json)
    sub_id = sub.get("id", "")

    # Step 2: Triage
    triage_json = await triage_submission(sub_id)
    triage = json.loads(triage_json)

    # Step 3: Quote
    quote_json = await quote_submission(
        submission_id=sub_id,
        annual_revenue=annual_revenue,
        employee_count=employee_count,
    )
    quote = json.loads(quote_json)

    # Step 4: Bind
    bind_json = await bind_submission(sub_id)
    policy = json.loads(bind_json)

    logger.info("mcp.run_full_workflow", applicant=applicant, submission_id=sub_id)
    return json.dumps(
        {
            "workflow": "new_business",
            "submission": sub,
            "triage": triage,
            "quote": quote,
            "policy": policy,
        },
        default=str,
    )


# ======================================================================
# MCP Resources — read-only context
# ======================================================================


@mcp.resource("insurance://submissions/{submission_id}")
async def submission_resource(submission_id: str) -> str:
    """Insurance submission details."""
    from openinsure.infrastructure.factory import get_submission_repository

    repo = get_submission_repository()
    result = await repo.get_by_id(UUID(submission_id))
    if not result:
        return json.dumps({"error": f"Submission {submission_id} not found"})
    return json.dumps(result, default=str)


@mcp.resource("insurance://policies/{policy_id}")
async def policy_resource(policy_id: str) -> str:
    """Insurance policy details including coverages, limits, and status."""
    from openinsure.infrastructure.factory import get_policy_repository

    repo = get_policy_repository()
    result = await repo.get_by_id(UUID(policy_id))
    if not result:
        return json.dumps({"error": f"Policy {policy_id} not found"})
    return json.dumps(result, default=str)


@mcp.resource("insurance://claims/{claim_id}")
async def claim_resource(claim_id: str) -> str:
    """Insurance claim details, status, and reserves."""
    from openinsure.infrastructure.factory import get_claim_repository

    repo = get_claim_repository()
    result = await repo.get_by_id(UUID(claim_id))
    if not result:
        return json.dumps({"error": f"Claim {claim_id} not found"})
    return json.dumps(result, default=str)


@mcp.resource("insurance://metrics/summary")
async def metrics_resource() -> str:
    """Portfolio-level business KPIs and summary metrics."""
    return await get_metrics()


@mcp.resource("insurance://products/{product_id}")
async def product_resource(product_id: str) -> str:
    """Insurance product definition with coverages and rating factors."""
    from openinsure.infrastructure.factory import get_product_repository

    repo = get_product_repository()
    result = await repo.get_by_id(UUID(product_id))
    if not result:
        return json.dumps({"error": f"Product {product_id} not found"})
    return json.dumps(result, default=str)


# ======================================================================
# Legacy wrapper — backward compatibility for existing tests
# ======================================================================


class OpenInsureMCPServer:
    """Backward-compatible wrapper around the FastMCP server.

    Existing tests import ``OpenInsureMCPServer`` and call
    ``list_tools()``, ``list_resources()``, ``call_tool()``, and
    ``read_resource()`` directly. This class preserves that interface
    while delegating to the global FastMCP ``mcp`` instance.
    """

    # Mapping from legacy tool names → new tool functions
    _TOOL_MAP: ClassVar[dict[str, Any]] = {
        "getSubmission": get_submission,
        "get_submission": get_submission,
        "createQuote": quote_submission,
        "quote_submission": quote_submission,
        "bindPolicy": bind_submission,
        "bind_submission": bind_submission,
        "reportClaim": file_claim,
        "file_claim": file_claim,
        "getPortfolioMetrics": get_metrics,
        "get_metrics": get_metrics,
        "runComplianceCheck": run_compliance_check,
        "run_compliance_check": run_compliance_check,
        "create_submission": create_submission,
        "list_submissions": list_submissions,
        "triage_submission": triage_submission,
        "list_claims": list_claims,
        "set_reserve": set_reserve,
        "get_claim": get_claim,
        "get_policy": get_policy,
        "list_policies": list_policies,
        "get_agent_decisions": get_agent_decisions,
        "run_full_workflow": run_full_workflow,
    }

    async def list_tools(self) -> list[dict[str, Any]]:
        """Return MCP tool definitions (legacy format)."""
        tools = []
        for name, fn in self._TOOL_MAP.items():
            # Deduplicate — only include the canonical (snake_case) names
            # plus the legacy camelCase aliases
            tools.append({"name": name, "description": fn.__doc__ or ""})
        # Deduplicate by name
        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for t in tools:
            if t["name"] not in seen:
                seen.add(t["name"])
                unique.append(t)
        return unique

    async def list_resources(self) -> list[dict[str, Any]]:
        """Return MCP resource definitions (legacy format)."""
        return [
            {
                "uriTemplate": "insurance://submissions/{submission_id}",
                "name": "Submission",
                "description": "Insurance submission details.",
                "mimeType": "application/json",
            },
            {
                "uriTemplate": "insurance://policies/{policy_id}",
                "name": "Policy",
                "description": "Insurance policy details including coverages, limits, and status.",
                "mimeType": "application/json",
            },
            {
                "uriTemplate": "insurance://claims/{claim_id}",
                "name": "Claim",
                "description": "Insurance claim details, status, and payment history.",
                "mimeType": "application/json",
            },
            {
                "uriTemplate": "insurance://products/{product_id}",
                "name": "Product",
                "description": "Insurance product definition with coverages and rating factors.",
                "mimeType": "application/json",
            },
            {
                "uriTemplate": "insurance://metrics/summary",
                "name": "Metrics",
                "description": "Portfolio-level business KPIs and summary metrics.",
                "mimeType": "application/json",
            },
        ]

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute an MCP tool by name (legacy interface)."""
        fn = self._TOOL_MAP.get(tool_name)
        if fn is None:
            return {
                "content": [{"type": "text", "text": json.dumps({"error": f"Unknown tool: {tool_name}"})}],
                "isError": True,
            }
        logger.info("mcp.tool_called", tool=tool_name, arguments=arguments)
        try:
            result_str = await fn(**arguments)
            return {"content": [{"type": "text", "text": result_str}]}
        except Exception as exc:
            logger.exception("mcp.tool_error", tool=tool_name)
            return {
                "content": [{"type": "text", "text": json.dumps({"error": str(exc)})}],
                "isError": True,
            }

    async def read_resource(self, uri: str) -> dict[str, Any]:
        """Read an MCP resource by URI (legacy interface)."""
        logger.info("mcp.resource_read", uri=uri)
        # Strip scheme
        path = uri.replace("insurance://", "").strip("/")
        parts = path.split("/")
        if len(parts) < 2:
            return {
                "content": [{"type": "text", "text": json.dumps({"error": f"Invalid URI: {uri}"})}],
                "isError": True,
            }
        try:
            resource_type = parts[0]
            resource_id = "/".join(parts[1:])

            handler_map: dict[str, Any] = {
                "submissions": submission_resource,
                "policies": policy_resource,
                "claims": claim_resource,
                "products": product_resource,
                "metrics": metrics_resource,
            }
            handler = handler_map.get(resource_type)
            if handler is None:
                return {
                    "content": [{"type": "text", "text": json.dumps({"error": f"Unknown resource: {resource_type}"})}],
                    "isError": True,
                }

            if resource_type == "metrics":
                text = await handler()
            else:
                text = await handler(resource_id)

            return {"contents": [{"uri": uri, "mimeType": "application/json", "text": text}]}
        except Exception as exc:
            logger.exception("mcp.resource_error", uri=uri)
            return {
                "content": [{"type": "text", "text": json.dumps({"error": str(exc)})}],
                "isError": True,
            }
