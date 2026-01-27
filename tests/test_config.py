"""Tests for configuration module."""

from pathlib import Path

from sentinel.core.config import Settings


def test_default_settings():
    """Settings load with defaults."""
    settings = Settings(
        _env_file=None,  # Don't load .env in tests
    )
    assert settings.data_dir == Path("data")
    assert settings.max_context_messages == 20


def test_db_path():
    """Database path combines data_dir and db_name."""
    settings = Settings(
        data_dir=Path("/tmp/test"),
        db_name="test.db",
        _env_file=None,
    )
    assert settings.db_path == Path("/tmp/test/test.db")
