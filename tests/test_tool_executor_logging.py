"""Tests for tool executor logging truncation."""

from sentinel.core.types import ActionResult
from sentinel.tools.executor import _truncate_for_logging


def test_truncate_short_result():
    """Test that short results are not truncated."""
    result = ActionResult(
        success=True,
        data={"content": "Short content", "url": "https://example.com"},
    )

    truncated = _truncate_for_logging(result)
    assert "Short content" in truncated
    assert "truncated" not in truncated.lower()


def test_truncate_long_result():
    """Test that long content is truncated."""
    long_content = "A" * 1000
    result = ActionResult(
        success=True,
        data={"content": long_content, "url": "https://example.com"},
    )

    truncated = _truncate_for_logging(result, max_len=100)
    assert "truncated" in truncated.lower()
    assert "1000 chars total" in truncated
    assert len(truncated) < len(long_content)
    # Short fields should not be truncated
    assert "https://example.com" in truncated


def test_truncate_error_result():
    """Test that error results are logged fully."""
    result = ActionResult(success=False, error="Something went wrong")

    truncated = _truncate_for_logging(result)
    assert "Something went wrong" in truncated
    assert "success=false" in truncated.lower()


def test_truncate_multiple_long_fields():
    """Test truncation with multiple long fields."""
    result = ActionResult(
        success=True,
        data={
            "content": "X" * 600,
            "description": "Y" * 600,
            "title": "Short title",
        },
    )

    truncated = _truncate_for_logging(result, max_len=100)
    assert "truncated, 600 chars total" in truncated
    assert "Short title" in truncated


def test_truncate_none_data():
    """Test truncation with None data."""
    result = ActionResult(success=True, data=None)

    truncated = _truncate_for_logging(result)
    assert "success=True" in truncated
    assert "data=None" in truncated
