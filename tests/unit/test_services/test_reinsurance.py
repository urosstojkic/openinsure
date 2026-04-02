"""Unit tests for reinsurance service — cession, recovery, bordereau."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from openinsure.domain.reinsurance import (
    ReinsuranceContract,
    TreatyStatus,
    TreatyType,
)
from openinsure.services.reinsurance import (
    calculate_cession,
    calculate_recovery,
    generate_bordereau,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _treaty(
    *,
    treaty_type: TreatyType = TreatyType.QUOTA_SHARE,
    status: TreatyStatus = TreatyStatus.ACTIVE,
    rate: Decimal = Decimal("25"),
    retention: Decimal = Decimal("0"),
    limit: Decimal = Decimal("1000000"),
    lobs: list[str] | None = None,
) -> ReinsuranceContract:
    return ReinsuranceContract(
        treaty_number="TR-001",
        treaty_type=treaty_type,
        reinsurer_name="Swiss Re",
        status=status,
        effective_date=date(2024, 1, 1),
        expiration_date=date(2025, 1, 1),
        lines_of_business=lobs or [],
        retention=retention,
        limit=limit,
        rate=rate,
    )


def _policy(
    premium: str = "10000",
    limit: str = "1000000",
    lob: str = "cyber",
) -> dict:
    return {
        "id": str(uuid4()),
        "policy_number": "POL-001",
        "premium": premium,
        "limit": limit,
        "lob": lob,
    }


def _claim(
    paid_amount: str = "50000",
    lob: str = "cyber",
) -> dict:
    return {
        "id": str(uuid4()),
        "claim_number": "CLM-001",
        "paid_amount": paid_amount,
        "lob": lob,
    }


# ---------------------------------------------------------------------------
# calculate_cession
# ---------------------------------------------------------------------------

class TestCalculateCession:
    def test_quota_share_cession(self):
        treaty = _treaty(treaty_type=TreatyType.QUOTA_SHARE, rate=Decimal("25"))
        policy = _policy(premium="10000", limit="1000000")
        cessions = calculate_cession(policy, [treaty])
        assert len(cessions) == 1
        assert cessions[0].ceded_premium == Decimal("2500.00")
        assert cessions[0].ceded_limit == Decimal("250000.00")

    def test_quota_share_fractional_rate(self):
        """Rate < 1 should be used directly (not divided by 100 again)."""
        treaty = _treaty(treaty_type=TreatyType.QUOTA_SHARE, rate=Decimal("0.25"))
        policy = _policy(premium="10000")
        cessions = calculate_cession(policy, [treaty])
        assert cessions[0].ceded_premium == Decimal("2500.00")

    def test_excess_of_loss(self):
        treaty = _treaty(
            treaty_type=TreatyType.EXCESS_OF_LOSS,
            retention=Decimal("500000"),
            limit=Decimal("1000000"),
        )
        policy = _policy(premium="10000", limit="1000000")
        cessions = calculate_cession(policy, [treaty])
        assert len(cessions) == 1
        assert cessions[0].ceded_limit == Decimal("500000")

    def test_excess_of_loss_below_retention(self):
        """Policy below retention → no cession."""
        treaty = _treaty(
            treaty_type=TreatyType.EXCESS_OF_LOSS,
            retention=Decimal("2000000"),
            limit=Decimal("1000000"),
        )
        policy = _policy(limit="1000000")
        cessions = calculate_cession(policy, [treaty])
        assert cessions == []

    def test_surplus_treaty(self):
        treaty = _treaty(
            treaty_type=TreatyType.SURPLUS,
            retention=Decimal("200000"),
            limit=Decimal("3000000"),
        )
        policy = _policy(premium="10000", limit="1000000")
        cessions = calculate_cession(policy, [treaty])
        assert len(cessions) == 1
        assert cessions[0].ceded_limit == Decimal("800000")

    def test_facultative_cession(self):
        treaty = _treaty(treaty_type=TreatyType.FACULTATIVE, rate=Decimal("10"))
        policy = _policy(premium="50000", limit="5000000")
        cessions = calculate_cession(policy, [treaty])
        assert len(cessions) == 1
        assert cessions[0].ceded_premium == Decimal("5000.00")

    def test_inactive_treaty_skipped(self):
        treaty = _treaty(status=TreatyStatus.EXPIRED)
        cessions = calculate_cession(_policy(), [treaty])
        assert cessions == []

    def test_lob_mismatch_skipped(self):
        treaty = _treaty(lobs=["property"])
        cessions = calculate_cession(_policy(lob="cyber"), [treaty])
        assert cessions == []

    def test_lob_match(self):
        treaty = _treaty(lobs=["cyber", "property"])
        cessions = calculate_cession(_policy(lob="cyber"), [treaty])
        assert len(cessions) == 1

    def test_empty_lob_list_matches_all(self):
        """Empty LOB list on treaty means it applies to all policies."""
        treaty = _treaty(lobs=[])
        cessions = calculate_cession(_policy(lob="auto"), [treaty])
        assert len(cessions) == 1

    def test_multiple_treaties(self):
        treaties = [
            _treaty(treaty_type=TreatyType.QUOTA_SHARE, rate=Decimal("10")),
            _treaty(treaty_type=TreatyType.QUOTA_SHARE, rate=Decimal("20")),
        ]
        cessions = calculate_cession(_policy(premium="10000"), treaties)
        assert len(cessions) == 2


# ---------------------------------------------------------------------------
# calculate_recovery
# ---------------------------------------------------------------------------

class TestCalculateRecovery:
    def test_quota_share_recovery(self):
        treaty = _treaty(treaty_type=TreatyType.QUOTA_SHARE, rate=Decimal("25"))
        claim = _claim(paid_amount="100000")
        recoveries = calculate_recovery(claim, [treaty])
        assert len(recoveries) == 1
        assert recoveries[0].recovery_amount == Decimal("25000.00")

    def test_excess_of_loss_recovery(self):
        treaty = _treaty(
            treaty_type=TreatyType.EXCESS_OF_LOSS,
            retention=Decimal("50000"),
            limit=Decimal("200000"),
        )
        claim = _claim(paid_amount="100000")
        recoveries = calculate_recovery(claim, [treaty])
        assert len(recoveries) == 1
        assert recoveries[0].recovery_amount == Decimal("50000.00")

    def test_excess_of_loss_below_retention(self):
        treaty = _treaty(
            treaty_type=TreatyType.EXCESS_OF_LOSS,
            retention=Decimal("200000"),
        )
        claim = _claim(paid_amount="100000")
        recoveries = calculate_recovery(claim, [treaty])
        assert recoveries == []

    def test_excess_of_loss_capped_at_limit(self):
        treaty = _treaty(
            treaty_type=TreatyType.EXCESS_OF_LOSS,
            retention=Decimal("50000"),
            limit=Decimal("30000"),
        )
        claim = _claim(paid_amount="100000")
        recoveries = calculate_recovery(claim, [treaty])
        assert recoveries[0].recovery_amount == Decimal("30000.00")

    def test_facultative_recovery(self):
        treaty = _treaty(treaty_type=TreatyType.FACULTATIVE, rate=Decimal("15"))
        claim = _claim(paid_amount="200000")
        recoveries = calculate_recovery(claim, [treaty])
        assert recoveries[0].recovery_amount == Decimal("30000.00")

    def test_inactive_treaty_skipped(self):
        treaty = _treaty(status=TreatyStatus.PENDING)
        recoveries = calculate_recovery(_claim(), [treaty])
        assert recoveries == []

    def test_lob_mismatch_skipped(self):
        treaty = _treaty(lobs=["property"])
        recoveries = calculate_recovery(_claim(lob="cyber"), [treaty])
        assert recoveries == []

    def test_uses_reserve_amount_fallback(self):
        """If paid_amount missing, falls back to reserve_amount."""
        treaty = _treaty(treaty_type=TreatyType.QUOTA_SHARE, rate=Decimal("50"))
        claim = {"id": str(uuid4()), "claim_number": "C-1", "reserve_amount": "10000", "lob": "cyber"}
        recoveries = calculate_recovery(claim, [treaty])
        assert recoveries[0].recovery_amount == Decimal("5000.00")


# ---------------------------------------------------------------------------
# generate_bordereau
# ---------------------------------------------------------------------------

class TestGenerateBordereau:
    def test_basic_bordereau(self):
        treaty = _treaty()
        tid = str(treaty.id)
        cessions = [
            {"treaty_id": tid, "ceded_premium": "1000", "ceded_limit": "50000", "cession_date": "2024-06-01"},
            {"treaty_id": tid, "ceded_premium": "2000", "ceded_limit": "100000", "cession_date": "2024-07-01"},
        ]
        recoveries = [
            {"treaty_id": tid, "recovery_amount": "500", "recovery_date": "2024-06-15"},
        ]
        result = generate_bordereau(treaty, cessions, recoveries)
        assert result["cession_count"] == 2
        assert result["recovery_count"] == 1
        assert Decimal(result["total_ceded_premium"]) == Decimal("3000")
        assert Decimal(result["total_recoveries"]) == Decimal("500")

    def test_period_filter(self):
        treaty = _treaty()
        tid = str(treaty.id)
        cessions = [
            {"treaty_id": tid, "ceded_premium": "1000", "ceded_limit": "50000", "cession_date": "2024-03-01"},
            {"treaty_id": tid, "ceded_premium": "2000", "ceded_limit": "100000", "cession_date": "2024-08-01"},
        ]
        result = generate_bordereau(
            treaty, cessions, [],
            period_start=date(2024, 6, 1),
            period_end=date(2024, 12, 31),
        )
        assert result["cession_count"] == 1
        assert Decimal(result["total_ceded_premium"]) == Decimal("2000")

    def test_other_treaty_filtered(self):
        treaty = _treaty()
        cessions = [
            {"treaty_id": "other-id", "ceded_premium": "9999", "ceded_limit": "1"},
        ]
        result = generate_bordereau(treaty, cessions, [])
        assert result["cession_count"] == 0

    def test_empty_cessions_recoveries(self):
        result = generate_bordereau(_treaty(), [], [])
        assert result["cession_count"] == 0
        assert result["recovery_count"] == 0
        assert Decimal(result["total_ceded_premium"]) == Decimal("0")


# ---------------------------------------------------------------------------
# Adversarial / edge-case tests
# ---------------------------------------------------------------------------

class TestReinsuranceAdversarial:
    """Tests that try to break cession/recovery with hostile inputs."""

    def test_cession_zero_rate_produces_no_cession(self):
        """Rate=0 → ceded_premium=0 → cession should not be appended."""
        treaty = _treaty(treaty_type=TreatyType.QUOTA_SHARE, rate=Decimal("0"))
        cessions = calculate_cession(_policy(premium="10000"), [treaty])
        assert cessions == []

    def test_cession_negative_premium(self):
        """Negative premium → negative cession (business allows credit return)."""
        treaty = _treaty(treaty_type=TreatyType.QUOTA_SHARE, rate=Decimal("25"))
        cessions = calculate_cession(_policy(premium="-5000"), [treaty])
        # Negative ceded_premium → not > 0 → not appended
        assert cessions == []

    def test_cession_rate_exactly_one(self):
        """Rate=1 (not > 1) → used directly as multiplier → 100% cession."""
        treaty = _treaty(treaty_type=TreatyType.QUOTA_SHARE, rate=Decimal("1"))
        cessions = calculate_cession(_policy(premium="10000"), [treaty])
        assert len(cessions) == 1
        # rate=1 is NOT divided by 100 (only rates > 1 are divided)
        # So rate=1 means 100% of premium is ceded
        assert cessions[0].ceded_premium == Decimal("10000.00")

    def test_cession_rate_exactly_100(self):
        """Rate=100 → should cede 100% of premium."""
        treaty = _treaty(treaty_type=TreatyType.QUOTA_SHARE, rate=Decimal("100"))
        cessions = calculate_cession(_policy(premium="10000"), [treaty])
        assert cessions[0].ceded_premium == Decimal("10000.00")

    def test_cession_rate_over_100(self):
        """Rate > 100 → still divided by 100, yields > 100% cession."""
        treaty = _treaty(treaty_type=TreatyType.QUOTA_SHARE, rate=Decimal("200"))
        cessions = calculate_cession(_policy(premium="10000"), [treaty])
        assert cessions[0].ceded_premium == Decimal("20000.00")

    def test_excess_of_loss_zero_policy_limit(self):
        """Zero policy limit → division by zero guard in premium calc."""
        treaty = _treaty(
            treaty_type=TreatyType.EXCESS_OF_LOSS,
            retention=Decimal("0"),
            limit=Decimal("100000"),
        )
        cessions = calculate_cession(_policy(premium="10000", limit="0"), [treaty])
        # limit=0, retention=0, excess=0 → no cession
        assert cessions == []

    def test_excess_of_loss_zero_retention(self):
        """Zero retention → entire limit is excess."""
        treaty = _treaty(
            treaty_type=TreatyType.EXCESS_OF_LOSS,
            retention=Decimal("0"),
            limit=Decimal("500000"),
        )
        cessions = calculate_cession(_policy(premium="10000", limit="1000000"), [treaty])
        assert len(cessions) == 1
        assert cessions[0].ceded_limit == Decimal("500000")

    def test_recovery_zero_claim_amount(self):
        """Zero paid amount → no recovery."""
        treaty = _treaty(treaty_type=TreatyType.QUOTA_SHARE, rate=Decimal("25"))
        recoveries = calculate_recovery(_claim(paid_amount="0"), [treaty])
        assert recoveries == []

    def test_recovery_negative_amount(self):
        """Negative paid amount → negative recovery → not appended."""
        treaty = _treaty(treaty_type=TreatyType.QUOTA_SHARE, rate=Decimal("25"))
        recoveries = calculate_recovery(_claim(paid_amount="-10000"), [treaty])
        assert recoveries == []

    def test_cession_empty_policy_dict(self):
        """Empty policy dict → defaults to 0 premium, 0 limit → no cession."""
        treaty = _treaty(treaty_type=TreatyType.QUOTA_SHARE, rate=Decimal("25"))
        cessions = calculate_cession({}, [treaty])
        assert cessions == []  # 0 premium → 0 ceded → not appended

    def test_cession_missing_lob_in_policy(self):
        """Missing lob key → empty string, matches empty treaty LOB list."""
        treaty = _treaty(lobs=[])
        cessions = calculate_cession(
            {"id": str(uuid4()), "policy_number": "P-X", "premium": "1000", "limit": "10000"},
            [treaty],
        )
        assert len(cessions) == 1

    def test_cession_empty_policy_dict_crashes_on_uuid(self):
        """Empty policy dict → causes Pydantic UUID validation error (discovered adversarially)."""
        treaty = _treaty(treaty_type=TreatyType.QUOTA_SHARE, rate=Decimal("25"))
        import pydantic
        with pytest.raises(pydantic.ValidationError, match="uuid"):
            calculate_cession({"premium": "1000", "limit": "10000"}, [treaty])

    def test_bordereau_negative_recovery_amounts(self):
        """Negative recovery amounts should sum correctly."""
        treaty = _treaty()
        tid = str(treaty.id)
        recoveries = [
            {"treaty_id": tid, "recovery_amount": "-500", "recovery_date": "2024-06-15"},
            {"treaty_id": tid, "recovery_amount": "1000", "recovery_date": "2024-06-20"},
        ]
        result = generate_bordereau(treaty, [], recoveries)
        assert Decimal(result["total_recoveries"]) == Decimal("500")

    def test_bordereau_period_filter_string_comparison(self):
        """Period filter uses string comparison — verify ISO date ordering works."""
        treaty = _treaty()
        tid = str(treaty.id)
        cessions = [
            {"treaty_id": tid, "ceded_premium": "100", "ceded_limit": "1000", "cession_date": "2024-01-15"},
            {"treaty_id": tid, "ceded_premium": "200", "ceded_limit": "2000", "cession_date": "2024-12-31"},
        ]
        result = generate_bordereau(
            treaty, cessions, [],
            period_start=date(2024, 6, 1),
        )
        assert result["cession_count"] == 1
        assert Decimal(result["total_ceded_premium"]) == Decimal("200")

    def test_cession_pending_treaty_skipped(self):
        """PENDING status should also be skipped (only ACTIVE cedes)."""
        treaty = _treaty(status=TreatyStatus.PENDING)
        cessions = calculate_cession(_policy(), [treaty])
        assert cessions == []

    def test_recovery_surplus_claim_exceeds_limit(self):
        """Surplus recovery should cap at treaty limit."""
        treaty = _treaty(
            treaty_type=TreatyType.SURPLUS,
            retention=Decimal("50000"),
            limit=Decimal("30000"),
        )
        recoveries = calculate_recovery(_claim(paid_amount="200000"), [treaty])
        assert recoveries[0].recovery_amount == Decimal("30000.00")
