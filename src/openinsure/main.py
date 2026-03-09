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

    # CORS middleware — allow the dashboard (port 3000) and any local origin
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:8000",
            "*",  # Fallback for other dev tools; restrict in production
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API router
    app.include_router(api_router)

    @app.on_event("startup")
    async def startup() -> None:
        logger.info("openinsure.startup", version=settings.app_version)

        # Seed sample data in debug / local-dev mode
        if settings.debug:
            from openinsure.infrastructure.seed_data import seed_sample_data

            await seed_sample_data()
            logger.info("openinsure.seed_data", status="loaded")

    @app.on_event("shutdown")
    async def shutdown() -> None:
        logger.info("openinsure.shutdown")

    return app


app = create_app()
