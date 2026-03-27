"""Tests for foundry_client.py — retry, circuit breaker, timeout, and response parsing."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from openinsure.agents.foundry_client import (
    CircuitBreaker,
    FoundryAgentClient,
    _is_transient_error,
    validate_agent_response,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client(
    openai_mock: Any = None,
    *,
    timeout: float = 5,
    max_retries: int = 2,
    circuit_breaker: CircuitBreaker | None = None,
) -> FoundryAgentClient:
    """Build a FoundryAgentClient with mocked internals."""
    with patch("openinsure.agents.foundry_client.get_settings") as gs:
        gs.return_value = SimpleNamespace(foundry_project_endpoint="")
        client = FoundryAgentClient(
            timeout=timeout,
            max_retries=max_retries,
            circuit_breaker=circuit_breaker,
        )
    client._enabled = True
    client._openai = openai_mock or MagicMock()
    return client


def _openai_ok(text: str = '{"risk_score": 5}') -> MagicMock:
    mock = MagicMock()
    mock.responses.create.return_value = SimpleNamespace(output_text=text)
    return mock


# ---------------------------------------------------------------------------
# _parse_response
# ---------------------------------------------------------------------------


class TestParseResponse:
    """Issue #141 — malformed GPT response handling."""

    def test_valid_json(self) -> None:
        result = FoundryAgentClient._parse_response('{"a": 1}')
        assert result == {"a": 1}

    def test_json_in_code_fence(self) -> None:
        result = FoundryAgentClient._parse_response('```json\n{"a": 1}\n```')
        assert result == {"a": 1}

    def test_empty_string(self) -> None:
        result = FoundryAgentClient._parse_response("")
        assert "parse_error" in result
        assert result["raw_text"] == ""

    def test_whitespace_only(self) -> None:
        result = FoundryAgentClient._parse_response("   \n  ")
        assert "parse_error" in result

    def test_non_json_text(self) -> None:
        result = FoundryAgentClient._parse_response("I'm sorry, I can't do that.")
        assert "parse_error" in result
        assert "I'm sorry" in result["raw_text"]

    def test_json_list_wrapped(self) -> None:
        result = FoundryAgentClient._parse_response("[1, 2, 3]")
        assert isinstance(result, dict)
        assert result["data"] == [1, 2, 3]
        assert "raw_text" in result

    def test_json_wrong_types(self) -> None:
        """JSON parses but keys have unexpected types — still returns a dict."""
        result = FoundryAgentClient._parse_response('{"risk_score": "high", "recommended_premium": null}')
        assert isinstance(result, dict)
        assert result["risk_score"] == "high"
        assert result["recommended_premium"] is None

    def test_json_missing_expected_keys(self) -> None:
        """JSON is valid but doesn't have the keys we want."""
        result = FoundryAgentClient._parse_response('{"foo": "bar"}')
        assert isinstance(result, dict)
        assert "risk_score" not in result

    def test_partial_json(self) -> None:
        result = FoundryAgentClient._parse_response('{"a": 1, "b":')
        assert "parse_error" in result


# ---------------------------------------------------------------------------
# validate_agent_response
# ---------------------------------------------------------------------------


class TestValidateAgentResponse:
    def test_valid_response(self) -> None:
        ok, issues = validate_agent_response(
            {"risk_score": 5, "appetite_match": "yes"},
            required_keys=["risk_score", "appetite_match"],
        )
        assert ok is True
        assert issues == []

    def test_missing_keys(self) -> None:
        ok, issues = validate_agent_response(
            {"foo": "bar"},
            required_keys=["risk_score"],
        )
        assert ok is False
        assert any("risk_score" in i for i in issues)

    def test_parse_error_present(self) -> None:
        ok, issues = validate_agent_response(
            {"raw_text": "hello", "parse_error": "not JSON"},
        )
        assert ok is False
        assert any("Parse error" in i for i in issues)

    def test_not_a_dict(self) -> None:
        ok, _issues = validate_agent_response("string value")  # type: ignore[arg-type]
        assert ok is False

    def test_no_required_keys(self) -> None:
        ok, _issues = validate_agent_response({"x": 1})
        assert ok is True


# ---------------------------------------------------------------------------
# _is_transient_error
# ---------------------------------------------------------------------------


class TestIsTransientError:
    def test_timeout_error(self) -> None:
        assert _is_transient_error(TimeoutError("request timed out")) is True

    def test_429(self) -> None:
        assert _is_transient_error(Exception("HTTP 429 Too Many Requests")) is True

    def test_500(self) -> None:
        assert _is_transient_error(Exception("500 Internal Server Error")) is True

    def test_503(self) -> None:
        assert _is_transient_error(Exception("503 Service Unavailable")) is True

    def test_400_not_transient(self) -> None:
        assert _is_transient_error(Exception("400 Bad Request")) is False

    def test_connection_error(self) -> None:
        assert _is_transient_error(ConnectionError("refused")) is True

    def test_status_code_attribute(self) -> None:
        exc = Exception("err")
        exc.status_code = 503  # type: ignore[attr-defined]
        assert _is_transient_error(exc) is True


# ---------------------------------------------------------------------------
# CircuitBreaker
# ---------------------------------------------------------------------------


class TestCircuitBreaker:
    def test_starts_closed(self) -> None:
        cb = CircuitBreaker()
        assert cb.state == "closed"
        assert cb.is_open is False

    def test_opens_after_threshold(self) -> None:
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        for _ in range(3):
            cb.record_failure()
        assert cb.is_open is True

    def test_stays_closed_below_threshold(self) -> None:
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert cb.is_open is False

    def test_success_resets(self) -> None:
        cb = CircuitBreaker(failure_threshold=2)
        cb.record_failure()
        cb.record_success()
        cb.record_failure()
        assert cb.is_open is False  # reset by success

    def test_half_open_after_recovery(self) -> None:
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0)
        cb.record_failure()
        assert cb.state == "half_open"  # 0s recovery

    def test_half_open_success_closes(self) -> None:
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0)
        cb.record_failure()
        _ = cb.state  # trigger half_open
        cb.record_success()
        assert cb.state == "closed"


# ---------------------------------------------------------------------------
# invoke — retry behaviour
# ---------------------------------------------------------------------------


class TestInvokeRetry:
    @pytest.mark.asyncio
    async def test_success_no_retry(self) -> None:
        openai = _openai_ok()
        client = _make_client(openai)
        result = await client.invoke("agent", "hello")
        assert result["source"] == "foundry"
        assert openai.responses.create.call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_transient_then_succeeds(self) -> None:
        openai = MagicMock()
        call_count = 0

        def side_effect(**kw: Any) -> SimpleNamespace:  # noqa: ARG001
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("503 Service Unavailable")  # noqa: TRY002
            return SimpleNamespace(output_text='{"ok": true}')

        openai.responses.create.side_effect = side_effect
        client = _make_client(openai, max_retries=2)
        result = await client.invoke("agent", "hi")
        assert result["source"] == "foundry"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_permanent_error_no_retry(self) -> None:
        openai = MagicMock()
        openai.responses.create.side_effect = Exception("400 Bad Request")
        client = _make_client(openai, max_retries=2)
        result = await client.invoke("agent", "hi")
        assert result["source"] == "fallback"
        assert "400" in result["error"]
        assert openai.responses.create.call_count == 1

    @pytest.mark.asyncio
    async def test_all_retries_exhausted(self) -> None:
        openai = MagicMock()
        openai.responses.create.side_effect = Exception("503 Service Unavailable")
        cb = CircuitBreaker(failure_threshold=10)
        client = _make_client(openai, max_retries=2, circuit_breaker=cb)
        result = await client.invoke("agent", "hi")
        assert result["source"] == "fallback"
        assert "503" in result["error"]
        assert openai.responses.create.call_count == 3  # 1 + 2 retries

    @pytest.mark.asyncio
    async def test_circuit_breaker_prevents_call(self) -> None:
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure()  # open the breaker
        client = _make_client(circuit_breaker=cb)
        result = await client.invoke("agent", "hi")
        assert result["source"] == "fallback"
        assert "circuit breaker" in result["error"].lower()
        assert client._openai.responses.create.call_count == 0

    @pytest.mark.asyncio
    async def test_timeout_passed_to_sdk(self) -> None:
        openai = _openai_ok()
        client = _make_client(openai, timeout=42)
        await client.invoke("agent", "hi")
        _, kwargs = openai.responses.create.call_args
        assert kwargs["timeout"] == 42

    @pytest.mark.asyncio
    async def test_timeout_override(self) -> None:
        openai = _openai_ok()
        client = _make_client(openai, timeout=42)
        await client.invoke("agent", "hi", timeout=10)
        _, kwargs = openai.responses.create.call_args
        assert kwargs["timeout"] == 10

    @pytest.mark.asyncio
    async def test_invoke_in_conversation_retry(self) -> None:
        openai = MagicMock()
        call_count = 0

        def side_effect(**kw: Any) -> SimpleNamespace:  # noqa: ARG001
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("429 Rate limit")  # noqa: TRY002
            return SimpleNamespace(output_text='{"ok": true}')

        openai.responses.create.side_effect = side_effect
        client = _make_client(openai, max_retries=2)
        result = await client.invoke_in_conversation("agent", "hi", "conv-1")
        assert result["source"] == "foundry"
        assert call_count == 2


# ---------------------------------------------------------------------------
# invoke — malformed response handling (Issue #141)
# ---------------------------------------------------------------------------


class TestInvokeMalformedResponse:
    @pytest.mark.asyncio
    async def test_non_json_response(self) -> None:
        openai = _openai_ok("Sorry, I cannot process that request.")
        client = _make_client(openai)
        result = await client.invoke("agent", "hi")
        assert result["source"] == "foundry"
        resp = result["response"]
        assert isinstance(resp, dict)
        assert "parse_error" in resp

    @pytest.mark.asyncio
    async def test_empty_response(self) -> None:
        openai = _openai_ok("")
        client = _make_client(openai)
        result = await client.invoke("agent", "hi")
        resp = result["response"]
        assert isinstance(resp, dict)
        assert "parse_error" in resp

    @pytest.mark.asyncio
    async def test_json_missing_keys(self) -> None:
        openai = _openai_ok('{"unrelated": "data"}')
        client = _make_client(openai)
        result = await client.invoke("agent", "hi")
        resp = result["response"]
        assert isinstance(resp, dict)
        assert "risk_score" not in resp

    @pytest.mark.asyncio
    async def test_json_wrong_types(self) -> None:
        openai = _openai_ok('{"risk_score": "not_a_number"}')
        client = _make_client(openai)
        result = await client.invoke("agent", "hi")
        resp = result["response"]
        assert isinstance(resp, dict)
        assert resp["risk_score"] == "not_a_number"
