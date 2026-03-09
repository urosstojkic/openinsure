"""Root API router for OpenInsure."""

from fastapi import APIRouter

from openinsure.api.billing import router as billing_router
from openinsure.api.claims import router as claims_router
from openinsure.api.compliance import router as compliance_router
from openinsure.api.health import router as health_router
from openinsure.api.policies import router as policies_router
from openinsure.api.products import router as products_router
from openinsure.api.submissions import router as submissions_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(submissions_router, prefix="/api/v1/submissions", tags=["submissions"])
api_router.include_router(policies_router, prefix="/api/v1/policies", tags=["policies"])
api_router.include_router(claims_router, prefix="/api/v1/claims", tags=["claims"])
api_router.include_router(products_router, prefix="/api/v1/products", tags=["products"])
api_router.include_router(billing_router, prefix="/api/v1/billing", tags=["billing"])
api_router.include_router(compliance_router, prefix="/api/v1/compliance", tags=["compliance"])
