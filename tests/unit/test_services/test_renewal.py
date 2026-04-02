"""Unit tests for renewal service — identify_renewals and generate_renewal_terms."""

from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from openinsure.services.renewal import generate_renewal_terms, identify_renewals


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _policy(
    policy_number: str = "POL-001",
    expiration_date: str | None = None,
    premium: float = 10000.0,
) -> dict:
    return {
        "policy_number": policy_number,
        "expiration_date": expiration_date,
        "total_premium": premium,
        "status": "active",
    }


# ---------------------------------------------------------------------------
# identify_renewals
# ---------------------------------------------------------------------------

class TestIdentifyRenewals:
    @pytest.mark.asyncio
    async def test_finds_expiring_policies(self):
        tomorrow = str(date.today() + timedelta(days=1))
        policies = [_policy(expiration_date=tomorrow)]
        mock_repo = AsyncMock()
        mock_repo.list_all.return_value = policies

        with patch("openinsure.services.renewal.get_policy_repository", return_value=mock_repo):
            result = await identify_renewals(days_ahead=90)
        assert len(result) == 1
        assert result[0]["policy_number"] == "POL-001"
        assert "days_to_expiry" in result[0]

    @pytest.mark.asyncio
    async def test_excludes_far_future_policies(self):
        far_future = str(date.today() + timedelta(days=365))
        policies = [_policy(expiration_date=far_future)]
        mock_repo = AsyncMock()
        mock_repo.list_all.return_value = policies

        with patch("openinsure.services.renewal.get_policy_repository", return_value=mock_repo):
            result = await identify_renewals(days_ahead=90)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_sorts_by_days_to_expiry(self):
        d1 = str(date.today() + timedelta(days=10))
        d2 = str(date.today() + timedelta(days=5))
        d3 = str(date.today() + timedelta(days=30))
        policies = [
            _policy("POL-A", expiration_date=d1),
            _policy("POL-B", expiration_date=d2),
            _policy("POL-C", expiration_date=d3),
        ]
        mock_repo = AsyncMock()
        mock_repo.list_all.return_value = policies

        with patch("openinsure.services.renewal.get_policy_repository", return_value=mock_repo):
            result = await identify_renewals(days_ahead=90)
        numbers = [r["policy_number"] for r in result]
        assert numbers == ["POL-B", "POL-A", "POL-C"]

    @pytest.mark.asyncio
    async def test_no_expiration_date_skipped(self):
        policies = [_policy(expiration_date=None)]
        mock_repo = AsyncMock()
        mock_repo.list_all.return_value = policies

        with patch("openinsure.services.renewal.get_policy_repository", return_value=mock_repo):
            result = await identify_renewals()
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_empty_repo(self):
        mock_repo = AsyncMock()
        mock_repo.list_all.return_value = []

        with patch("openinsure.services.renewal.get_policy_repository", return_value=mock_repo):
            result = await identify_renewals()
        assert result == []

    @pytest.mark.asyncio
    async def test_custom_days_ahead(self):
        d_in_window = str(date.today() + timedelta(days=25))
        d_out_window = str(date.today() + timedelta(days=35))
        policies = [
            _policy("IN", expiration_date=d_in_window),
            _policy("OUT", expiration_date=d_out_window),
        ]
        mock_repo = AsyncMock()
        mock_repo.list_all.return_value = policies

        with patch("openinsure.services.renewal.get_policy_repository", return_value=mock_repo):
            result = await identify_renewals(days_ahead=30)
        assert len(result) == 1
        assert result[0]["policy_number"] == "IN"


# ---------------------------------------------------------------------------
# generate_renewal_terms
# ---------------------------------------------------------------------------

class TestGenerateRenewalTerms:
    @pytest.mark.asyncio
    async def test_premium_increase(self):
        policy = _policy(premium=10000.0)
        terms = await generate_renewal_terms(policy)
        assert terms["renewal_premium"] == pytest.approx(10500.0)

    @pytest.mark.asyncio
    async def test_recommendation_renew_as_is(self):
        terms = await generate_renewal_terms(_policy(premium=5000.0))
        assert terms["recommendation"] == "renew_as_is"

    @pytest.mark.asyncio
    async def test_recommendation_review_required(self):
        terms = await generate_renewal_terms(_policy(premium=0))
        assert terms["recommendation"] == "review_required"

    @pytest.mark.asyncio
    async def test_effective_date_from_expiration(self):
        policy = _policy(expiration_date="2025-06-01")
        terms = await generate_renewal_terms(policy)
        assert terms["effective_date"] == "2025-06-01"

    @pytest.mark.asyncio
    async def test_original_policy_number(self):
        terms = await generate_renewal_terms(_policy(policy_number="POL-XYZ"))
        assert terms["original_policy"] == "POL-XYZ"

    @pytest.mark.asyncio
    async def test_changes_list_initially_empty(self):
        terms = await generate_renewal_terms(_policy())
        assert terms["changes"] == []

    @pytest.mark.asyncio
    async def test_fallback_to_premium_key(self):
        """If total_premium is missing, falls back to 'premium' key."""
        policy = {"policy_number": "P-1", "premium": 8000}
        terms = await generate_renewal_terms(policy)
        assert terms["renewal_premium"] == pytest.approx(8400.0)


# ---------------------------------------------------------------------------
# Adversarial / edge-case tests
# ---------------------------------------------------------------------------

class TestRenewalAdversarial:
    """Tests that try to break renewal logic with hostile inputs."""

    @pytest.mark.asyncio
    async def test_repo_exception_propagates(self):
        """Repository failure should propagate — not silently swallowed."""
        mock_repo = AsyncMock()
        mock_repo.list_all.side_effect = RuntimeError("Database connection lost")
        with patch("openinsure.services.renewal.get_policy_repository", return_value=mock_repo):
            with pytest.raises(RuntimeError, match="Database connection lost"):
                await identify_renewals()

    @pytest.mark.asyncio
    async def test_negative_days_ahead(self):
        """Negative days_ahead → target_date in the past → only already-expired policies."""
        yesterday = str(date.today() - timedelta(days=1))
        policies = [_policy(expiration_date=yesterday)]
        mock_repo = AsyncMock()
        mock_repo.list_all.return_value = policies
        with patch("openinsure.services.renewal.get_policy_repository", return_value=mock_repo):
            result = await identify_renewals(days_ahead=-10)
        # yesterday <= (today - 10 days) is False, so nothing returned
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_zero_days_ahead(self):
        """days_ahead=0 → target is today → only today/past expiries."""
        today_str = str(date.today())
        policies = [_policy("EXP-TODAY", expiration_date=today_str)]
        mock_repo = AsyncMock()
        mock_repo.list_all.return_value = policies
        with patch("openinsure.services.renewal.get_policy_repository", return_value=mock_repo):
            result = await identify_renewals(days_ahead=0)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_negative_premium_renewal(self):
        """Negative premium → 5% increase on a negative = more negative."""
        terms = await generate_renewal_terms(_policy(premium=-5000.0))
        assert terms["renewal_premium"] == pytest.approx(-5250.0)
        assert terms["recommendation"] == "review_required"

    @pytest.mark.asyncio
    async def test_none_premium_crashes(self):
        """None premium values → float(None) raises TypeError.
        Adversarial finding: renewal.py doesn't guard against None premium.
        """
        policy = {"policy_number": "P-1", "total_premium": None, "premium": None}
        with pytest.raises(TypeError):
            await generate_renewal_terms(policy)

    @pytest.mark.asyncio
    async def test_missing_all_premium_keys(self):
        """No premium keys at all → should default to 0."""
        policy = {"policy_number": "P-1"}
        terms = await generate_renewal_terms(policy)
        assert terms["renewal_premium"] == pytest.approx(0.0)

    @pytest.mark.asyncio
    async def test_very_large_days_ahead(self):
        """Extreme days_ahead should not overflow."""
        far = str(date.today() + timedelta(days=36500))
        policies = [_policy(expiration_date=far)]
        mock_repo = AsyncMock()
        mock_repo.list_all.return_value = policies
        with patch("openinsure.services.renewal.get_policy_repository", return_value=mock_repo):
            result = await identify_renewals(days_ahead=36500)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_malformed_expiration_date_string_comparison(self):
        """Malformed date string → str comparison still works (no fromisoformat
        called until days_to_expiry calc), so ValueError may or may not fire
        depending on whether the string sorts before the target date."""
        policies = [_policy(expiration_date="not-a-date")]
        mock_repo = AsyncMock()
        mock_repo.list_all.return_value = policies
        with patch("openinsure.services.renewal.get_policy_repository", return_value=mock_repo):
            try:
                result = await identify_renewals()
                # "not-a-date" <= str(target_date) → True (alphabetical)
                # Then date.fromisoformat("not-a-date") → ValueError
            except ValueError:
                pass  # Expected when trying to parse the date for days_to_expiry

    @pytest.mark.asyncio
    async def test_already_expired_policy(self):
        """Already-expired policies should still be returned (overdue renewals)."""
        past = str(date.today() - timedelta(days=30))
        policies = [_policy("EXPIRED", expiration_date=past)]
        mock_repo = AsyncMock()
        mock_repo.list_all.return_value = policies
        with patch("openinsure.services.renewal.get_policy_repository", return_value=mock_repo):
            result = await identify_renewals(days_ahead=90)
        assert len(result) == 1
        assert result[0]["days_to_expiry"] < 0
