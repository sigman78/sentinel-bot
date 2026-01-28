"""Tests for Telegram interface."""

from datetime import datetime, timedelta

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


def test_should_quote_reply_first_message():
    """First message should not quote-reply."""
    interface = TelegramInterface.__new__(TelegramInterface)
    interface._last_message_time = None
    assert not interface._should_quote_reply(datetime.now())


def test_should_quote_reply_recent_message():
    """Recent messages (< 5 min) should not quote-reply."""
    interface = TelegramInterface.__new__(TelegramInterface)
    now = datetime.now()
    interface._last_message_time = now - timedelta(minutes=2)
    assert not interface._should_quote_reply(now)


def test_should_quote_reply_old_message():
    """Old messages (5+ min) should quote-reply."""
    interface = TelegramInterface.__new__(TelegramInterface)
    now = datetime.now()
    interface._last_message_time = now - timedelta(minutes=6)
    assert interface._should_quote_reply(now)


def test_should_quote_reply_boundary():
    """5 minute boundary should trigger quote-reply."""
    interface = TelegramInterface.__new__(TelegramInterface)
    now = datetime.now()
    interface._last_message_time = now - timedelta(seconds=300)
    assert interface._should_quote_reply(now)
