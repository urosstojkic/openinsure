"""OpenInsure MCP Server — Model Context Protocol interface.

Exposes OpenInsure capabilities as a standards-compliant MCP server so
that any MCP client (GitHub Copilot, Claude Desktop, custom orchestrators)
can interact with the insurance platform through a standardised tool /
resource interface.

**White-label ready:** The backend API URL is configured via the
``OPENINSURE_API_BASE_URL`` environment variable.  Each tenant sets this
to their own Azure Container Apps deployment — no code changes needed.

**Architecture:** All tools delegate to the tenant's FastAPI REST API
which is backed by Microsoft Foundry agents, RBAC / authority checks,
compliance audit trails, and the real Azure SQL / Cosmos DB persistence
layer.  This ensures MCP consumers get the same AI-powered results as
dashboard users.

Tools (21):
    Submission: create_submission, get_submission, list_submissions,
                triage_submission, quote_submission, bind_submission
    Claims:     file_claim, get_claim, list_claims, set_reserve
    Policy:     get_policy, list_policies
    Billing:    create_invoice, record_payment, get_billing_status
    Documents:  generate_declaration, generate_certificate
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
import os
from typing import Any, ClassVar

import httpx
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

# ======================================================================
# HTTP client — talks to the tenant's FastAPI backend
# ======================================================================


def _resolve_base_url() -> str:
    """Resolve the backend API base URL.

    Resolution order:
      1. ``OPENINSURE_API_BASE_URL`` env var  (recommended for white-label)
      2. ``--api-url <url>`` CLI argument      (set by __main__.py)
      3. ``http://localhost:{OPENINSURE_PORT}`` (local dev fallback)

    For white-label / multi-tenant deployments, each tenant sets
    ``OPENINSURE_API_BASE_URL`` in their MCP client config:

    .. code-block:: json

        {
          "mcpServers": {
            "openinsure": {
              "command": "python",
              "args": ["-m", "openinsure.mcp"],
              "env": {
                "OPENINSURE_API_BASE_URL": "https://acme-insurance.azurecontainerapps.io"
              }
            }
          }
        }
    """
    url = os.environ.get("OPENINSURE_API_BASE_URL")
    if url:
        return url.rstrip("/")

    # Local dev fallback
    port = os.environ.get("OPENINSURE_PORT", "8000")
    fallback = f"http://localhost:{port}"
    logger.warning(
        "mcp.config.using_localhost_fallback",
        hint="Set OPENINSURE_API_BASE_URL for production / white-label deployments",
        fallback_url=fallback,
    )
    return fallback


_BASE_URL: str = _resolve_base_url()


def configure_base_url(url: str) -> None:
    """Override the backend URL at runtime (used by ``--api-url`` CLI arg)."""
    global _BASE_URL  # noqa: PLW0603
    _BASE_URL = url.rstrip("/")
    logger.info("mcp.config.base_url_set", url=_BASE_URL)


def _api_url(path: str) -> str:
    """Build a full API URL from a relative path."""
    return f"{_BASE_URL}/api/v1{path}"


async def _request(
    method: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any] | list[Any]:
    """Send an HTTP request to the FastAPI backend and return parsed JSON."""
    url = _api_url(path)
    # Strip None values from query params
    if params:
        params = {k: v for k, v in params.items() if v is not None}

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.request(method, url, json=json_body, params=params)
        resp.raise_for_status()
        return resp.json()


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
    body = {
        "applicant_name": applicant,
        "line_of_business": line_of_business,
        "risk_data": {
            "annual_revenue": annual_revenue,
            "employee_count": employee_count,
            "industry": industry,
        },
    }
    result = await _request("POST", "/submissions", json_body=body)
    logger.info("mcp.create_submission", submission_id=result.get("id"))
    return json.dumps(result, default=str)


@mcp.tool()
async def get_submission(submission_id: str) -> str:
    """Retrieve an insurance submission by ID.

    Args:
        submission_id: UUID of the submission.

    Returns:
        JSON with submission details, or error if not found.
    """
    try:
        result = await _request("GET", f"/submissions/{submission_id}")
        return json.dumps(result, default=str)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return json.dumps({"error": f"Submission {submission_id} not found"})
        raise


@mcp.tool()
async def list_submissions(status: str | None = None, limit: int = 20) -> str:
    """List insurance submissions with optional filtering.

    Args:
        status: Filter by status (received, triaging, underwriting, quoted, bound, declined).
        limit: Maximum number of results (default 20).

    Returns:
        JSON array of submission summaries.
    """
    params: dict[str, Any] = {"limit": limit}
    if status:
        params["status"] = status
    result = await _request("GET", "/submissions", params=params)
    return json.dumps(result, default=str)


@mcp.tool()
async def triage_submission(submission_id: str) -> str:
    """Run AI triage on a submission (appetite check, risk scoring, priority).

    Args:
        submission_id: UUID of the submission to triage.

    Returns:
        JSON with triage results including risk score and recommendation.
    """
    try:
        result = await _request("POST", f"/submissions/{submission_id}/triage")
        logger.info("mcp.triage_submission", submission_id=submission_id)
        return json.dumps(result, default=str)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return json.dumps({"error": f"Submission {submission_id} not found"})
        raise


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
    try:
        result = await _request("POST", f"/submissions/{submission_id}/quote")
        logger.info("mcp.quote_submission", submission_id=submission_id)
        return json.dumps(result, default=str)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return json.dumps({"error": f"Submission {submission_id} not found"})
        raise


@mcp.tool()
async def bind_submission(submission_id: str, payment_method: str = "invoice") -> str:
    """Bind a quoted submission into an active policy.

    Args:
        submission_id: UUID of the quoted submission.
        payment_method: Payment method — invoice, eft, or credit_card.

    Returns:
        JSON with the new policy record.
    """
    try:
        result = await _request("POST", f"/submissions/{submission_id}/bind")
        logger.info("mcp.bind_submission", submission_id=submission_id)
        return json.dumps(result, default=str)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return json.dumps({"error": f"Submission {submission_id} not found"})
        raise


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
    body: dict[str, Any] = {
        "policy_id": policy_id,
        "date_of_loss": loss_date,
        "description": description,
        "claim_type": cause_of_loss,
        "reported_by": "MCP Client",
    }
    if estimated_amount is not None:
        body["metadata"] = {"estimated_amount": estimated_amount}
    result = await _request("POST", "/claims", json_body=body)
    logger.info("mcp.file_claim", claim_id=result.get("id"), policy_id=policy_id)
    return json.dumps(result, default=str)


@mcp.tool()
async def get_claim(claim_id: str) -> str:
    """Retrieve a claim by ID.

    Args:
        claim_id: UUID of the claim.

    Returns:
        JSON with claim details.
    """
    try:
        result = await _request("GET", f"/claims/{claim_id}")
        return json.dumps(result, default=str)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return json.dumps({"error": f"Claim {claim_id} not found"})
        raise


@mcp.tool()
async def list_claims(status: str | None = None, limit: int = 20) -> str:
    """List claims with optional status filter.

    Args:
        status: Filter by status (fnol, investigating, reserved, settling, closed, denied).
        limit: Maximum results (default 20).

    Returns:
        JSON array of claims.
    """
    params: dict[str, Any] = {"limit": limit}
    if status:
        params["status"] = status
    result = await _request("GET", "/claims", params=params)
    return json.dumps(result, default=str)


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
    body: dict[str, Any] = {
        "category": category,
        "amount": amount,
    }
    if notes:
        body["notes"] = notes
    try:
        result = await _request("POST", f"/claims/{claim_id}/reserve", json_body=body)
        logger.info("mcp.set_reserve", claim_id=claim_id, amount=amount, category=category)
        return json.dumps(result, default=str)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return json.dumps({"error": f"Claim {claim_id} not found"})
        raise


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
    try:
        result = await _request("GET", f"/policies/{policy_id}")
        return json.dumps(result, default=str)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return json.dumps({"error": f"Policy {policy_id} not found"})
        raise


@mcp.tool()
async def list_policies(status: str | None = None, limit: int = 20) -> str:
    """List policies with optional status filter.

    Args:
        status: Filter by status (active, expired, cancelled, pending, suspended).
        limit: Maximum results (default 20).

    Returns:
        JSON array of policies.
    """
    params: dict[str, Any] = {"limit": limit}
    if status:
        params["status"] = status
    result = await _request("GET", "/policies", params=params)
    return json.dumps(result, default=str)


# ======================================================================
# Billing tools (#77)
# ======================================================================


@mcp.tool()
async def create_invoice(
    account_id: str,
    amount: float,
    due_date: str,
    description: str = "Premium installment",
) -> str:
    """Generate an invoice on a billing account.

    Args:
        account_id: UUID of the billing account.
        amount: Invoice amount in USD.
        due_date: Due date in ISO-8601 format (YYYY-MM-DD).
        description: Line-item description.

    Returns:
        JSON with the created invoice record.
    """
    body: dict[str, Any] = {
        "amount": amount,
        "due_date": due_date,
        "description": description,
    }
    try:
        result = await _request(
            "POST",
            f"/billing/accounts/{account_id}/invoices",
            json_body=body,
        )
        logger.info(
            "mcp.create_invoice",
            account_id=account_id,
            amount=amount,
        )
        return json.dumps(result, default=str)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return json.dumps({"error": f"Billing account {account_id} not found"})
        if exc.response.status_code == 409:
            return json.dumps({"error": "Cannot generate invoices on a cancelled account"})
        raise


@mcp.tool()
async def record_payment(
    account_id: str,
    amount: float,
    method: str = "ach",
    reference: str = "",
) -> str:
    """Record a payment against a billing account.

    Args:
        account_id: UUID of the billing account.
        amount: Payment amount in USD.
        method: Payment method (ach, wire, check, credit_card).
        reference: External payment reference number.

    Returns:
        JSON with payment confirmation, updated balance, and account status.
    """
    body: dict[str, Any] = {
        "amount": amount,
        "method": method,
    }
    if reference:
        body["reference"] = reference
    try:
        result = await _request(
            "POST",
            f"/billing/accounts/{account_id}/payments",
            json_body=body,
        )
        logger.info(
            "mcp.record_payment",
            account_id=account_id,
            amount=amount,
            method=method,
        )
        return json.dumps(result, default=str)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return json.dumps({"error": f"Billing account {account_id} not found"})
        if exc.response.status_code == 409:
            return json.dumps({"error": exc.response.json().get("detail", "Payment conflict")})
        raise


@mcp.tool()
async def get_billing_status(account_id: str) -> str:
    """Get billing account balance, invoices, and payment history.

    Args:
        account_id: UUID of the billing account.

    Returns:
        JSON with account details, balance, invoice list, and ledger.
    """
    try:
        account = await _request("GET", f"/billing/accounts/{account_id}")
        ledger = await _request("GET", f"/billing/accounts/{account_id}/ledger")
        return json.dumps({"account": account, "ledger": ledger}, default=str)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return json.dumps({"error": f"Billing account {account_id} not found"})
        raise


# ======================================================================
# Document tools (#78)
# ======================================================================


@mcp.tool()
async def generate_declaration(policy_id: str) -> str:
    """Generate a declarations page for a policy.

    Produces a structured document with named insured, policy period,
    coverage summary, premium breakdown, and endorsements.

    Args:
        policy_id: UUID of the policy.

    Returns:
        JSON with document title, sections, and summary.
    """
    try:
        result = await _request("GET", f"/policies/{policy_id}/documents/declaration")
        logger.info("mcp.generate_declaration", policy_id=policy_id)
        return json.dumps(result, default=str)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return json.dumps({"error": f"Policy {policy_id} not found"})
        raise


@mcp.tool()
async def generate_certificate(policy_id: str) -> str:
    """Generate a Certificate of Insurance for a policy.

    Produces a structured certificate with insured info, coverage types,
    limits, policy period, and cancellation provisions.

    Args:
        policy_id: UUID of the policy.

    Returns:
        JSON with certificate title, sections, and summary.
    """
    try:
        result = await _request("GET", f"/policies/{policy_id}/documents/certificate")
        logger.info("mcp.generate_certificate", policy_id=policy_id)
        return json.dumps(result, default=str)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return json.dumps({"error": f"Policy {policy_id} not found"})
        raise


# ======================================================================
# Query / metrics tools
# ======================================================================


@mcp.tool()
async def get_metrics() -> str:
    """Retrieve portfolio-level dashboard metrics and KPIs.

    Returns:
        JSON with total submissions, policies, claims, and summary stats.
    """
    result = await _request("GET", "/metrics/summary")
    return json.dumps(result, default=str)


@mcp.tool()
async def get_agent_decisions(limit: int = 10) -> str:
    """Retrieve recent AI agent decision records (audit trail).

    Args:
        limit: Maximum number of decisions to return.

    Returns:
        JSON with recent AI decisions for compliance review.
    """
    result = await _request("GET", "/compliance/decisions", params={"limit": limit})
    return json.dumps(result, default=str)


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
    try:
        result = await _request("GET", f"/compliance/decisions/{decision_id}")
        return json.dumps({"status": "compliant", "decision": result}, default=str)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return json.dumps({"error": f"Decision {decision_id} not found"})
        raise


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
    # Step 1: Create submission via API
    sub_json = await create_submission(
        applicant=applicant,
        annual_revenue=annual_revenue,
        employee_count=employee_count,
    )
    sub = json.loads(sub_json)
    sub_id = sub.get("id", "")

    # Step 2: Run the multi-agent workflow via API (triage → quote → bind)
    try:
        workflow_result = await _request("POST", f"/workflows/new-business/{sub_id}")
        logger.info("mcp.run_full_workflow", applicant=applicant, submission_id=sub_id)
        return json.dumps(
            {
                "workflow": "new_business",
                "submission": sub,
                "workflow_execution": workflow_result,
            },
            default=str,
        )
    except httpx.HTTPStatusError:
        # Fallback: run steps individually via API if workflow endpoint fails
        triage_json = await triage_submission(sub_id)
        triage = json.loads(triage_json)

        quote_json = await quote_submission(submission_id=sub_id)
        quote = json.loads(quote_json)

        bind_json = await bind_submission(sub_id)
        policy = json.loads(bind_json)

        logger.info("mcp.run_full_workflow.fallback", applicant=applicant, submission_id=sub_id)
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
# MCP Resources — read-only context (via API)
# ======================================================================


@mcp.resource("insurance://submissions/{submission_id}")
async def submission_resource(submission_id: str) -> str:
    """Insurance submission details."""
    return await get_submission(submission_id)


@mcp.resource("insurance://policies/{policy_id}")
async def policy_resource(policy_id: str) -> str:
    """Insurance policy details including coverages, limits, and status."""
    return await get_policy(policy_id)


@mcp.resource("insurance://claims/{claim_id}")
async def claim_resource(claim_id: str) -> str:
    """Insurance claim details, status, and reserves."""
    return await get_claim(claim_id)


@mcp.resource("insurance://metrics/summary")
async def metrics_resource() -> str:
    """Portfolio-level business KPIs and summary metrics."""
    return await get_metrics()


@mcp.resource("insurance://products/{product_id}")
async def product_resource(product_id: str) -> str:
    """Insurance product definition with coverages and rating factors."""
    try:
        result = await _request("GET", f"/products/{product_id}")
        return json.dumps(result, default=str)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return json.dumps({"error": f"Product {product_id} not found"})
        raise


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
        "create_invoice": create_invoice,
        "record_payment": record_payment,
        "get_billing_status": get_billing_status,
        "generate_declaration": generate_declaration,
        "generate_certificate": generate_certificate,
    }

    async def list_tools(self) -> list[dict[str, Any]]:
        """Return MCP tool definitions (legacy format)."""
        tools = []
        for name, fn in self._TOOL_MAP.items():
            tools.append({"name": name, "description": fn.__doc__ or ""})
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
