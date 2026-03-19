"""OpenInsure — AI-Native Insurance Platform API."""

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from openinsure.api.router import api_router
from openinsure.config import get_settings

logger = structlog.get_logger()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="OpenInsure API",
        description=(
            "AI-native open-source core insurance platform. Agents-first architecture for cyber insurance operations."
        ),
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

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

    @app.exception_handler(Exception)
    async def _global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        if settings.debug:
            return JSONResponse(
                status_code=500,
                content={"detail": str(exc), "type": type(exc).__name__},
            )
        logger.error("unhandled_exception", path=request.url.path, error=str(exc))
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    # Include API router
    app.include_router(api_router)

    @app.on_event("startup")
    async def startup() -> None:
        logger.info("openinsure.startup", version=settings.app_version)
        logger.info("openinsure.storage_mode", mode=settings.storage_mode)

        # Auto-apply SQL migrations on startup when Azure SQL is configured
        if settings.storage_mode == "azure" and settings.sql_connection_string:
            try:
                from openinsure.infrastructure.auto_migrate import apply_pending_migrations

                applied = await apply_pending_migrations()
                if applied:
                    logger.info("openinsure.migrations", applied=applied)
                else:
                    logger.info("openinsure.migrations", status="up-to-date")
            except Exception as exc:
                logger.warning("openinsure.migrations.failed", error=str(exc))

        # Seed sample data only in debug / local-dev mode with in-memory storage
        if settings.debug and settings.storage_mode == "memory":
            from openinsure.infrastructure.seed_data import seed_sample_data

            await seed_sample_data()
            logger.info("openinsure.seed_data", status="loaded")

    @app.on_event("shutdown")
    async def shutdown() -> None:
        logger.info("openinsure.shutdown")

    return app


app = create_app()
