"""Knowledge search service using Azure AI Search with fallback."""

from __future__ import annotations

from typing import Any

import structlog

from openinsure.infrastructure.factory import get_search_adapter

logger = structlog.get_logger()


async def search_knowledge(
    query: str,
    *,
    category: str | None = None,
    top: int = 10,
) -> list[dict[str, Any]]:
    """Search insurance knowledge base. Falls back to keyword matching on static data."""
    adapter = get_search_adapter()
    if adapter:
        try:
            results = await adapter.search(
                query=query,
                top=top,
                filters=f"category eq '{category}'" if category else None,
                select=["id", "title", "content", "category", "source"],
            )
            return results.get("results", [])
        except Exception as e:
            logger.warning("search.fallback", error=str(e))

    # Fallback: keyword search over static knowledge
    return _fallback_search(query, category, top)


def _fallback_search(query: str, category: str | None, top: int) -> list[dict[str, Any]]:
    """Simple keyword search over static knowledge data."""
    from openinsure.agents.knowledge_agent import (
        COVERAGE_RULES,
        REGULATORY_REQUIREMENTS,
        UNDERWRITING_GUIDELINES,
    )

    results: list[dict[str, Any]] = []
    query_lower = query.lower()

    all_knowledge: dict[str, dict[str, Any]] = {
        "guideline": UNDERWRITING_GUIDELINES,
        "regulatory": REGULATORY_REQUIREMENTS,
        "coverage": COVERAGE_RULES,
    }

    for cat, data in all_knowledge.items():
        if category and cat != category:
            continue
        for key, value in data.items():
            content = str(value).lower()
            if query_lower in content or query_lower in key.lower():
                results.append(
                    {
                        "id": f"{cat}-{key}",
                        "title": key,
                        "content": str(value)[:500],
                        "category": cat,
                        "source": "static",
                        "score": 1.0,
                    }
                )

    return results[:top]
