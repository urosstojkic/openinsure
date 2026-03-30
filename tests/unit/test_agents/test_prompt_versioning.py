"""Tests for prompt versioning and template loading."""

from __future__ import annotations

import os

import pytest

from openinsure.agents.prompts.versioning import (
    PromptTemplate,
    clear_cache,
    get_prompt_version,
    get_system_preamble,
    list_available_templates,
    load_template,
)


@pytest.fixture(autouse=True)
def _clean_cache():
    """Clear template cache before and after each test."""
    clear_cache()
    yield
    clear_cache()


class TestPromptVersioning:
    """Tests for the prompt versioning module."""

    def test_load_template_triage(self):
        template = load_template("triage", "1.0")
        assert template is not None
        assert template.name == "triage"
        assert template.version == "1.0"
        assert template.source == "yaml"
        assert "Triage Agent" in template.system_preamble

    def test_load_template_underwriting(self):
        template = load_template("underwriting", "1.0")
        assert template is not None
        assert template.name == "underwriting"
        assert "Underwriting Agent" in template.system_preamble

    def test_load_template_claims(self):
        template = load_template("claims", "1.0")
        assert template is not None
        assert template.name == "claims"

    def test_load_template_policy(self):
        template = load_template("policy", "1.0")
        assert template is not None

    def test_load_template_compliance(self):
        template = load_template("compliance", "1.0")
        assert template is not None

    def test_load_template_not_found(self):
        result = load_template("nonexistent_agent", "1.0")
        assert result is None

    def test_load_template_wrong_version(self):
        result = load_template("triage", "99.0")
        assert result is None

    def test_template_caching(self):
        t1 = load_template("triage", "1.0")
        t2 = load_template("triage", "1.0")
        assert t1 is t2  # Same object from cache

    def test_get_prompt_version_default(self):
        # Without env var set, should return "1.0"
        version = get_prompt_version("triage")
        assert version == "1.0"

    def test_get_prompt_version_from_env(self, monkeypatch):
        monkeypatch.setenv("OPENINSURE_PROMPT_VERSION_TRIAGE", "2.0")
        version = get_prompt_version("triage")
        assert version == "2.0"

    def test_get_system_preamble_yaml(self):
        preamble = get_system_preamble("triage", inline_fallback="FALLBACK")
        assert "Triage Agent" in preamble
        assert "FALLBACK" not in preamble

    def test_get_system_preamble_fallback(self):
        preamble = get_system_preamble("nonexistent", inline_fallback="FALLBACK TEXT")
        assert preamble == "FALLBACK TEXT"

    def test_list_available_templates(self):
        templates = list_available_templates()
        assert len(templates) >= 5
        names = [t["name"] for t in templates]
        assert "triage" in names
        assert "underwriting" in names
        assert "claims" in names

    def test_prompt_template_dataclass(self):
        t = PromptTemplate(
            name="test",
            version="1.0",
            system_preamble="You are a test agent.",
        )
        assert t.source == "inline"
        assert t.metadata == {}
        assert t.description == ""
