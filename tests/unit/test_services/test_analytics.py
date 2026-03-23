"""Tests for the analytics endpoints."""

from __future__ import annotations


class TestAnalyticsPrompt:
    """Test the analytics prompt builder."""

    def test_build_analytics_prompt(self) -> None:
        from openinsure.api.analytics import build_analytics_prompt

        metrics = {"submissions": {"total": 100, "bound": 30}}
        prompt = build_analytics_prompt(metrics, "last_12_months")
        assert "OpenInsure Analytics Agent" in prompt
        assert "last_12_months" in prompt
        assert "100" in prompt

    def test_build_analytics_prompt_empty_metrics(self) -> None:
        from openinsure.api.analytics import build_analytics_prompt

        prompt = build_analytics_prompt({}, "Q1_2025")
        assert "Q1_2025" in prompt
        assert "RESPOND WITH JSON" in prompt
