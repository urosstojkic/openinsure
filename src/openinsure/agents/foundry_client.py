# mypy: ignore-errors
"""Client for invoking OpenInsure agents hosted in Microsoft Foundry.

Uses the azure-ai-projects SDK v2 to call agents via the Responses API.
Falls back to local stub agents when Foundry is unavailable.

Instruments the OpenAI SDK with OpenTelemetry so every Foundry invocation
is recorded as a trace span in Application Insights.

Includes retry with exponential backoff, circuit breaker, and configurable
timeout to handle transient Foundry failures gracefully.
"""

import asyncio
import json
import time
from typing import Any

import structlog

from openinsure.config import get_settings

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Default resilience settings
# ---------------------------------------------------------------------------
DEFAULT_TIMEOUT_SECONDS = 60
MAX_RETRIES = 2
RETRY_BASE_DELAY_SECONDS = 1.0
CIRCUIT_BREAKER_FAILURE_THRESHOLD = 5
CIRCUIT_BREAKER_RECOVERY_SECONDS = 60

# HTTP status codes considered transient (worth retrying)
_TRANSIENT_STATUS_CODES = {"429", "500", "503"}


class CircuitBreaker:
    """Simple circuit breaker to prevent cascading failures.

    After *failure_threshold* consecutive failures the breaker opens and
    all calls are short-circuited for *recovery_timeout* seconds.  After
    the recovery window the breaker enters a half-open state and allows
    one probe request through.
    """

    def __init__(
        self,
        failure_threshold: int = CIRCUIT_BREAKER_FAILURE_THRESHOLD,
        recovery_timeout: float = CIRCUIT_BREAKER_RECOVERY_SECONDS,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._consecutive_failures = 0
        self._last_failure_time: float = 0.0
        self._state: str = "closed"  # closed | open | half_open

    @property
    def state(self) -> str:
        # Auto-transition open → half_open after recovery window
        if self._state == "open":
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self._recovery_timeout:
                self._state = "half_open"
                logger.info(
                    "circuit_breaker.half_open",
                    elapsed_s=round(elapsed, 1),
                    recovery_timeout=self._recovery_timeout,
                )
        return self._state

    @property
    def is_open(self) -> bool:
        return self.state == "open"

    def record_success(self) -> None:
        prev = self._state
        self._consecutive_failures = 0
        self._state = "closed"
        if prev in ("open", "half_open"):
            logger.info("circuit_breaker.closed", previous_state=prev)

    def record_failure(self) -> None:
        self._consecutive_failures += 1
        self._last_failure_time = time.monotonic()
        if self._consecutive_failures >= self._failure_threshold and self._state != "open":
            self._state = "open"
            logger.warning(
                "circuit_breaker.opened",
                consecutive_failures=self._consecutive_failures,
                recovery_timeout=self._recovery_timeout,
            )


def _is_transient_error(exc: Exception) -> bool:
    """Return True if *exc* represents a transient/retryable failure."""
    err_str = str(exc).lower()
    type_name = type(exc).__name__

    # Timeout-related
    if "timeout" in err_str or "timed out" in err_str:
        return True
    if "Timeout" in type_name or "TimeoutError" in type_name:
        return True

    # Connection errors
    if "ConnectionError" in type_name or "connection" in err_str:
        return True

    # HTTP status codes embedded in error messages
    exc_upper = str(exc)
    for code in _TRANSIENT_STATUS_CODES:
        if code in exc_upper:
            return True

    # openai library specific attributes
    if hasattr(exc, "status_code"):
        if str(getattr(exc, "status_code", "")) in _TRANSIENT_STATUS_CODES:
            return True

    return False


def validate_agent_response(
    response: dict[str, Any],
    required_keys: list[str] | None = None,
) -> tuple[bool, list[str]]:
    """Check that an agent response dict has the expected shape.

    Returns ``(is_valid, issues)`` — callers should log *issues* as
    warnings but **never** crash.
    """
    issues: list[str] = []

    if not isinstance(response, dict):
        return False, [f"Expected dict, got {type(response).__name__}"]

    if "parse_error" in response:
        issues.append(f"Parse error: {response['parse_error']}")

    if required_keys:
        for key in required_keys:
            if key not in response:
                issues.append(f"Missing required key: {key}")

    if issues:
        logger.warning(
            "foundry_client.response_validation_failed",
            issues=issues,
        )

    return len(issues) == 0, issues


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
    """Calls Foundry-hosted agents with retry, circuit breaker, and timeout."""

    def __init__(
        self,
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = MAX_RETRIES,
        circuit_breaker: CircuitBreaker | None = None,
    ) -> None:
        settings = get_settings()
        self._enabled = bool(settings.foundry_project_endpoint)
        self._openai = None
        self._timeout = timeout
        self._max_retries = max_retries
        self._circuit_breaker = circuit_breaker or CircuitBreaker()

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
        """True when the OpenAI client is initialised and circuit is not open."""
        return self._enabled and self._openai is not None and not self._circuit_breaker.is_open

    @property
    def circuit_breaker(self) -> CircuitBreaker:
        return self._circuit_breaker

    @staticmethod
    def _parse_response(text: str) -> dict[str, Any]:
        """Parse agent response text, attempting JSON extraction.

        Strips markdown code fences before parsing.  Always returns a
        dict — on JSON failure the dict contains ``raw_text`` and
        ``parse_error`` keys so callers never crash on malformed output.
        """
        if not text or not text.strip():
            return {"raw_text": "", "parse_error": "Empty response from agent"}

        try:
            clean = text.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
                clean = clean.rsplit("```", 1)[0]
            parsed = json.loads(clean)
            if isinstance(parsed, dict):
                return parsed
            # Non-dict JSON (list, int, etc.) — wrap so callers always get a dict
            return {"data": parsed, "raw_text": text}
        except (json.JSONDecodeError, ValueError) as exc:
            return {"raw_text": text, "parse_error": str(exc)}

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

    # ------------------------------------------------------------------
    # Core invocation with retry + circuit breaker
    # ------------------------------------------------------------------

    async def invoke(
        self,
        agent_name: str,
        message: str,
        *,
        conversation_id: str | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Invoke a Foundry agent and return parsed response.

        Always returns a dict with these keys:
        - ``response``: Parsed agent response (always a dict)
        - ``source``: ``"foundry"`` or ``"fallback"``
        - ``raw``: Raw text from the agent (empty string on fallback)
        - ``execution_time_ms``: Latency in milliseconds (0 on fast-fail)
        - ``error``: Error message if present, otherwise absent

        Includes retry with exponential backoff for transient errors
        and a circuit breaker to avoid cascading failures.

        If *conversation_id* is provided the message is sent within that
        conversation, enabling multi-turn context retention.
        """
        if conversation_id is not None:
            return await self.invoke_in_conversation(agent_name, message, conversation_id, timeout=timeout)

        base: dict[str, Any] = {
            "response": {},
            "source": "fallback",
            "raw": "",
            "execution_time_ms": 0,
        }

        if not self._enabled or self._openai is None:
            return {**base, "error": "Foundry not available"}

        if self._circuit_breaker.is_open:
            logger.warning(
                "foundry_client.circuit_breaker_open",
                agent=agent_name,
            )
            return {**base, "error": "Circuit breaker open — Foundry temporarily bypassed"}

        effective_timeout = timeout if timeout is not None else self._timeout
        start = time.monotonic()
        last_error: Exception | None = None

        for attempt in range(1 + self._max_retries):
            try:
                response = self._openai.responses.create(
                    input=[{"role": "user", "content": message}],
                    extra_body={
                        "agent_reference": {
                            "name": agent_name,
                            "type": "agent_reference",
                        }
                    },
                    timeout=effective_timeout,
                )
                text = response.output_text
                elapsed_ms = int((time.monotonic() - start) * 1000)

                self._circuit_breaker.record_success()
                return {
                    "source": "foundry",
                    "raw": text,
                    "execution_time_ms": elapsed_ms,
                    "response": self._parse_response(text),
                }

            except Exception as exc:
                last_error = exc
                is_last = attempt >= self._max_retries

                if not is_last and _is_transient_error(exc):
                    delay = RETRY_BASE_DELAY_SECONDS * (2**attempt)  # 1s, 2s
                    logger.warning(
                        "foundry_client.retrying",
                        agent=agent_name,
                        attempt=attempt + 1,
                        max_retries=self._max_retries,
                        delay_s=delay,
                        error=str(exc),
                    )
                    await asyncio.sleep(delay)
                    continue

                # Permanent error or last retry exhausted
                self._circuit_breaker.record_failure()
                elapsed_ms = int((time.monotonic() - start) * 1000)
                logger.exception(
                    "foundry_client.invoke_failed",
                    agent=agent_name,
                    attempt=attempt + 1,
                    error=str(exc),
                )
                return {
                    **base,
                    "execution_time_ms": elapsed_ms,
                    "error": str(exc),
                }

        # Should be unreachable, but guard against it
        self._circuit_breaker.record_failure()
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return {**base, "execution_time_ms": elapsed_ms, "error": str(last_error)}

    async def invoke_in_conversation(
        self,
        agent_name: str,
        message: str,
        conversation_id: str,
        *,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Invoke a Foundry agent within an existing conversation.

        Enables multi-turn interactions where the agent retains context
        from previous messages in the same conversation.

        Returns the same dict shape as :meth:`invoke`.  Includes the same
        retry and circuit-breaker behaviour.
        """
        base: dict[str, Any] = {
            "response": {},
            "source": "fallback",
            "raw": "",
            "execution_time_ms": 0,
        }

        if not self._enabled or self._openai is None:
            return {**base, "error": "Foundry not available"}

        if self._circuit_breaker.is_open:
            logger.warning(
                "foundry_client.circuit_breaker_open",
                agent=agent_name,
                conversation_id=conversation_id,
            )
            return {**base, "error": "Circuit breaker open — Foundry temporarily bypassed"}

        effective_timeout = timeout if timeout is not None else self._timeout
        start = time.monotonic()
        last_error: Exception | None = None

        for attempt in range(1 + self._max_retries):
            try:
                response = self._openai.responses.create(
                    conversation=conversation_id,
                    extra_body={
                        "agent_reference": {
                            "name": agent_name,
                            "type": "agent_reference",
                        }
                    },
                    input=message,
                    timeout=effective_timeout,
                )
                text = response.output_text
                elapsed_ms = int((time.monotonic() - start) * 1000)

                self._circuit_breaker.record_success()
                return {
                    "source": "foundry",
                    "raw": text,
                    "execution_time_ms": elapsed_ms,
                    "response": self._parse_response(text),
                }

            except Exception as exc:
                last_error = exc
                is_last = attempt >= self._max_retries

                if not is_last and _is_transient_error(exc):
                    delay = RETRY_BASE_DELAY_SECONDS * (2**attempt)
                    logger.warning(
                        "foundry_client.retrying",
                        agent=agent_name,
                        conversation_id=conversation_id,
                        attempt=attempt + 1,
                        max_retries=self._max_retries,
                        delay_s=delay,
                        error=str(exc),
                    )
                    await asyncio.sleep(delay)
                    continue

                self._circuit_breaker.record_failure()
                elapsed_ms = int((time.monotonic() - start) * 1000)
                logger.exception(
                    "foundry_client.invoke_in_conversation_failed",
                    agent=agent_name,
                    conversation_id=conversation_id,
                    attempt=attempt + 1,
                    error=str(exc),
                )
                return {
                    **base,
                    "execution_time_ms": elapsed_ms,
                    "error": str(exc),
                }

        self._circuit_breaker.record_failure()
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return {**base, "execution_time_ms": elapsed_ms, "error": str(last_error)}


# Singleton
_client: FoundryAgentClient | None = None


def get_foundry_client() -> FoundryAgentClient:
    global _client  # noqa: PLW0603
    if _client is None:
        _client = FoundryAgentClient()
    return _client
