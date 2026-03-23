"""Root API router for OpenInsure."""

from fastapi import APIRouter, Depends

from openinsure.api.actuarial import router as actuarial_router
from openinsure.api.agent_traces import router as agent_traces_router
from openinsure.api.analytics import router as analytics_router
from openinsure.api.billing import router as billing_router
from openinsure.api.broker import router as broker_router
from openinsure.api.claims import router as claims_router
from openinsure.api.compliance import router as compliance_router
from openinsure.api.demo import router as demo_router
from openinsure.api.documents import router as documents_router
from openinsure.api.escalations import router as escalations_router
from openinsure.api.events import router as events_router
from openinsure.api.finance import router as finance_router
from openinsure.api.health import router as health_router
from openinsure.api.knowledge import router as knowledge_router
from openinsure.api.metrics import router as metrics_router
from openinsure.api.mga_oversight import router as mga_router
from openinsure.api.policies import router as policies_router
from openinsure.api.products import router as products_router
from openinsure.api.reinsurance import router as reinsurance_router
from openinsure.api.renewals import router as renewals_router
from openinsure.api.submissions import router as submissions_router
from openinsure.api.underwriter import router as underwriter_router
from openinsure.api.workflows import router as workflows_router
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
api_v1_router.include_router(knowledge_router, prefix="/knowledge", tags=["knowledge"])

# Carrier-only module — disabled in MGA deployments via deployment profile
api_v1_router.include_router(reinsurance_router, prefix="/reinsurance", tags=["reinsurance"])
api_v1_router.include_router(actuarial_router, prefix="/actuarial", tags=["actuarial"])
api_v1_router.include_router(metrics_router, prefix="/metrics", tags=["metrics"])
api_v1_router.include_router(escalations_router, prefix="/escalations", tags=["escalations"])
api_v1_router.include_router(workflows_router, prefix="/workflows", tags=["workflows"])
api_v1_router.include_router(underwriter_router, prefix="/underwriter", tags=["underwriter"])
api_v1_router.include_router(broker_router, prefix="/broker", tags=["broker"])
api_v1_router.include_router(renewals_router, prefix="/renewals", tags=["renewals"])
api_v1_router.include_router(mga_router, prefix="/mga", tags=["mga-oversight"])
api_v1_router.include_router(finance_router, prefix="/finance", tags=["finance"])
api_v1_router.include_router(analytics_router, prefix="/analytics", tags=["analytics"])
api_v1_router.include_router(agent_traces_router, prefix="/agent-traces", tags=["agent-traces"])
api_v1_router.include_router(demo_router, prefix="/demo", tags=["demo"])

api_router.include_router(api_v1_router)
