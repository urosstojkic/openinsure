"""EU AI Act bias monitoring engine.

Implements Article 9 (risk management) and Article 10 (data governance)
requirements for detecting and reporting bias in AI decisions.

Methods:
- Statistical parity: approval rate should be similar across groups
- 4/5ths rule: ratio of lowest to highest group rate must be >= 0.8
- Disparate impact: identify groups with significantly different outcomes
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from collections.abc import Callable

logger = structlog.get_logger()


class BiasAnalysisResult:
    """Result of a single group-based bias analysis."""

    def __init__(self) -> None:
        self.metric_name: str = ""
        self.group_field: str = ""  # e.g., "industry", "revenue_band", "state"
        self.groups: dict[str, dict[str, Any]] = {}  # group_name → {total, positive, rate}
        self.four_fifths_ratio: float = 1.0
        self.passes_threshold: bool = True
        self.flagged_groups: list[str] = []
        self.timestamp: str = datetime.now(UTC).isoformat()

    def to_dict(self) -> dict[str, Any]:
        # Compute max rate among sufficiently-sized groups for gap calculation
        max_rate = 0.0
        for data in self.groups.values():
            if data.get("total", 0) >= _MIN_SAMPLE_SIZE and data["rate"] > max_rate:
                max_rate = data["rate"]

        groups_with_gap: dict[str, dict[str, Any]] = {}
        for name, data in self.groups.items():
            gap_pct = round((max_rate - data["rate"]) * 100, 2) if max_rate > 0 else 0.0
            groups_with_gap[name] = {
                **data,
                "gap_percentage": gap_pct,
                "flagged": name in self.flagged_groups,
            }

        return {
            "metric": self.metric_name,
            "group_field": self.group_field,
            "groups": groups_with_gap,
            "four_fifths_ratio": round(self.four_fifths_ratio, 4),
            "passes_threshold": self.passes_threshold,
            "flagged_groups": self.flagged_groups,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def analyze_submission_bias(submissions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Analyze submission decisions for bias across multiple dimensions."""
    results: list[dict[str, Any]] = []

    # Analyze by industry
    results.append(
        _analyze_by_group(
            submissions,
            group_field="industry",
            group_fn=lambda s: (s.get("risk_data") or {}).get("industry", "Unknown"),
            outcome_fn=lambda s: s.get("status") in ("bound", "quoted"),
            metric_name="Approval Rate by Industry",
        ).to_dict()
    )

    # Analyze by revenue band
    results.append(
        _analyze_by_group(
            submissions,
            group_field="revenue_band",
            group_fn=lambda s: _revenue_band((s.get("risk_data") or {}).get("annual_revenue", 0)),
            outcome_fn=lambda s: s.get("status") in ("bound", "quoted"),
            metric_name="Approval Rate by Revenue Band",
        ).to_dict()
    )

    # Analyze by security score band
    results.append(
        _analyze_by_group(
            submissions,
            group_field="security_score_band",
            group_fn=lambda s: _security_score_band((s.get("risk_data") or {}).get("security_score")),
            outcome_fn=lambda s: s.get("status") in ("bound", "quoted"),
            metric_name="Approval Rate by Security Score",
        ).to_dict()
    )

    # Analyze by channel
    results.append(
        _analyze_by_group(
            submissions,
            group_field="channel",
            group_fn=lambda s: s.get("channel", "unknown"),
            outcome_fn=lambda s: s.get("status") in ("bound", "quoted"),
            metric_name="Approval Rate by Channel",
        ).to_dict()
    )

    return results


async def generate_bias_report(
    submissions: list[dict[str, Any]],
    claims: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Generate a comprehensive bias report for compliance."""
    analyses = await analyze_submission_bias(submissions)

    any_flagged = any(a.get("flagged_groups") for a in analyses)

    if any_flagged:
        logger.warning(
            "bias_flagged",
            flagged_analyses=[a["metric"] for a in analyses if a.get("flagged_groups")],
        )

    return {
        "report_id": datetime.now(UTC).strftime("%Y%m%d-%H%M%S"),
        "generated_at": datetime.now(UTC).isoformat(),
        "period": "all_time",
        "total_submissions_analyzed": len(submissions),
        "analyses": analyses,
        "overall_status": "flagged" if any_flagged else "compliant",
        "eu_ai_act_reference": "Article 9 (Risk Management), Article 10 (Data Governance)",
        "recommendation": (
            "Investigate flagged groups for potential disparate impact"
            if any_flagged
            else "No disparate impact detected — monitoring continues"
        ),
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Minimum sample size for a group to be included in 4/5ths ratio analysis
_MIN_SAMPLE_SIZE = 10


def _analyze_by_group(
    items: list[dict[str, Any]],
    *,
    group_field: str,
    group_fn: Callable[[dict[str, Any]], str],
    outcome_fn: Callable[[dict[str, Any]], bool],
    metric_name: str,
) -> BiasAnalysisResult:
    """Generic group-based bias analysis using the 4/5ths rule."""
    result = BiasAnalysisResult()
    result.metric_name = metric_name
    result.group_field = group_field

    # Tally counts per group
    groups: dict[str, dict[str, int]] = {}
    for item in items:
        group = str(group_fn(item))
        if group not in groups:
            groups[group] = {"total": 0, "positive": 0}
        groups[group]["total"] += 1
        if outcome_fn(item):
            groups[group]["positive"] += 1

    # Calculate rates
    for name, data in groups.items():
        rate = data["positive"] / data["total"] if data["total"] > 0 else 0.0
        result.groups[name] = {
            "total": data["total"],
            "positive": data["positive"],
            "rate": round(rate, 4),
        }

    # 4/5ths rule: only include groups with sufficient sample size
    rates = [g["rate"] for g in result.groups.values() if g["total"] >= _MIN_SAMPLE_SIZE]
    if len(rates) >= 2:
        max_rate = max(rates)
        min_rate = min(rates)
        result.four_fifths_ratio = min_rate / max_rate if max_rate > 0 else 1.0
        result.passes_threshold = result.four_fifths_ratio >= 0.8

        # Flag groups whose rate falls below 80 % of the highest rate
        threshold = max_rate * 0.8
        for name, data in result.groups.items():
            if data["total"] >= _MIN_SAMPLE_SIZE and data["rate"] < threshold:
                result.flagged_groups.append(name)

    return result


def _revenue_band(revenue: Any) -> str:
    """Classify revenue into bands for group analysis."""
    try:
        rev = float(revenue)
    except (TypeError, ValueError):
        return "Unknown"
    if rev < 1_000_000:
        return "<$1M"
    if rev < 5_000_000:
        return "$1M-$5M"
    if rev < 25_000_000:
        return "$5M-$25M"
    if rev < 100_000_000:
        return "$25M-$100M"
    return "$100M+"


def _security_score_band(score: Any) -> str:
    """Classify a 0–1 security score into human-readable bands."""
    if score is None:
        return "Unknown"
    try:
        s = float(score)
    except (TypeError, ValueError):
        return "Unknown"
    if s < 0.3:
        return "Poor (<0.3)"
    if s < 0.5:
        return "Fair (0.3-0.5)"
    if s < 0.7:
        return "Good (0.5-0.7)"
    if s < 0.9:
        return "Strong (0.7-0.9)"
    return "Excellent (0.9+)"
