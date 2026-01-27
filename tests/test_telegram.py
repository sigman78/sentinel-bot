"""Tests for Telegram interface."""

from sentinel.interfaces.telegram import TelegramInterface


def test_split_message_short():
    """Short messages should not be split."""
    interface = TelegramInterface.__new__(TelegramInterface)
    chunks = interface._split_message("Hello world", 4000)
    assert len(chunks) == 1
    assert chunks[0] == "Hello world"


def test_split_message_long():
    """Long messages should be split."""
    interface = TelegramInterface.__new__(TelegramInterface)
    text = "A" * 5000
    chunks = interface._split_message(text, 4000)
    assert len(chunks) == 2
    assert len(chunks[0]) == 4000
    assert len(chunks[1]) == 1000


def test_split_message_at_newline():
    """Should prefer splitting at newlines."""
    interface = TelegramInterface.__new__(TelegramInterface)
    text = "A" * 3000 + "\n" + "B" * 2000
    chunks = interface._split_message(text, 4000)
    assert len(chunks) == 2
    assert chunks[0].endswith("\n")
    assert chunks[1].startswith("B")


def test_split_message_at_space():
    """Should prefer splitting at spaces when no newline."""
    interface = TelegramInterface.__new__(TelegramInterface)
    text = "word " * 1000  # 5000 chars
    chunks = interface._split_message(text, 4000)
    assert len(chunks) == 2
    # Should split at word boundary
    assert not chunks[0].endswith("wor")
