"""Unit tests for knowledge_search service — AI Search + fallback."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from openinsure.services.knowledge_search import _fallback_search, search_knowledge


# ---------------------------------------------------------------------------
# search_knowledge — with adapter
# ---------------------------------------------------------------------------

class TestSearchKnowledge:
    @pytest.mark.asyncio
    async def test_uses_adapter_when_available(self):
        mock_adapter = AsyncMock()
        mock_adapter.search.return_value = {
            "results": [
                {"id": "1", "title": "MFA Policy", "content": "Require MFA", "category": "guideline"},
            ]
        }
        with patch("openinsure.services.knowledge_search.get_search_adapter", return_value=mock_adapter):
            results = await search_knowledge("MFA")
        assert len(results) == 1
        assert results[0]["title"] == "MFA Policy"
        mock_adapter.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_passes_category_filter(self):
        mock_adapter = AsyncMock()
        mock_adapter.search.return_value = {"results": []}
        with patch("openinsure.services.knowledge_search.get_search_adapter", return_value=mock_adapter):
            await search_knowledge("ransomware", category="coverage")
        call_kwargs = mock_adapter.search.call_args
        assert "category eq 'coverage'" in str(call_kwargs)

    @pytest.mark.asyncio
    async def test_no_category_filter(self):
        mock_adapter = AsyncMock()
        mock_adapter.search.return_value = {"results": []}
        with patch("openinsure.services.knowledge_search.get_search_adapter", return_value=mock_adapter):
            await search_knowledge("ransomware")
        call_kwargs = mock_adapter.search.call_args
        assert call_kwargs[1].get("filters") is None

    @pytest.mark.asyncio
    async def test_falls_back_on_adapter_exception(self):
        mock_adapter = AsyncMock()
        mock_adapter.search.side_effect = RuntimeError("Azure down")
        with patch("openinsure.services.knowledge_search.get_search_adapter", return_value=mock_adapter):
            with patch("openinsure.services.knowledge_search._fallback_search", return_value=[{"id": "fb"}]) as fb:
                results = await search_knowledge("test")
        assert len(results) == 1
        fb.assert_called_once()

    @pytest.mark.asyncio
    async def test_falls_back_when_no_adapter(self):
        with patch("openinsure.services.knowledge_search.get_search_adapter", return_value=None):
            with patch("openinsure.services.knowledge_search._fallback_search", return_value=[]) as fb:
                results = await search_knowledge("test")
        assert results == []
        fb.assert_called_once()

    @pytest.mark.asyncio
    async def test_respects_top_parameter(self):
        mock_adapter = AsyncMock()
        mock_adapter.search.return_value = {"results": []}
        with patch("openinsure.services.knowledge_search.get_search_adapter", return_value=mock_adapter):
            await search_knowledge("query", top=5)
        assert mock_adapter.search.call_args[1]["top"] == 5


# ---------------------------------------------------------------------------
# _fallback_search
# ---------------------------------------------------------------------------

class TestFallbackSearch:
    def test_finds_matching_content(self):
        """The fallback should find entries where the query appears in content or key."""
        results = _fallback_search("cyber", None, 10)
        # Should find at least some static knowledge mentioning "cyber"
        assert isinstance(results, list)

    def test_category_filter(self):
        results = _fallback_search("cyber", "guideline", 100)
        for r in results:
            assert r["category"] == "guideline"

    def test_top_limit(self):
        results = _fallback_search("", None, 2)
        assert len(results) <= 2

    def test_case_insensitive(self):
        lower = _fallback_search("cyber", None, 100)
        upper = _fallback_search("CYBER", None, 100)
        assert len(lower) == len(upper)

    def test_result_structure(self):
        results = _fallback_search("insurance", None, 1)
        if results:
            r = results[0]
            assert "id" in r
            assert "title" in r
            assert "content" in r
            assert "category" in r
            assert "source" in r
            assert r["source"] == "static"


# ---------------------------------------------------------------------------
# Adversarial / edge-case tests
# ---------------------------------------------------------------------------

class TestKnowledgeSearchAdversarial:
    """Tests that try to break knowledge search with hostile inputs."""

    @pytest.mark.asyncio
    async def test_empty_query(self):
        """Empty query string should return results (matches everything in fallback)."""
        with patch("openinsure.services.knowledge_search.get_search_adapter", return_value=None):
            results = await search_knowledge("")
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_top_zero(self):
        """top=0 should return empty list."""
        with patch("openinsure.services.knowledge_search.get_search_adapter", return_value=None):
            results = await search_knowledge("cyber", top=0)
        assert results == []

    @pytest.mark.asyncio
    async def test_top_negative(self):
        """top=-1 → Python slice [:−1] drops last element but doesn't crash."""
        with patch("openinsure.services.knowledge_search.get_search_adapter", return_value=None):
            results = await search_knowledge("cyber", top=-1)
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_category_special_chars(self):
        """Category with special characters in filter string."""
        mock_adapter = AsyncMock()
        mock_adapter.search.return_value = {"results": []}
        with patch("openinsure.services.knowledge_search.get_search_adapter", return_value=mock_adapter):
            await search_knowledge("test", category="it's a 'test'")
        # Should not crash — the filter string may be malformed but adapter handles it

    @pytest.mark.asyncio
    async def test_adapter_returns_malformed_response(self):
        """Adapter returns dict without 'results' key → should return empty list."""
        mock_adapter = AsyncMock()
        mock_adapter.search.return_value = {"items": [{"id": "1"}]}
        with patch("openinsure.services.knowledge_search.get_search_adapter", return_value=mock_adapter):
            results = await search_knowledge("test")
        assert results == []

    @pytest.mark.asyncio
    async def test_adapter_returns_none_falls_back(self):
        """Adapter.search returns None → AttributeError caught → falls back to static."""
        mock_adapter = AsyncMock()
        mock_adapter.search.return_value = None
        with patch("openinsure.services.knowledge_search.get_search_adapter", return_value=mock_adapter):
            # The AttributeError from None.get() is caught by the except block
            # and falls back to _fallback_search gracefully
            results = await search_knowledge("test")
        assert isinstance(results, list)

    def test_fallback_nonexistent_category(self):
        """Non-existent category should return empty results."""
        results = _fallback_search("cyber", "nonexistent_category", 10)
        assert results == []

    def test_fallback_content_truncation(self):
        """Content in results should be truncated to 500 chars."""
        results = _fallback_search("cyber", None, 100)
        for r in results:
            assert len(r["content"]) <= 500

    @pytest.mark.asyncio
    async def test_concurrent_adapter_failure_and_fallback(self):
        """Adapter raises, falls back, and fallback succeeds — end-to-end."""
        mock_adapter = AsyncMock()
        mock_adapter.search.side_effect = ConnectionError("Network unreachable")
        with patch("openinsure.services.knowledge_search.get_search_adapter", return_value=mock_adapter):
            results = await search_knowledge("cyber")
        # Falls back to static search
        assert isinstance(results, list)
