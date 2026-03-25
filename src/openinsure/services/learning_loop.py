# mypy: ignore-errors
"""Decision Learning Loop — tracks decision outcomes for continuous improvement.

When an agent makes a decision (triage, quote, bind), and later the outcome is
known (claim filed, policy cancelled, premium collected), this service captures
that feedback so future prompts include historical accuracy context.

Addresses issue #86.
"""

from __future__ import annotations

import statistics
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# In-memory decision outcome store (Azure SQL variant can be added later)
# ---------------------------------------------------------------------------

_decision_outcomes: list[dict[str, Any]] = []
_decision_records: dict[str, dict[str, Any]] = {}


def _reset_store() -> None:
    """Reset the in-memory store — used by tests."""
    _decision_outcomes.clear()
    _decision_records.clear()


class DecisionOutcomeTracker:
    """Tracks decision outcomes for continuous improvement.

    Records the original AI decision and its real-world outcome, then
    computes accuracy metrics and improvement signals that are injected
    back into agent prompts.
    """

    # ------------------------------------------------------------------
    # Record keeping
    # ------------------------------------------------------------------

    async def record_decision(self, decision: dict[str, Any]) -> str:
        """Store an AI decision for later outcome correlation.

        Args:
            decision: Must include ``decision_id``, ``agent_name``,
                ``decision_type`` (triage/quote/bind/claims), and
                ``predicted`` dict with the agent's predictions.

        Returns:
            The decision_id.
        """
        decision_id = str(decision.get("decision_id", ""))
        if not decision_id:
            raise ValueError("decision must include decision_id")

        record = {
            "decision_id": decision_id,
            "agent_name": decision.get("agent_name", "unknown"),
            "decision_type": decision.get("decision_type", "unknown"),
            "predicted": decision.get("predicted", {}),
            "submission_id": decision.get("submission_id"),
            "policy_id": decision.get("policy_id"),
            "claim_id": decision.get("claim_id"),
            "metadata": decision.get("metadata", {}),
            "recorded_at": datetime.now(UTC).isoformat(),
        }
        _decision_records[decision_id] = record
        logger.info(
            "learning_loop.decision_recorded",
            decision_id=decision_id,
            agent=record["agent_name"],
            decision_type=record["decision_type"],
        )
        return decision_id

    async def record_outcome(self, decision_id: str, outcome: dict[str, Any]) -> dict[str, Any]:
        """Record the outcome of a prior AI decision.

        Args:
            decision_id: ID of the original decision.
            outcome: Actual outcome data — e.g. ``{"claim_filed": True,
                "actual_loss": 45000}`` or ``{"policy_renewed": True,
                "actual_premium_collected": 12000}``.

        Returns:
            The stored outcome record with deviation analysis.
        """
        original = _decision_records.get(decision_id)

        predicted = original.get("predicted", {}) if original else {}
        deviation = self._compute_deviation(predicted, outcome)

        record = {
            "decision_id": decision_id,
            "agent_name": original.get("agent_name", "unknown") if original else "unknown",
            "decision_type": original.get("decision_type", "unknown") if original else "unknown",
            "predicted": predicted,
            "actual": outcome,
            "deviation": deviation,
            "recorded_at": datetime.now(UTC).isoformat(),
            "original_decision_at": original.get("recorded_at") if original else None,
        }
        _decision_outcomes.append(record)
        logger.info(
            "learning_loop.outcome_recorded",
            decision_id=decision_id,
            agent=record["agent_name"],
            deviation=deviation,
        )
        return record

    # ------------------------------------------------------------------
    # Analytics
    # ------------------------------------------------------------------

    async def get_accuracy_metrics(
        self,
        agent_name: str,
        period_days: int = 90,
    ) -> dict[str, Any]:
        """How accurate were this agent's predictions?

        Compares predicted risk_score vs actual claims frequency, and
        predicted premium vs actual loss ratio.

        Args:
            agent_name: Agent identifier (e.g. ``"triage"``, ``"underwriting"``).
            period_days: Look-back window in days (default 90).

        Returns:
            Dict with accuracy breakdown: total_decisions, correct_predictions,
            accuracy_rate, avg_deviation, and per-metric breakdowns.
        """
        cutoff = datetime.now(UTC) - timedelta(days=period_days)
        relevant = [
            o
            for o in _decision_outcomes
            if o.get("agent_name") == agent_name and o.get("recorded_at", "") >= cutoff.isoformat()
        ]

        if not relevant:
            return {
                "agent_name": agent_name,
                "period_days": period_days,
                "total_decisions": 0,
                "accuracy_rate": 0.0,
                "avg_deviation": 0.0,
                "metrics": {},
            }

        # Accuracy: a prediction is "correct" if deviation < 20%
        deviations = [abs(o.get("deviation", {}).get("overall_pct", 0.0)) for o in relevant]
        correct = sum(1 for d in deviations if d < 0.20)
        accuracy = correct / len(relevant) if relevant else 0.0
        avg_dev = statistics.mean(deviations) if deviations else 0.0

        # Per-metric breakdowns
        risk_devs = [
            o["deviation"]["risk_score_deviation"] for o in relevant if "risk_score_deviation" in o.get("deviation", {})
        ]
        premium_devs = [
            o["deviation"]["premium_deviation_pct"]
            for o in relevant
            if "premium_deviation_pct" in o.get("deviation", {})
        ]

        metrics: dict[str, Any] = {}
        if risk_devs:
            metrics["risk_score"] = {
                "avg_deviation": round(statistics.mean(risk_devs), 3),
                "sample_size": len(risk_devs),
            }
        if premium_devs:
            metrics["premium"] = {
                "avg_deviation_pct": round(statistics.mean(premium_devs), 3),
                "sample_size": len(premium_devs),
            }

        return {
            "agent_name": agent_name,
            "period_days": period_days,
            "total_decisions": len(relevant),
            "correct_predictions": correct,
            "accuracy_rate": round(accuracy, 3),
            "avg_deviation": round(avg_dev, 3),
            "metrics": metrics,
        }

    async def get_improvement_signals(self, agent_name: str) -> list[dict[str, Any]]:
        """What patterns should the agent adjust for?

        Identifies systematic biases — e.g. "Healthcare submissions
        were underpriced by 15%".

        Args:
            agent_name: Agent identifier.

        Returns:
            List of improvement signal dicts with category, message,
            direction (over/under), and magnitude.
        """
        relevant = [o for o in _decision_outcomes if o.get("agent_name") == agent_name]
        if not relevant:
            return []

        signals: list[dict[str, Any]] = []

        # Group by industry (from metadata)
        industry_groups: dict[str, list[dict[str, Any]]] = {}
        for o in relevant:
            industry = (
                o.get("predicted", {}).get("industry", "") or o.get("actual", {}).get("industry", "") or "unknown"
            )
            industry_groups.setdefault(industry, []).append(o)

        for industry, outcomes in industry_groups.items():
            if industry == "unknown" or len(outcomes) < 2:
                continue

            premium_devs = [
                o["deviation"]["premium_deviation_pct"]
                for o in outcomes
                if "premium_deviation_pct" in o.get("deviation", {})
            ]
            if premium_devs and len(premium_devs) >= 2:
                avg = statistics.mean(premium_devs)
                if abs(avg) > 0.10:  # >10% systematic bias
                    # Positive deviation = actual losses > predicted premium = underpriced
                    direction = "underpriced" if avg > 0 else "overpriced"
                    signals.append(
                        {
                            "category": "pricing_bias",
                            "industry": industry,
                            "message": (
                                f"{industry.replace('_', ' ').title()} submissions were "
                                f"{direction} by {abs(avg) * 100:.0f}%"
                            ),
                            "direction": direction,
                            "magnitude": round(abs(avg), 3),
                            "sample_size": len(premium_devs),
                        }
                    )

            # Claims accuracy
            claim_predictions = [o for o in outcomes if "claim_filed" in o.get("actual", {})]
            if claim_predictions and len(claim_predictions) >= 2:
                predicted_risk = [o.get("predicted", {}).get("risk_score", 5) for o in claim_predictions]
                actual_claims = [1 if o["actual"]["claim_filed"] else 0 for o in claim_predictions]
                avg_predicted_risk = statistics.mean(predicted_risk)
                actual_claim_rate = statistics.mean(actual_claims)
                # Compare: high predicted risk should correlate with high claim rate
                if actual_claim_rate > 0.3 and avg_predicted_risk < 5:
                    signals.append(
                        {
                            "category": "risk_underestimate",
                            "industry": industry,
                            "message": (
                                f"{industry.replace('_', ' ').title()} had {actual_claim_rate * 100:.0f}% "
                                f"claim rate but avg predicted risk was only {avg_predicted_risk:.1f}/10"
                            ),
                            "direction": "under",
                            "magnitude": round(actual_claim_rate, 3),
                            "sample_size": len(claim_predictions),
                        }
                    )

        return signals

    async def get_all_metrics(self, period_days: int = 90) -> dict[str, Any]:
        """Get accuracy metrics for all agents.

        Returns:
            Dict keyed by agent_name with accuracy metrics for each.
        """
        agent_names = {o.get("agent_name", "unknown") for o in _decision_outcomes}
        results: dict[str, Any] = {}
        for agent in sorted(agent_names):
            results[agent] = await self.get_accuracy_metrics(agent, period_days)
        return {
            "period_days": period_days,
            "agents": results,
            "total_outcomes_tracked": len(_decision_outcomes),
            "generated_at": datetime.now(UTC).isoformat(),
        }

    # ------------------------------------------------------------------
    # Prompt context builder
    # ------------------------------------------------------------------

    async def get_prompt_context(self, agent_name: str) -> str:
        """Build a prompt context string with historical accuracy data.

        Suitable for injection into agent prompts so agents are aware
        of their own performance and can self-correct.

        Args:
            agent_name: Agent identifier.

        Returns:
            Multi-line string for prompt injection, or empty string if
            no outcome data exists.
        """
        metrics = await self.get_accuracy_metrics(agent_name)
        signals = await self.get_improvement_signals(agent_name)

        if metrics["total_decisions"] == 0:
            return ""

        lines = [
            "HISTORICAL ACCURACY:",
            f"Your decisions had {metrics['accuracy_rate'] * 100:.0f}% accuracy "
            f"over the last {metrics['period_days']} days "
            f"({metrics['total_decisions']} decisions tracked).",
        ]

        risk_metrics = metrics.get("metrics", {}).get("risk_score", {})
        if risk_metrics:
            lines.append(
                f"Risk score avg deviation: {risk_metrics['avg_deviation']:.2f} "
                f"(sample size: {risk_metrics['sample_size']})"
            )

        premium_metrics = metrics.get("metrics", {}).get("premium", {})
        if premium_metrics:
            pct = premium_metrics["avg_deviation_pct"] * 100
            direction = "below" if pct < 0 else "above"
            lines.append(
                f"Premium predictions were {abs(pct):.0f}% {direction} actual losses "
                f"(sample size: {premium_metrics['sample_size']})"
            )

        for signal in signals:
            lines.append(f"SIGNAL: {signal['message']}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_deviation(
        predicted: dict[str, Any],
        actual: dict[str, Any],
    ) -> dict[str, Any]:
        """Compute deviation between predicted and actual values."""
        deviation: dict[str, Any] = {}

        # Risk score deviation
        pred_risk = predicted.get("risk_score")
        actual_risk = actual.get("actual_risk_score")
        if pred_risk is not None and actual_risk is not None:
            deviation["risk_score_deviation"] = round(float(actual_risk) - float(pred_risk), 3)

        # Premium deviation
        pred_premium = predicted.get("premium") or predicted.get("recommended_premium")
        actual_loss = actual.get("actual_loss") or actual.get("actual_premium_collected")
        if pred_premium and actual_loss:
            pred_f = float(pred_premium)
            actual_f = float(actual_loss)
            if pred_f > 0:
                deviation["premium_deviation_pct"] = round((actual_f - pred_f) / pred_f, 3)

        # Overall percentage deviation (average of available metrics)
        pct_values = [abs(v) for k, v in deviation.items() if k.endswith(("_pct", "_deviation"))]
        deviation["overall_pct"] = round(statistics.mean(pct_values), 3) if pct_values else 0.0

        return deviation


# Module-level singleton
_tracker: DecisionOutcomeTracker | None = None


def get_decision_tracker() -> DecisionOutcomeTracker:
    """Return the singleton DecisionOutcomeTracker."""
    global _tracker  # noqa: PLW0603
    if _tracker is None:
        _tracker = DecisionOutcomeTracker()
    return _tracker
