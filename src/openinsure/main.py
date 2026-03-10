"""OpenInsure — AI-Native Insurance Platform API."""

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

    # Include API router
    app.include_router(api_router)

    @app.on_event("startup")
    async def startup() -> None:
        logger.info("openinsure.startup", version=settings.app_version)
        logger.info("openinsure.storage_mode", mode=settings.storage_mode)

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
