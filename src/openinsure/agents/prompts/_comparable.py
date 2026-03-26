# mypy: ignore-errors
"""Comparable account context helpers for prompt injection (Feature 2)."""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger()


async def _get_comparable_triage_context(submission: dict[str, Any]) -> str:
    """Get comparable account context for triage (Feature 2)."""
    try:
        from openinsure.services.comparable_accounts import get_comparable_finder

        finder = get_comparable_finder()
        return await finder.get_triage_context(submission)
    except Exception:
        logger.debug("prompts.comparable_triage_context_failed", exc_info=True)
        return ""


async def _get_comparable_underwriting_context(submission: dict[str, Any]) -> str:
    """Get comparable account context for underwriting (Feature 2)."""
    try:
        from openinsure.services.comparable_accounts import get_comparable_finder

        finder = get_comparable_finder()
        return await finder.get_underwriting_context(submission)
    except Exception:
        logger.debug("prompts.comparable_uw_context_failed", exc_info=True)
        return ""
