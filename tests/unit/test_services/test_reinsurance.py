"""Unit tests for reinsurance service — cession, recovery, bordereau."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

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
