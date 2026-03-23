"""Tests for the bias monitoring engine."""

import pytest

from openinsure.services.bias_monitor import (
    BiasAnalysisResult,
    _analyze_by_group,
    _revenue_band,
    _security_score_band,
    analyze_submission_bias,
    generate_bias_report,
)

# ---------------------------------------------------------------------------
# Helpers to build fake submissions
# ---------------------------------------------------------------------------


def _make_submission(*, industry: str, revenue: float, channel: str, status: str) -> dict:
    return {
        "risk_data": {"industry": industry, "annual_revenue": revenue},
        "channel": channel,
        "status": status,
    }


def _make_submissions(groups: list[tuple[str, int, int]]) -> list[dict]:
    """Build a flat list of submissions from (industry, approved, rejected) triples."""
    subs = []
    for industry, approved, rejected in groups:
        for _ in range(approved):
            subs.append(_make_submission(industry=industry, revenue=5_000_000, channel="email", status="bound"))
        for _ in range(rejected):
            subs.append(_make_submission(industry=industry, revenue=5_000_000, channel="email", status="declined"))
    return subs


# ---------------------------------------------------------------------------
# BiasAnalysisResult
# ---------------------------------------------------------------------------


class TestBiasAnalysisResult:
    def test_to_dict_contains_all_keys(self):
        result = BiasAnalysisResult()
        result.metric_name = "Test Metric"
        result.group_field = "industry"
        d = result.to_dict()
        assert d["metric"] == "Test Metric"
        assert d["group_field"] == "industry"
        assert "four_fifths_ratio" in d
        assert "passes_threshold" in d
        assert "flagged_groups" in d
        assert "timestamp" in d

    def test_defaults(self):
        result = BiasAnalysisResult()
        assert result.passes_threshold is True
        assert result.four_fifths_ratio == 1.0
        assert result.flagged_groups == []


# ---------------------------------------------------------------------------
# _revenue_band
# ---------------------------------------------------------------------------


class TestRevenueBand:
    @pytest.mark.parametrize(
        ("revenue", "expected"),
        [
            (500_000, "<$1M"),
            (1_000_000, "$1M-$5M"),
            (4_999_999, "$1M-$5M"),
            (5_000_000, "$5M-$25M"),
            (25_000_000, "$25M-$100M"),
            (100_000_000, "$100M+"),
            (None, "Unknown"),
            ("bad", "Unknown"),
        ],
    )
    def test_bands(self, revenue, expected):
        assert _revenue_band(revenue) == expected


# ---------------------------------------------------------------------------
# _analyze_by_group
# ---------------------------------------------------------------------------


class TestAnalyzeByGroup:
    def test_single_group_no_flag(self):
        """A single group can't trigger 4/5ths rule (need >= 2 groups)."""
        subs = _make_submissions([("Tech", 15, 5)])
        result = _analyze_by_group(
            subs,
            group_field="industry",
            group_fn=lambda s: s["risk_data"]["industry"],
            outcome_fn=lambda s: s["status"] == "bound",
            metric_name="test",
        )
        assert result.passes_threshold is True
        assert result.flagged_groups == []
        assert result.groups["Tech"]["total"] == 20
        assert result.groups["Tech"]["positive"] == 15

    def test_two_equal_groups_pass(self):
        subs = _make_submissions([("Tech", 15, 5), ("Finance", 14, 6)])
        result = _analyze_by_group(
            subs,
            group_field="industry",
            group_fn=lambda s: s["risk_data"]["industry"],
            outcome_fn=lambda s: s["status"] == "bound",
            metric_name="test",
        )
        assert result.passes_threshold is True
        assert result.flagged_groups == []

    def test_disparate_group_flagged(self):
        """One group well below 80% of the best rate → flagged."""
        subs = _make_submissions([("Tech", 18, 2), ("Retail", 5, 15)])
        result = _analyze_by_group(
            subs,
            group_field="industry",
            group_fn=lambda s: s["risk_data"]["industry"],
            outcome_fn=lambda s: s["status"] == "bound",
            metric_name="test",
        )
        assert result.passes_threshold is False
        assert "Retail" in result.flagged_groups
        assert result.four_fifths_ratio < 0.8

    def test_small_groups_ignored(self):
        """Groups with < 10 items are excluded from 4/5ths analysis."""
        subs = _make_submissions([("Tech", 18, 2)])
        # Add a tiny group that has a terrible rate
        for _ in range(3):
            subs.append(_make_submission(industry="Tiny", revenue=1_000_000, channel="api", status="declined"))
        result = _analyze_by_group(
            subs,
            group_field="industry",
            group_fn=lambda s: s["risk_data"]["industry"],
            outcome_fn=lambda s: s["status"] == "bound",
            metric_name="test",
        )
        assert result.passes_threshold is True  # Tiny group ignored
        assert "Tiny" not in result.flagged_groups

    def test_empty_input(self):
        result = _analyze_by_group(
            [],
            group_field="industry",
            group_fn=lambda s: "x",
            outcome_fn=lambda s: True,
            metric_name="test",
        )
        assert result.groups == {}
        assert result.passes_threshold is True


# ---------------------------------------------------------------------------
# analyze_submission_bias (async)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAnalyzeSubmissionBias:
    async def test_returns_four_analyses(self):
        subs = _make_submissions([("Tech", 15, 5), ("Finance", 14, 6)])
        results = await analyze_submission_bias(subs)
        assert len(results) == 4
        fields = {r["group_field"] for r in results}
        assert fields == {"industry", "revenue_band", "security_score_band", "channel"}

    async def test_empty_submissions(self):
        results = await analyze_submission_bias([])
        assert len(results) == 4
        assert all(r["groups"] == {} for r in results)


# ---------------------------------------------------------------------------
# generate_bias_report (async)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestGenerateBiasReport:
    async def test_compliant_report(self):
        subs = _make_submissions([("Tech", 15, 5), ("Finance", 14, 6)])
        report = await generate_bias_report(subs)
        assert report["overall_status"] == "compliant"
        assert report["total_submissions_analyzed"] == 40
        assert "analyses" in report
        assert "eu_ai_act_reference" in report
        assert "Article 9" in report["eu_ai_act_reference"]

    async def test_flagged_report(self):
        subs = _make_submissions([("Tech", 18, 2), ("Retail", 3, 17)])
        report = await generate_bias_report(subs)
        assert report["overall_status"] == "flagged"
        assert "Investigate" in report["recommendation"]

    async def test_report_id_format(self):
        report = await generate_bias_report([])
        assert report["report_id"]  # non-empty
        assert report["generated_at"]  # non-empty
        assert report["period"] == "all_time"

    async def test_claims_param_accepted(self):
        """Claims parameter is accepted for future use."""
        report = await generate_bias_report([], claims=[{"id": "c1"}])
        assert report["overall_status"] == "compliant"


# ---------------------------------------------------------------------------
# _security_score_band
# ---------------------------------------------------------------------------


class TestSecurityScoreBand:
    @pytest.mark.parametrize(
        ("score", "expected"),
        [
            (0.1, "Poor (<0.3)"),
            (0.35, "Fair (0.3-0.5)"),
            (0.6, "Good (0.5-0.7)"),
            (0.8, "Strong (0.7-0.9)"),
            (0.95, "Excellent (0.9+)"),
            (None, "Unknown"),
            ("bad", "Unknown"),
        ],
    )
    def test_bands(self, score, expected):
        assert _security_score_band(score) == expected


# ---------------------------------------------------------------------------
# gap_percentage in group data
# ---------------------------------------------------------------------------


class TestGapPercentage:
    def test_group_data_includes_gap_and_flagged(self):
        subs = _make_submissions([("Tech", 18, 2), ("Retail", 5, 15)])
        result = _analyze_by_group(
            subs,
            group_field="industry",
            group_fn=lambda s: s["risk_data"]["industry"],
            outcome_fn=lambda s: s["status"] == "bound",
            metric_name="test",
        )
        d = result.to_dict()
        for group in d["groups"].values():
            assert "gap_percentage" in group
            assert "flagged" in group
        # The best group has gap 0
        assert d["groups"]["Tech"]["gap_percentage"] == 0.0
        assert d["groups"]["Tech"]["flagged"] is False
        # Retail is flagged with a positive gap
        assert d["groups"]["Retail"]["gap_percentage"] > 0
        assert d["groups"]["Retail"]["flagged"] is True
