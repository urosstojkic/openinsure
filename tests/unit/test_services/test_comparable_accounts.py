"""Tests for the Comparable Account Retrieval service."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

from openinsure.services.comparable_accounts import (
    ComparableAccountFinder,
    get_comparable_finder,
)


def _make_submission(
    sub_id: str = "sub-new",
    *,
    revenue: float = 5_000_000,
    employees: int = 50,
    sic: str = "7372",
    industry: str = "technology",
    lob: str = "cyber",
    status: str = "received",
    premium: float | None = None,
) -> dict[str, Any]:
    return {
        "id": sub_id,
        "applicant_name": f"Test Corp {sub_id}",
        "line_of_business": lob,
        "status": status,
        "quoted_premium": premium,
        "risk_data": {
            "annual_revenue": revenue,
            "employee_count": employees,
            "industry_sic_code": sic,
            "industry": industry,
            "security_maturity_score": 7.0,
            "has_mfa": True,
            "has_endpoint_protection": True,
        },
    }


# Sample historical data for mocked repo
MOCK_SUBMISSIONS = [
    _make_submission("sub-hist-1", revenue=4_500_000, employees=45, status="bound", premium=12000),
    _make_submission("sub-hist-2", revenue=6_000_000, employees=60, status="quoted", premium=15000),
    _make_submission("sub-hist-3", revenue=5_000_000, employees=50, status="declined"),
    _make_submission(
        "sub-hist-4",
        revenue=50_000_000,
        employees=500,
        sic="2011",
        industry="manufacturing",
        status="bound",
        premium=80000,
    ),
    _make_submission("sub-hist-5", revenue=5_200_000, employees=48, status="bound", premium=11000),
    _make_submission("sub-hist-6", status="received"),
]


def _make_finder() -> ComparableAccountFinder:
    finder = ComparableAccountFinder()
    sub_repo = AsyncMock()
    sub_repo.list_all = AsyncMock(return_value=list(MOCK_SUBMISSIONS))
    finder._sub_repo_instance = sub_repo
    finder._policy_repo_instance = AsyncMock(list_all=AsyncMock(return_value=[]))
    finder._claim_repo_instance = AsyncMock(list_all=AsyncMock(return_value=[]))
    return finder


class TestSimilarityScore:
    """Tests for the similarity scoring algorithm."""

    def test_identical_attributes_max_score(self) -> None:
        score = ComparableAccountFinder._similarity_score(
            target_revenue=5_000_000,
            target_employees=50,
            target_sic="7372",
            target_industry="technology",
            target_security=7.0,
            cand_merged={
                "annual_revenue": 5_000_000,
                "employee_count": 50,
                "industry_sic_code": "7372",
                "security_maturity_score": 7.0,
            },
        )
        assert score > 0.8

    def test_different_industry_low_score(self) -> None:
        score = ComparableAccountFinder._similarity_score(
            target_revenue=5_000_000,
            target_employees=50,
            target_sic="7372",
            target_industry="technology",
            target_security=7.0,
            cand_merged={
                "annual_revenue": 5_000_000,
                "employee_count": 50,
                "industry_sic_code": "2011",
                "security_maturity_score": 7.0,
            },
        )
        assert score < 0.7

    def test_similar_revenue_within_50pct(self) -> None:
        score = ComparableAccountFinder._similarity_score(
            target_revenue=5_000_000,
            target_employees=50,
            target_sic="7372",
            target_industry="technology",
            target_security=7.0,
            cand_merged={
                "annual_revenue": 6_000_000,
                "employee_count": 50,
                "industry_sic_code": "7372",
                "security_maturity_score": 7.0,
            },
        )
        assert score > 0.7

    def test_revenue_outside_50pct_lower_score(self) -> None:
        close = ComparableAccountFinder._similarity_score(
            target_revenue=5_000_000,
            target_employees=50,
            target_sic="7372",
            target_industry="technology",
            target_security=7.0,
            cand_merged={
                "annual_revenue": 5_500_000,
                "employee_count": 50,
                "industry_sic_code": "7372",
                "security_maturity_score": 7.0,
            },
        )
        far = ComparableAccountFinder._similarity_score(
            target_revenue=5_000_000,
            target_employees=50,
            target_sic="7372",
            target_industry="technology",
            target_security=7.0,
            cand_merged={
                "annual_revenue": 50_000_000,
                "employee_count": 50,
                "industry_sic_code": "7372",
                "security_maturity_score": 7.0,
            },
        )
        assert close > far

    def test_zero_values_handled(self) -> None:
        score = ComparableAccountFinder._similarity_score(
            target_revenue=0,
            target_employees=0,
            target_sic="",
            target_industry="",
            target_security=0,
            cand_merged={},
        )
        assert score == 0.0


class TestFindComparables:
    """Tests for the end-to-end find_comparables method."""

    async def test_find_comparables_returns_list(self) -> None:
        finder = _make_finder()
        results = await finder.find_comparables(_make_submission(), limit=5)
        assert isinstance(results, list)
        assert len(results) > 0

    async def test_comparable_has_expected_fields(self) -> None:
        finder = _make_finder()
        results = await finder.find_comparables(_make_submission(), limit=5)
        for r in results:
            assert "submission_id" in r
            assert "similarity_score" in r
            assert "status" in r
            assert "claims_count" in r

    async def test_excludes_self(self) -> None:
        finder = _make_finder()
        results = await finder.find_comparables(_make_submission(sub_id="sub-hist-1"), limit=100)
        ids = [r["submission_id"] for r in results]
        assert "sub-hist-1" not in ids

    async def test_excludes_received_status(self) -> None:
        finder = _make_finder()
        results = await finder.find_comparables(_make_submission(), limit=100)
        ids = [r["submission_id"] for r in results]
        assert "sub-hist-6" not in ids

    async def test_respects_limit(self) -> None:
        finder = _make_finder()
        results = await finder.find_comparables(_make_submission(), limit=2)
        assert len(results) <= 2

    async def test_sorted_by_similarity(self) -> None:
        finder = _make_finder()
        results = await finder.find_comparables(_make_submission(), limit=5)
        if len(results) >= 2:
            scores = [r["similarity_score"] for r in results]
            assert scores == sorted(scores, reverse=True)


class TestContextBuilders:
    """Tests for the prompt context string builders."""

    async def test_triage_context_has_content(self) -> None:
        finder = _make_finder()
        ctx = await finder.get_triage_context(_make_submission())
        assert isinstance(ctx, str)
        assert "COMPARABLE ACCOUNTS" in ctx

    async def test_underwriting_context_has_content(self) -> None:
        finder = _make_finder()
        ctx = await finder.get_underwriting_context(_make_submission())
        assert isinstance(ctx, str)
        assert "COMPARABLE PRICING" in ctx


class TestSingleton:
    """Test the singleton factory."""

    def test_get_comparable_finder_returns_same_instance(self) -> None:
        f1 = get_comparable_finder()
        f2 = get_comparable_finder()
        assert f1 is f2
