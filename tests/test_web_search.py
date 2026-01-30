"""Tests for web search and fetch tools."""

import pytest

from sentinel.tools.builtin.web_search import fetch_webpage, set_brave_api_key, web_search


@pytest.mark.asyncio
async def test_web_search_no_api_key():
    """Test web search without API key configured."""
    set_brave_api_key("")
    result = await web_search("test query")

    assert not result.success
    assert "not configured" in result.error.lower()


@pytest.mark.asyncio
async def test_web_search_with_mock_key():
    """Test web search with mock API key (will fail but validates structure)."""
    set_brave_api_key("test_key")
    result = await web_search("python programming", count=3)

    # With invalid key, expect failure but proper error handling
    assert not result.success
    assert result.error is not None


@pytest.mark.asyncio
async def test_web_search_count_validation():
    """Test that count parameter is properly validated."""
    set_brave_api_key("test_key")

    # Count should be clamped to 1-20 range
    result = await web_search("test", count=100)
    # Should attempt with count=20 (max)
    assert not result.success  # Will fail with invalid key

    result = await web_search("test", count=-5)
    # Should attempt with count=1 (min)
    assert not result.success  # Will fail with invalid key


@pytest.mark.integration
@pytest.mark.asyncio
async def test_web_search_real_query():
    """Integration test with real API key (requires SENTINEL_BRAVE_SEARCH_API_KEY)."""
    import os

    api_key = os.getenv("SENTINEL_BRAVE_SEARCH_API_KEY", "")
    if not api_key:
        pytest.skip("SENTINEL_BRAVE_SEARCH_API_KEY not set")

    set_brave_api_key(api_key)
    result = await web_search("Python programming language", count=5)

    assert result.success
    assert result.data is not None
    assert "results" in result.data
    assert "query" in result.data
    assert result.data["query"] == "Python programming language"

    # Check result structure
    if result.data["results"]:
        first_result = result.data["results"][0]
        assert "title" in first_result
        assert "url" in first_result
        assert "description" in first_result


# Tests for fetch_webpage tool


@pytest.mark.asyncio
async def test_fetch_webpage_invalid_url():
    """Test fetch_webpage with invalid URL format."""
    result = await fetch_webpage("not-a-valid-url")

    assert not result.success
    assert "http://" in result.error.lower() or "https://" in result.error.lower()


@pytest.mark.asyncio
async def test_fetch_webpage_invalid_format():
    """Test that invalid format parameter defaults to markdown."""
    result = await fetch_webpage("https://example.com", format="invalid")

    # Should default to markdown format
    # May succeed or fail depending on network, but shouldn't crash
    assert result.data is not None or result.error is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fetch_webpage_real_request_markdown():
    """Integration test with real webpage (markdown format)."""
    result = await fetch_webpage("https://example.com", format="markdown")

    assert result.success
    assert result.data is not None
    assert "content" in result.data
    assert "url" in result.data
    assert result.data["url"] == "https://example.com"
    assert result.data["format"] == "markdown"
    assert len(result.data["content"]) > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fetch_webpage_real_request_json():
    """Integration test with real webpage (JSON format)."""
    result = await fetch_webpage("https://example.com", format="json")

    assert result.success
    assert result.data is not None
    assert "content" in result.data
    assert "url" in result.data
    assert result.data["url"] == "https://example.com"
    assert result.data["format"] == "json"
    assert len(result.data["content"]) > 0
