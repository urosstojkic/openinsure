"""Knowledge search API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query

router = APIRouter()


@router.get("/search")
async def search_knowledge_endpoint(
    q: str = Query(..., min_length=2),
    category: str | None = Query(None),
    top: int = Query(10, ge=1, le=50),
):
    """Search the insurance knowledge base."""
    from openinsure.services.knowledge_search import search_knowledge

    results = await search_knowledge(q, category=category, top=top)
    return {"query": q, "results": results, "count": len(results)}
