"""Client for invoking OpenInsure agents hosted in Microsoft Foundry.

Uses the azure-ai-projects SDK v2 to call agents via the Responses API.
Falls back to local stub agents when Foundry is unavailable.
"""

import json
from typing import Any

import structlog

from openinsure.config import get_settings

logger = structlog.get_logger()


class FoundryAgentClient:
    """Calls Foundry-hosted agents."""

    def __init__(self) -> None:
        settings = get_settings()
        self._enabled = bool(settings.foundry_project_endpoint)
        self._openai = None

        if self._enabled:
            try:
                from azure.ai.projects import AIProjectClient
                from azure.identity import DefaultAzureCredential

                client = AIProjectClient(
                    endpoint=settings.foundry_project_endpoint,
                    credential=DefaultAzureCredential(),
                )
                self._openai = client.get_openai_client()
                logger.info("foundry_client.connected", endpoint=settings.foundry_project_endpoint)
            except Exception as e:
                logger.warning("foundry_client.init_failed", error=str(e))
                self._enabled = False

    @property
    def is_available(self) -> bool:
        return self._enabled and self._openai is not None

    async def invoke(self, agent_name: str, message: str) -> dict[str, Any]:
        """Invoke a Foundry agent and return parsed response.

        Returns dict with at minimum: {"response": str, "source": "foundry"|"fallback"}
        """
        if not self.is_available:
            return {"response": "", "source": "fallback", "error": "Foundry not available"}

        try:
            if self._openai is None:
                return {"response": "", "source": "fallback", "error": "OpenAI client not initialized"}
            response = self._openai.responses.create(
                input=[{"role": "user", "content": message}],
                extra_body={"agent_reference": {"name": agent_name, "type": "agent_reference"}},
            )
            text = response.output_text

            # Try to parse as JSON
            try:
                # Strip markdown code fences if present
                clean = text.strip()
                if clean.startswith("```"):
                    clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
                    clean = clean.rsplit("```", 1)[0]
                parsed = json.loads(clean)
                return {"response": parsed, "source": "foundry", "raw": text}
            except (json.JSONDecodeError, ValueError):
                return {"response": text, "source": "foundry", "raw": text}

        except Exception as e:
            logger.exception("foundry_client.invoke_failed", agent=agent_name, error=str(e))
            return {"response": "", "source": "fallback", "error": str(e)}


# Singleton
_client: FoundryAgentClient | None = None


def get_foundry_client() -> FoundryAgentClient:
    global _client  # noqa: PLW0603
    if _client is None:
        _client = FoundryAgentClient()
    return _client
