"""Bias Detection and Monitoring for EU AI Act compliance.

Implements Art. 9 (Risk Management) and Art. 10 (Data Governance) requirements.
Monitors AI-driven insurance decisions for disparate impact across
demographic groups using the 4/5ths (80 %) rule.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()

_FOUR_FIFTHS_THRESHOLD = 0.80


class BiasMetric(BaseModel):
    """A single bias measurement for one demographic group."""

    metric_name: str = Field(..., description="Name of the metric being measured")
    demographic_group: str = Field(..., description="Demographic group label, e.g. 'age:25-34'")
    observed_rate: float = Field(..., ge=0.0, le=1.0, description="Observed favorable-outcome rate for this group")
    expected_rate: float = Field(..., ge=0.0, le=1.0, description="Expected (reference-group) favorable-outcome rate")
    disparate_impact_ratio: float = Field(
        ...,
        description="Ratio of observed to expected rate; <0.80 triggers a flag",
    )
    flagged: bool = Field(..., description="True when the 4/5ths rule is violated")


class BiasReport(BaseModel):
    """Aggregated bias analysis report for a decision type over a time period."""

    report_id: UUID = Field(default_factory=uuid4)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    decision_type: str = Field(..., description="Type of decision analysed, e.g. 'quote_decision'")
    period_start: datetime
    period_end: datetime
    metrics: list[BiasMetric] = Field(default_factory=list)
    summary: str = Field(default="", description="Human-readable summary of findings")
    recommendations: list[str] = Field(
        default_factory=list,
        description="Actionable recommendations for bias mitigation",
    )


class BiasMonitor:
    """Monitors AI decisions for disparate impact.

    In production, this reads from the Decision Record Store / data warehouse.
    This reference implementation operates on in-memory decision data.
    """

    def __init__(self) -> None:
        self._decisions: list[dict[str, Any]] = []

    def record_decision(self, decision: dict[str, Any]) -> None:
        """Ingest a decision for later bias analysis.

        Expected keys:
            decision_type  – e.g. "quote_decision"
            demographic_group – e.g. "age:25-34"
            outcome – "favorable" | "adverse"
            timestamp – ISO-8601 string
        """
        self._decisions.append(decision)

    # ------------------------------------------------------------------
    # Core analysis
    # ------------------------------------------------------------------

    async def analyze_outcomes(
        self,
        decision_type: str,
        *,
        period_start: datetime | None = None,
        period_end: datetime | None = None,
    ) -> dict[str, dict[str, float]]:
        """Compute favorable-outcome rates per demographic group.

        Returns ``{group: {"favorable": count, "total": count, "rate": float}}``.
        """
        filtered = [d for d in self._decisions if d.get("decision_type") == decision_type]
        if period_start:
            filtered = [d for d in filtered if d.get("timestamp", "") >= period_start.isoformat()]
        if period_end:
            filtered = [d for d in filtered if d.get("timestamp", "") <= period_end.isoformat()]

        groups: dict[str, dict[str, float]] = defaultdict(lambda: {"favorable": 0.0, "total": 0.0, "rate": 0.0})
        for d in filtered:
            group = d.get("demographic_group", "unknown")
            groups[group]["total"] += 1
            if d.get("outcome") == "favorable":
                groups[group]["favorable"] += 1

        for stats in groups.values():
            stats["rate"] = stats["favorable"] / stats["total"] if stats["total"] > 0 else 0.0

        return dict(groups)

    async def check_disparate_impact(
        self,
        outcome_rates: dict[str, dict[str, float]],
    ) -> list[BiasMetric]:
        """Apply the 4/5ths rule across all groups.

        The reference group is the one with the highest favorable-outcome rate.
        Any group whose rate is below 80 % of the reference rate is flagged.
        """
        if not outcome_rates:
            return []

        # Determine the reference (highest) rate
        reference_rate = max(g["rate"] for g in outcome_rates.values())
        if reference_rate == 0.0:
            return []

        metrics: list[BiasMetric] = []
        for group, stats in outcome_rates.items():
            ratio = stats["rate"] / reference_rate
            flagged = ratio < _FOUR_FIFTHS_THRESHOLD
            metrics.append(
                BiasMetric(
                    metric_name="favorable_outcome_rate",
                    demographic_group=group,
                    observed_rate=round(stats["rate"], 4),
                    expected_rate=round(reference_rate, 4),
                    disparate_impact_ratio=round(ratio, 4),
                    flagged=flagged,
                )
            )
            if flagged:
                logger.warning(
                    "bias_monitor.disparate_impact_detected",
                    group=group,
                    ratio=round(ratio, 4),
                    threshold=_FOUR_FIFTHS_THRESHOLD,
                )

        return metrics

    # ------------------------------------------------------------------
    # Report generation
    # ------------------------------------------------------------------

    async def generate_report(
        self,
        decision_type: str,
        period_start: datetime,
        period_end: datetime,
    ) -> BiasReport:
        """Produce a full :class:`BiasReport` for a decision type and period."""
        outcome_rates = await self.analyze_outcomes(decision_type, period_start=period_start, period_end=period_end)
        metrics = await self.check_disparate_impact(outcome_rates)

        flagged_groups = [m.demographic_group for m in metrics if m.flagged]
        if flagged_groups:
            summary = (
                f"Disparate impact detected for {len(flagged_groups)} group(s): "
                f"{', '.join(flagged_groups)}. "
                "Immediate review recommended per EU AI Act Art. 9."
            )
            recommendations = [
                "Review decision model inputs for proxy discrimination.",
                "Conduct root-cause analysis on flagged demographic groups.",
                "Consider re-calibrating rating factors that correlate with protected characteristics.",
                "Engage compliance officer for Art. 9 risk-management review.",
                "Document remediation actions in the decision record store.",
            ]
        else:
            summary = "No disparate impact detected. All groups are within the 4/5ths threshold."
            recommendations = [
                "Continue routine monitoring on the standard schedule.",
            ]

        return BiasReport(
            decision_type=decision_type,
            period_start=period_start,
            period_end=period_end,
            metrics=metrics,
            summary=summary,
            recommendations=recommendations,
        )
