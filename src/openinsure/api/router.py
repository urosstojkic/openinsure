"""Root API router for OpenInsure."""

from fastapi import APIRouter, Depends

from openinsure.api.billing import router as billing_router
from openinsure.api.claims import router as claims_router
from openinsure.api.compliance import router as compliance_router
from openinsure.api.health import router as health_router
from openinsure.api.policies import router as policies_router
from openinsure.api.products import router as products_router
from openinsure.api.documents import router as documents_router
from openinsure.api.events import router as events_router
from openinsure.api.submissions import router as submissions_router
from openinsure.rbac.auth import get_current_user

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])

# All /api/v1/* endpoints require API key authentication
api_v1_router = APIRouter(prefix="/api/v1", dependencies=[Depends(get_current_user)])
api_v1_router.include_router(submissions_router, prefix="/submissions", tags=["submissions"])
api_v1_router.include_router(policies_router, prefix="/policies", tags=["policies"])
api_v1_router.include_router(claims_router, prefix="/claims", tags=["claims"])
api_v1_router.include_router(products_router, prefix="/products", tags=["products"])
api_v1_router.include_router(billing_router, prefix="/billing", tags=["billing"])
api_v1_router.include_router(compliance_router, prefix="/compliance", tags=["compliance"])
api_v1_router.include_router(documents_router, prefix="/documents", tags=["documents"])
api_v1_router.include_router(events_router, prefix="/events", tags=["events"])

api_router.include_router(api_v1_router)
