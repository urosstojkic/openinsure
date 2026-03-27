"""Tests for submission_service.py handling of malformed Foundry responses."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from openinsure.services.submission_service import SubmissionService, _safe_float

FOUNDRY_CLIENT_PATCH = "openinsure.agents.foundry_client.get_foundry_client"

# ---------------------------------------------------------------------------
# _safe_float helper
# ---------------------------------------------------------------------------


class TestSafeFloat:
    def test_normal_int(self) -> None:
        assert _safe_float(5, default=0.0) == 5.0

    def test_normal_float(self) -> None:
        assert _safe_float(3.14, default=0.0) == 3.14

    def test_string_number(self) -> None:
        assert _safe_float("12.5", default=0.0) == 12.5

    def test_none_returns_default(self) -> None:
        assert _safe_float(None, default=99.0) == 99.0

    def test_garbage_string(self) -> None:
        assert _safe_float("not_a_number", default=7.0) == 7.0

    def test_dict_returns_default(self) -> None:
        assert _safe_float({"x": 1}, default=1.0) == 1.0

    def test_nan_returns_default(self) -> None:
        assert _safe_float(float("nan"), default=5.0) == 5.0


# ---------------------------------------------------------------------------
# SubmissionService.run_triage with malformed responses
# ---------------------------------------------------------------------------


def _mock_foundry(invoke_response: dict[str, Any]) -> MagicMock:
    """Create a mock foundry client that returns the given invoke response."""
    mock = MagicMock()
    mock.is_available = True
    mock.invoke = AsyncMock(return_value=invoke_response)
    return mock


def _mock_repo() -> MagicMock:
    repo = MagicMock()
    repo.update = AsyncMock()
    return repo


class TestTriageMalformedResponse:
    @pytest.mark.asyncio
    async def test_triage_non_json_response(self) -> None:
        """Foundry returns non-JSON text — should fall through to local fallback."""
        foundry = _mock_foundry(
            {
                "response": {"raw_text": "I can't do that", "parse_error": "not JSON"},
                "source": "foundry",
                "raw": "I can't do that",
                "execution_time_ms": 100,
            }
        )
        repo = _mock_repo()

        svc = SubmissionService()
        svc._repo = repo

        with patch(FOUNDRY_CLIENT_PATCH, return_value=foundry):
            result = await svc.run_triage("sub-1", {"id": "sub-1"})

        # Should still produce a valid triage result (with defaults)
        assert result["status"] == "underwriting"
        assert isinstance(result["risk_score"], float)

    @pytest.mark.asyncio
    async def test_triage_empty_response(self) -> None:
        foundry = _mock_foundry(
            {
                "response": {"raw_text": "", "parse_error": "Empty response"},
                "source": "foundry",
                "raw": "",
                "execution_time_ms": 50,
            }
        )
        repo = _mock_repo()

        svc = SubmissionService()
        svc._repo = repo

        with patch(FOUNDRY_CLIENT_PATCH, return_value=foundry):
            result = await svc.run_triage("sub-1", {"id": "sub-1"})

        assert result["status"] == "underwriting"
        assert result["risk_score"] == 5.0  # default

    @pytest.mark.asyncio
    async def test_triage_risk_score_wrong_type(self) -> None:
        foundry = _mock_foundry(
            {
                "response": {"appetite_match": "yes", "risk_score": "high"},
                "source": "foundry",
                "raw": '{"appetite_match":"yes","risk_score":"high"}',
                "execution_time_ms": 100,
            }
        )
        repo = _mock_repo()

        svc = SubmissionService()
        svc._repo = repo

        with patch(FOUNDRY_CLIENT_PATCH, return_value=foundry):
            result = await svc.run_triage("sub-1", {"id": "sub-1"})

        assert result["status"] == "underwriting"
        assert result["risk_score"] == 5.0  # falls back to default

    @pytest.mark.asyncio
    async def test_triage_missing_keys_uses_defaults(self) -> None:
        """JSON response missing expected keys — defaults applied safely."""
        foundry = _mock_foundry(
            {
                "response": {"some_other_key": "value"},
                "source": "foundry",
                "raw": '{"some_other_key": "value"}',
                "execution_time_ms": 80,
            }
        )
        repo = _mock_repo()

        svc = SubmissionService()
        svc._repo = repo

        with patch(FOUNDRY_CLIENT_PATCH, return_value=foundry):
            result = await svc.run_triage("sub-1", {"id": "sub-1"})

        assert result["status"] == "underwriting"
        assert result["recommendation"] == "proceed_to_quote"
        assert result["risk_score"] == 5.0


# ---------------------------------------------------------------------------
# SubmissionService.calculate_premium with malformed responses
# ---------------------------------------------------------------------------


class TestPremiumMalformedResponse:
    @pytest.mark.asyncio
    async def test_premium_garbage_value_falls_to_rating_engine(self) -> None:
        """recommended_premium is garbage string — should fall to local engine."""
        foundry = _mock_foundry(
            {
                "response": {"recommended_premium": "not_a_number", "risk_score": 5},
                "source": "foundry",
                "raw": '{"recommended_premium":"not_a_number"}',
                "execution_time_ms": 100,
            }
        )
        repo = _mock_repo()

        svc = SubmissionService()
        svc._repo = repo

        with patch(FOUNDRY_CLIENT_PATCH, return_value=foundry):
            result = await svc.calculate_premium("sub-1", {"id": "sub-1"})

        # Should fall through to local rating engine or LOB minimum
        assert result["ai_mode"] in ("local_rating_engine", "lob_minimum_fallback")
        assert result["premium"] > 0

    @pytest.mark.asyncio
    async def test_premium_none_value_falls_to_rating_engine(self) -> None:
        foundry = _mock_foundry(
            {
                "response": {"recommended_premium": None},
                "source": "foundry",
                "raw": '{"recommended_premium":null}',
                "execution_time_ms": 100,
            }
        )
        repo = _mock_repo()

        svc = SubmissionService()
        svc._repo = repo

        with patch(FOUNDRY_CLIENT_PATCH, return_value=foundry):
            result = await svc.calculate_premium("sub-1", {"id": "sub-1"})

        assert result["ai_mode"] in ("local_rating_engine", "lob_minimum_fallback")

    @pytest.mark.asyncio
    async def test_premium_missing_key_falls_to_rating_engine(self) -> None:
        foundry = _mock_foundry(
            {
                "response": {"risk_score": 5},
                "source": "foundry",
                "raw": '{"risk_score": 5}',
                "execution_time_ms": 100,
            }
        )
        repo = _mock_repo()

        svc = SubmissionService()
        svc._repo = repo

        with patch(FOUNDRY_CLIENT_PATCH, return_value=foundry):
            result = await svc.calculate_premium("sub-1", {"id": "sub-1"})

        assert result["ai_mode"] in ("local_rating_engine", "lob_minimum_fallback")

    @pytest.mark.asyncio
    async def test_premium_negative_falls_to_rating_engine(self) -> None:
        foundry = _mock_foundry(
            {
                "response": {"recommended_premium": -500},
                "source": "foundry",
                "raw": '{"recommended_premium":-500}',
                "execution_time_ms": 100,
            }
        )
        repo = _mock_repo()

        svc = SubmissionService()
        svc._repo = repo

        with patch(FOUNDRY_CLIENT_PATCH, return_value=foundry):
            result = await svc.calculate_premium("sub-1", {"id": "sub-1"})

        assert result["ai_mode"] in ("local_rating_engine", "lob_minimum_fallback")

    @pytest.mark.asyncio
    async def test_premium_valid_foundry_response(self) -> None:
        foundry = _mock_foundry(
            {
                "response": {"recommended_premium": 12500, "risk_score": 35},
                "source": "foundry",
                "raw": '{"recommended_premium":12500}',
                "execution_time_ms": 100,
            }
        )
        repo = _mock_repo()

        svc = SubmissionService()
        svc._repo = repo

        with patch(FOUNDRY_CLIENT_PATCH, return_value=foundry):
            result = await svc.calculate_premium("sub-1", {"id": "sub-1"})

        assert result["ai_mode"] == "foundry"
        assert result["premium"] == 12500
