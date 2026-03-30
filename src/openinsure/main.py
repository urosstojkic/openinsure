"""OpenInsure — AI-Native Insurance Platform API."""

import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

import pyodbc
import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from openinsure.api.errors import make_error
from openinsure.api.router import api_router
from openinsure.config import get_settings
from openinsure.domain.exceptions import DomainError
from openinsure.infrastructure.repository import IntegrityConstraintError
from openinsure.logging import redact_pii_processor
from openinsure.rate_limit import limiter

# Configure structlog with PII redaction processor
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        redact_pii_processor,
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

openapi_tags = [
    {"name": "submissions", "description": "Insurance submission intake and processing pipeline"},
    {"name": "policies", "description": "Policy administration — bind, endorse, renew, cancel"},
    {"name": "claims", "description": "Claims management — FNOL, reserves, payments, closure"},
    {"name": "billing", "description": "Billing accounts, invoices, and payment recording"},
    {"name": "compliance", "description": "AI decision audit, bias monitoring, EU AI Act compliance"},
    {"name": "knowledge", "description": "Insurance knowledge graph — guidelines, rules, precedents"},
    {"name": "reinsurance", "description": "Reinsurance treaties, cessions, recoveries (carrier-only)"},
    {"name": "actuarial", "description": "Reserves, loss triangles, IBNR, rate adequacy (carrier-only)"},
    {"name": "renewals", "description": "Policy renewal identification, terms generation, processing"},
    {"name": "mga-oversight", "description": "MGA authority tracking, bordereaux, compliance (carrier-only)"},
    {"name": "finance", "description": "Financial summary, cash flow, commissions, reconciliation"},
    {"name": "analytics", "description": "Underwriting, claims, and AI-powered portfolio analytics"},
    {"name": "demo", "description": "Live demo endpoints for showcasing the full platform"},
    {"name": "health", "description": "Health and readiness probes"},
]


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        logger.info("openinsure.startup", version=settings.app_version)
        logger.info("openinsure.storage_mode", mode=settings.storage_mode)

        # Auto-apply SQL migrations on startup when Azure SQL is configured
        if settings.storage_mode == "azure" and settings.sql_connection_string:
            try:
                from openinsure.infrastructure.auto_migrate import apply_pending_migrations

                applied = await apply_pending_migrations()
                if applied:
                    logger.info("openinsure.migrations", applied=applied)
                    print(f"[MIGRATIONS] Applied: {applied}", flush=True)
                else:
                    logger.info("openinsure.migrations", status="up-to-date")
                    print("[MIGRATIONS] All up-to-date", flush=True)
            except Exception as exc:
                logger.warning("openinsure.migrations.failed", error=str(exc))
                import traceback

                print(f"[MIGRATIONS] FAILED: {exc}", flush=True)
                traceback.print_exc()

        # Seed sample data only in debug / local-dev mode with in-memory storage
        if settings.debug and settings.storage_mode == "memory":
            from openinsure.infrastructure.seed_data import seed_sample_data

            await seed_sample_data()
            logger.info("openinsure.seed_data", status="loaded")

        # Always populate the in-memory escalation queue from existing repo data,
        # since it isn't persisted across restarts regardless of storage mode.
        from openinsure.services.escalation import _escalation_queue

        if not _escalation_queue:
            try:
                from openinsure.infrastructure.factory import get_submission_repository
                from openinsure.infrastructure.seed_data import (
                    _rng,
                    _sample_decision_records,
                    _sample_escalations,
                )

                _sub_repo = get_submission_repository()
                _subs = await _sub_repo.list_all(limit=5000)
                if _subs:
                    _rng.seed(42)
                    _decs = _sample_decision_records(_subs)
                    _escs = _sample_escalations(_subs, _decs)
                    _escalation_queue.extend(_escs)
                    logger.info("openinsure.escalations.seeded", count=len(_escs))
            except Exception:
                logger.warning("openinsure.escalations.seed_failed", exc_info=True)

        yield

        logger.info("openinsure.shutdown")

    app = FastAPI(
        title="OpenInsure API",
        description=(
            "AI-native open-source core insurance platform. Agents-first architecture for cyber insurance operations."
        ),
        version=settings.app_version,
        openapi_tags=openapi_tags,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Rate limiting — configured via settings
    limiter.default_limits = [f"{settings.rate_limit_per_minute}/minute"]
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # CORS middleware — environment-aware origin list (no wildcard)
    allowed_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
    if settings.debug:
        allowed_origins.append("http://localhost:8000")
    # In production, the dashboard URL would be set via OPENINSURE_CORS_ORIGINS env var
    if hasattr(settings, "cors_origins") and settings.cors_origins:
        allowed_origins.extend(settings.cors_origins.split(","))

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Rate-limiting middleware (must be added after CORS so CORS headers are included in 429 responses)
    from slowapi.middleware import SlowAPIMiddleware

    app.add_middleware(SlowAPIMiddleware)

    # -- Constraint-violation handlers (issues #162, #163) -------------------

    # Map constraint names to user-friendly messages
    constraint_messages: dict[str, str] = {
        # CHECK constraints (issue #162 → 422)
        "CK_policies_dates": "Effective date must be on or before expiration date",
        "CK_treaties_dates": "Effective date must be on or before expiration date",
        "CK_policies_premium": "Total premium must not be negative",
        "CK_reserves_amount": "Reserve amount must not be negative",
        "CK_payments_amount": "Payment amount must not be negative",
        "CK_invoices_amount": "Invoice amount must not be negative",
        "CK_submissions_premium": "Quoted premium must not be negative",
        "CK_products_version": "Product version must be at least 1",
        # UNIQUE constraints (issue #163 → 409)
        "UQ_policies_active_insured_product": "Active policy already exists for this insured and product",
        "UQ_billing_policy": "A billing account already exists for this policy",
        "UQ_renewal_active": "An active renewal already exists for this policy",
    }

    def _parse_constraint_name(error_msg: str) -> str | None:
        """Extract constraint name from a pyodbc IntegrityError message."""
        match = re.search(r"constraint ['\"]?(\w+)['\"]?", error_msg, re.IGNORECASE)
        if match:
            return match.group(1)
        # Unique index violations use different wording
        match = re.search(r"index ['\"]?(\w+)['\"]?", error_msg, re.IGNORECASE)
        return match.group(1) if match else None

    @app.exception_handler(pyodbc.IntegrityError)
    async def _integrity_error_handler(request: Request, exc: pyodbc.IntegrityError) -> JSONResponse:
        request_id = str(uuid4())
        error_msg = str(exc)
        constraint = _parse_constraint_name(error_msg)
        friendly = constraint_messages.get(constraint or "", "")

        logger.warning(
            "constraint_violation",
            path=request.url.path,
            constraint=constraint,
            request_id=request_id,
        )

        # CHECK constraint violations → 422; UNIQUE violations → 409
        is_unique = constraint and constraint.startswith("UQ_")
        is_check = constraint and constraint.startswith("CK_")

        if is_unique:
            return JSONResponse(
                status_code=409,
                content=make_error(
                    error=friendly or "Duplicate record violates uniqueness constraint",
                    code="CONFLICT",
                    request_id=request_id,
                    reason=constraint,
                ),
            )
        if is_check:
            return JSONResponse(
                status_code=422,
                content=make_error(
                    error=friendly or "Value violates a business validation rule",
                    code="VALIDATION_ERROR",
                    request_id=request_id,
                    reason=constraint,
                ),
            )
        # Fallback for other integrity errors (FK violations, etc.)
        return JSONResponse(
            status_code=422,
            content=make_error(
                error=friendly or "Data integrity constraint violated",
                code="INTEGRITY_ERROR",
                request_id=request_id,
                reason=constraint,
            ),
        )

    @app.exception_handler(IntegrityConstraintError)
    async def _fk_restrict_handler(request: Request, exc: IntegrityConstraintError) -> JSONResponse:
        request_id = str(uuid4())
        logger.warning(
            "delete_blocked_by_fk",
            path=request.url.path,
            detail=str(exc),
            request_id=request_id,
        )
        return JSONResponse(
            status_code=409,
            content=make_error(
                error=str(exc),
                code="CONFLICT",
                request_id=request_id,
                reason="FK_RESTRICT",
            ),
        )

    @app.exception_handler(DomainError)
    async def _domain_exception_handler(request: Request, exc: DomainError) -> JSONResponse:
        request_id = str(uuid4())
        logger.warning(
            "domain_exception",
            path=request.url.path,
            error=str(exc),
            code=exc.code,
            request_id=request_id,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=make_error(
                error=str(exc),
                code=exc.code,
                request_id=request_id,
                resource_type=exc.details.get("resource_type"),
                resource_id=exc.details.get("resource_id"),
                reason=exc.details.get("reason"),
            ),
        )

    @app.exception_handler(Exception)
    async def _global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = str(uuid4())
        logger.error(
            "unhandled_exception",
            path=request.url.path,
            error=str(exc),
            error_type=type(exc).__name__,
            request_id=request_id,
        )
        if settings.debug:
            return JSONResponse(
                status_code=500,
                content=make_error(
                    error=str(exc),
                    code="INTERNAL_ERROR",
                    request_id=request_id,
                    reason=type(exc).__name__,
                ),
            )
        return JSONResponse(
            status_code=500,
            content=make_error(
                error="Internal server error",
                code="INTERNAL_ERROR",
                request_id=request_id,
            ),
        )

    # Include API router
    app.include_router(api_router)

    return app


app = create_app()
