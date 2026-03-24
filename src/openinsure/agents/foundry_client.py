"""Client for invoking OpenInsure agents hosted in Microsoft Foundry.

Uses the azure-ai-projects SDK v2 to call agents via the Responses API.
Falls back to local stub agents when Foundry is unavailable.

Instruments the OpenAI SDK with OpenTelemetry so every Foundry invocation
is recorded as a trace span in Application Insights.
"""

import json
import time
from typing import Any

import structlog

from openinsure.config import get_settings

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# OpenTelemetry instrumentation (best-effort, non-blocking)
# ---------------------------------------------------------------------------
_otel_configured = False


def _configure_otel_once() -> None:
    """Set up Azure Monitor + OpenAI instrumentation once per process."""
    global _otel_configured  # noqa: PLW0603
    if _otel_configured:
        return
    _otel_configured = True
    try:
        from azure.ai.projects import AIProjectClient
        from azure.identity import DefaultAzureCredential

        settings = get_settings()
        if not settings.foundry_project_endpoint:
            return

        client = AIProjectClient(
            endpoint=settings.foundry_project_endpoint,
            credential=DefaultAzureCredential(),
        )
        conn_str = client.telemetry.get_application_insights_connection_string()

        from azure.monitor.opentelemetry import configure_azure_monitor
        from opentelemetry.instrumentation.openai_v2 import OpenAIInstrumentor

        configure_azure_monitor(connection_string=conn_str)
        OpenAIInstrumentor().instrument()  # type: ignore[no-untyped-call]
        logger.info("foundry_client.otel_configured")
    except Exception as exc:
        # Non-fatal — tracing is best-effort
        logger.debug("foundry_client.otel_skipped", reason=str(exc))


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
                # Best-effort OTEL instrumentation
                _configure_otel_once()
            except Exception as e:
                logger.warning("foundry_client.init_failed", error=str(e))
                self._enabled = False

    @property
    def is_available(self) -> bool:
        return self._enabled and self._openai is not None

    @staticmethod
    def _parse_response(text: str) -> dict | str:
        """Parse agent response text, attempting JSON extraction.

        Strips markdown code fences before parsing. Returns the parsed
        dict/list on success, or the original text on failure.
        """
        try:
            clean = text.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
                clean = clean.rsplit("```", 1)[0]
            return json.loads(clean)
        except (json.JSONDecodeError, ValueError):
            return text

    async def create_conversation(self) -> str | None:
        """Create a new Foundry conversation for multi-turn interactions.

        Returns conversation ID or None if Foundry is unavailable.
        """
        if not self.is_available or self._openai is None:
            return None

        try:
            conversation = self._openai.conversations.create()
            logger.info("foundry_client.conversation_created", conversation_id=conversation.id)
            return conversation.id
        except Exception as e:
            logger.exception("foundry_client.create_conversation_failed", error=str(e))
            return None

    async def invoke(self, agent_name: str, message: str, *, conversation_id: str | None = None) -> dict[str, Any]:
        """Invoke a Foundry agent and return parsed response.

        Always returns a dict with these keys:
        - ``response``: Parsed agent response (dict or str)
        - ``source``: ``"foundry"`` or ``"fallback"``
        - ``raw``: Raw text from the agent (empty string on fallback)
        - ``execution_time_ms``: Latency in milliseconds (0 on fast-fail)
        - ``error``: Error message if present, otherwise absent

        The consistent shape prevents downstream code from hitting
        KeyError on missing fields.

        If *conversation_id* is provided the message is sent within that
        conversation, enabling multi-turn context retention.
        """
        if conversation_id is not None:
            return await self.invoke_in_conversation(agent_name, message, conversation_id)

        base: dict[str, Any] = {
            "response": "",
            "source": "fallback",
            "raw": "",
            "execution_time_ms": 0,
        }

        if not self.is_available:
            return {**base, "error": "Foundry not available"}

        start = time.monotonic()
        try:
            if self._openai is None:
                return {**base, "error": "OpenAI client not initialized"}
            response = self._openai.responses.create(
                input=[{"role": "user", "content": message}],
                extra_body={"agent": {"name": agent_name, "type": "agent_reference"}},
            )
            text = response.output_text
            elapsed_ms = int((time.monotonic() - start) * 1000)

            return {
                "source": "foundry",
                "raw": text,
                "execution_time_ms": elapsed_ms,
                "response": self._parse_response(text),
            }

        except Exception as e:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.exception("foundry_client.invoke_failed", agent=agent_name, error=str(e))
            return {**base, "execution_time_ms": elapsed_ms, "error": str(e)}

    async def invoke_in_conversation(self, agent_name: str, message: str, conversation_id: str) -> dict[str, Any]:
        """Invoke a Foundry agent within an existing conversation.

        Enables multi-turn interactions where the agent retains context
        from previous messages in the same conversation.

        Returns the same dict shape as :meth:`invoke`.
        """
        base: dict[str, Any] = {
            "response": "",
            "source": "fallback",
            "raw": "",
            "execution_time_ms": 0,
        }

        if not self.is_available:
            return {**base, "error": "Foundry not available"}

        start = time.monotonic()
        try:
            if self._openai is None:
                return {**base, "error": "OpenAI client not initialized"}
            response = self._openai.responses.create(
                conversation=conversation_id,
                extra_body={"agent_reference": {"name": agent_name, "type": "agent_reference"}},
                input=message,
            )
            text = response.output_text
            elapsed_ms = int((time.monotonic() - start) * 1000)

            return {
                "source": "foundry",
                "raw": text,
                "execution_time_ms": elapsed_ms,
                "response": self._parse_response(text),
            }

        except Exception as e:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.exception(
                "foundry_client.invoke_in_conversation_failed",
                agent=agent_name,
                conversation_id=conversation_id,
                error=str(e),
            )
            return {**base, "execution_time_ms": elapsed_ms, "error": str(e)}


# Singleton
_client: FoundryAgentClient | None = None


def get_foundry_client() -> FoundryAgentClient:
    global _client  # noqa: PLW0603
    if _client is None:
        _client = FoundryAgentClient()
    return _client
