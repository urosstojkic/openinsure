"""Prompt versioning and template loading for OpenInsure agents.

Supports loading prompt templates from YAML files with version tracking.
Falls back to inline Python prompts when YAML files are unavailable.
Enables A/B testing by switching versions via configuration.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


@dataclass
class PromptTemplate:
    """A versioned prompt template loaded from YAML or inline Python."""

    name: str
    version: str
    system_preamble: str
    description: str = ""
    output_schema_note: str = ""
    source: str = "inline"  # "yaml" or "inline"
    metadata: dict[str, Any] = field(default_factory=dict)


# Cache of loaded templates keyed by (name, version)
_template_cache: dict[tuple[str, str], PromptTemplate] = {}


def _load_yaml_safe(path: Path) -> dict[str, Any]:
    """Load a YAML file, returning empty dict on failure."""
    try:
        import yaml
    except ImportError:
        logger.debug("prompt_versioning.pyyaml_not_installed")
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        logger.warning("prompt_versioning.yaml_load_failed", path=str(path), exc_info=True)
        return {}


def load_template(name: str, version: str = "1.0") -> PromptTemplate | None:
    """Load a prompt template by name and version.

    Looks for ``templates/{name}_v{major}.yaml`` in the prompts package
    directory. Returns ``None`` if not found (caller should use inline
    fallback).
    """
    cache_key = (name, version)
    if cache_key in _template_cache:
        return _template_cache[cache_key]

    # Derive filename: version "1.0" -> v1, "2.0" -> v2
    major = version.split(".", maxsplit=1)[0] if "." in version else version
    yaml_path = _TEMPLATES_DIR / f"{name}_v{major}.yaml"

    if not yaml_path.is_file():
        return None

    data = _load_yaml_safe(yaml_path)
    if not data:
        return None

    template = PromptTemplate(
        name=data.get("name", name),
        version=data.get("version", version),
        system_preamble=data.get("system_preamble", "").strip(),
        description=data.get("description", ""),
        output_schema_note=data.get("output_schema_note", "").strip(),
        source="yaml",
        metadata={
            k: v
            for k, v in data.items()
            if k not in {"name", "version", "system_preamble", "description", "output_schema_note"}
        },
    )
    _template_cache[cache_key] = template
    logger.debug("prompt_versioning.loaded", name=name, version=version, source="yaml")
    return template


def get_prompt_version(agent_name: str) -> str:
    """Get the configured prompt version for an agent.

    Reads from environment variable ``OPENINSURE_PROMPT_VERSION_{AGENT}``
    (e.g. ``OPENINSURE_PROMPT_VERSION_TRIAGE=2.0``).
    Defaults to ``"1.0"`` if not set.
    """
    env_key = f"OPENINSURE_PROMPT_VERSION_{agent_name.upper()}"
    return os.environ.get(env_key, "1.0")


def get_system_preamble(agent_name: str, *, inline_fallback: str) -> str:
    """Get the system preamble for an agent, preferring YAML over inline.

    Args:
        agent_name: The agent name (e.g. "triage", "underwriting").
        inline_fallback: The inline Python string to use if YAML unavailable.

    Returns:
        The system preamble string from YAML template or the inline fallback.
    """
    version = get_prompt_version(agent_name)
    template = load_template(agent_name, version)
    if template:
        return template.system_preamble
    return inline_fallback


def list_available_templates() -> list[dict[str, str]]:
    """List all available YAML prompt templates."""
    results: list[dict[str, str]] = []
    if not _TEMPLATES_DIR.is_dir():
        return results
    for path in sorted(_TEMPLATES_DIR.glob("*.yaml")):
        data = _load_yaml_safe(path)
        if data:
            results.append(
                {
                    "name": data.get("name", path.stem),
                    "version": data.get("version", "unknown"),
                    "file": path.name,
                    "description": data.get("description", ""),
                }
            )
    return results


def clear_cache() -> None:
    """Clear the template cache (useful in tests)."""
    _template_cache.clear()
