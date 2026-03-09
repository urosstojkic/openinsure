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

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure per environment in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API router
    app.include_router(api_router)

    @app.on_event("startup")
    async def startup() -> None:
        logger.info("openinsure.startup", version=settings.app_version)

    @app.on_event("shutdown")
    async def shutdown() -> None:
        logger.info("openinsure.shutdown")

    return app


app = create_app()
